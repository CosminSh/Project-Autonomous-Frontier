import asyncio
import logging
import os
import random
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Agent, Intent, AuditLog, WorldHex, ChassisPart, InventoryItem, AuctionOrder
from .bot_logic import process_bot_brain
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import uuid

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heartbeat")

# Game Constants (GDD Section 3.2 & 5.2)
MOVE_ENERGY_COST = 5
MINE_ENERGY_COST = 10
ATTACK_ENERGY_COST = 15
RECHARGE_RATE = 2 # Energy recharged per tick
TICK_DURATION = 5 # Seconds
MAX_CAPACITOR = 100

# Death & Respawn Constants
TOWN_COORDINATES = (0, 0)
INVENTORY_LOSS_CHANCE = 0.5
INVENTORY_LOSS_PERCENT = 0.3
RESPAWN_HP_PERCENT = 0.5

def get_hex_distance(q1, r1, q2, r2):
    """
    Calculates distance on a cube/axial hex grid.
    Dist = (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) / 2
    """
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./demo.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(
    title="STRIKE-VECTOR: SOL API",
    description="Backend API for STRIKE-VECTOR agent-centric industrial RPG",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Required for Google OAuth popups to communicate back to the window
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_api_key(request: Request, db: Session = Depends(get_db)):
    api_key = request.headers.get("X-API-KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )
    
    agent = db.execute(select(Agent).where(Agent.api_key == api_key)).scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return agent

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "419308259695-sj14gj8q7ml5o9uao2j59pgkp1vvthh0.apps.googleusercontent.com")

@app.post("/auth/login")
async def login(request: Request):
    print("\n--- AUTH LOGIN REQUEST RECEIVED ---")
    try:
        data = await request.json()
        token = data.get("token")
        if not token:
            print("ERROR: No token in request data")
            return {"status": "error", "message": "Missing token"}
        
        print(f"Token length: {len(token)}")
        
        try:
            # Verify Google JWT
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
            email = idinfo['email']
            name = idinfo.get('name', email.split('@')[0])
            print(f"VERIFIED GOOGLE USER: {email}")
        except Exception as e:
            print(f"GOOGLE VERIFICATION FAILED: {str(e)}")
            return {"status": "error", "message": f"Google Verification Failed: {str(e)}"}
        
        with SessionLocal() as db:
            print(f"Searching for agent with email: {email}")
            agent = db.execute(select(Agent).where(Agent.user_email == email)).scalar_one_or_none()
            if not agent:
                print(f"CREATING NEW AGENT for {email}")
                # Create new Agent for this user
                api_key = str(uuid.uuid4())
                agent = Agent(
                    user_email=email,
                    name=name,
                    api_key=api_key,
                    owner="player",
                    q=0, r=0,
                    structure=100, max_structure=100, capacitor=100
                )
                db.add(agent)
                db.flush()
                # Give starting credits
                db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
                db.commit()
                db.refresh(agent)
                print(f"Agent created: ID={agent.id}")
            else:
                print(f"EXISTING AGENT FOUND: ID={agent.id}")
            
            return {
                "status": "success",
                "api_key": agent.api_key,
                "agent_id": agent.id,
                "name": agent.name
            }
            
    except Exception as e:
        print(f"CRITICAL LOGIN ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Server Error: {str(e)}"}

@app.get("/api/global_stats")
async def global_stats(db: Session = Depends(get_db)):
    agent_count = db.execute(select(func.count(Agent.id))).scalar()
    item_count = db.execute(select(func.count(InventoryItem.id))).scalar()
    trade_count = db.execute(select(func.count(AuctionOrder.id))).scalar()
    
    return {
        "total_agents": agent_count,
        "total_items": item_count,
        "market_listings": trade_count,
        "status": "online"
    }

@app.post("/auth/guest")
async def guest_login(db: Session = Depends(get_db)):
    """Bypass Auth for local testing. Returns the first player agent's key."""
    print("--- GUEST LOGIN REQUEST ---")
    agent = db.execute(select(Agent).where(Agent.owner == "player")).first()
    if not agent:
        # Create a default one if none exists
        from uuid import uuid4
        agent = Agent(
            user_email="guest@local.test",
            name="Guest-Pilot",
            api_key=str(uuid4()),
            owner="player",
            q=0, r=0,
            structure=100, max_structure=100, capacitor=100
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
    
    # Extract agent from row if needed (SQLAlchemy 2.0 select returns Row)
    if hasattr(agent, "Agent"): agent = agent.Agent
    elif isinstance(agent, tuple): agent = agent[0]

    return {
        "status": "success",
        "api_key": agent.api_key,
        "agent_id": agent.id,
        "name": agent.name
    }

@app.get("/api/my_agent")
async def my_agent(current_agent: Agent = Depends(verify_api_key)):
    return {
        "id": current_agent.id,
        "name": current_agent.name,
        "structure": current_agent.structure,
        "max_structure": current_agent.max_structure,
        "capacitor": current_agent.capacitor,
        "q": current_agent.q,
        "r": current_agent.r,
        "inventory": [
            {"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory
        ],
        "parts": [
            {"name": p.name, "type": p.part_type, "stats": p.stats} for p in current_agent.parts
        ],
        "api_key": current_agent.api_key
    }

@app.get("/api/agent_logs")
async def get_agent_logs(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    logs = db.execute(select(AuditLog).where(AuditLog.agent_id == current_agent.id).order_by(AuditLog.time.desc()).limit(20)).scalars().all()
    return [
        {"time": l.time, "event": l.event_type, "details": l.details} for l in logs
    ]

async def heartbeat_loop():
    tick_count = 0
    while True:
        tick_count += 1
        logger.info(f"--- STARTING TICK {tick_count} ---")
        
        try:
            with SessionLocal() as db:
                # 1. Read all intents for current tick
                intents = db.execute(select(Intent)).scalars().all()
                
                for intent in intents:
                    agent = db.get(Agent, intent.agent_id)
                    if not agent:
                        continue
                        
                    # 1.1 Process Bot Brain for the NEXT tick if this is a bot
                    if agent.is_bot:
                        process_bot_brain(db, agent, tick_count)

                    if intent.action_type == "MOVE":
                        if agent.capacitor < MOVE_ENERGY_COST:
                            logger.info(f"Agent {agent.id} failed to move: Insufficient Capacitor ({agent.capacitor}/{MOVE_ENERGY_COST})")
                            continue

                        target_q = intent.data.get("target_q")
                        target_r = intent.data.get("target_r")
                        
                        # Collision Check
                        obstacle = db.execute(select(WorldHex).where(
                            WorldHex.q == target_q, 
                            WorldHex.r == target_r,
                            WorldHex.terrain_type == "OBSTACLE"
                        )).scalar_one_or_none()
                        
                        if not obstacle:
                            agent.q = target_q
                            agent.r = target_r
                            agent.capacitor -= MOVE_ENERGY_COST
                            logger.info(f"Agent {agent.id} moved to ({target_q}, {target_r}). Energy: {agent.capacitor}")
                        else:
                            logger.info(f"Agent {agent.id} hit obstacle at ({target_q}, {target_r})")
                            
                    elif intent.action_type == "MINE":
                        if agent.capacitor < MINE_ENERGY_COST:
                            logger.info(f"Agent {agent.id} failed to mine: Insufficient Capacitor ({agent.capacitor}/{MINE_ENERGY_COST})")
                            continue

                        hex_data = db.execute(select(WorldHex).where(
                            WorldHex.q == agent.q, 
                            WorldHex.r == agent.r
                        )).scalar_one_or_none()
                        
                        if hex_data and hex_data.resource_type in ["IRON_ORE", "COBALT_ORE", "GOLD_ORE", "ORE"]:
                            # Check for Drill in Actuators
                            has_drill = any(p.part_type == "Actuator" and "Drill" in p.name for p in agent.parts)
                            if has_drill:
                                yield_amount = int(agent.kinetic_force * 0.5 * hex_data.resource_density)
                                agent.capacitor -= MINE_ENERGY_COST
                                
                                # Add to Inventory
                                resource_name = hex_data.resource_type if "_ORE" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
                                inv_item = next((i for i in agent.inventory if i.item_type == resource_name), None)
                                if inv_item:
                                    inv_item.quantity += yield_amount
                                else:
                                    from models import InventoryItem
                                    db.add(InventoryItem(agent_id=agent.id, item_type=resource_name, quantity=yield_amount))

                                logger.info(f"Agent {agent.id} mined {yield_amount} {resource_name}. Energy: {agent.capacitor}")
                                # Log to Audit (TimescaleDB)
                                log = AuditLog(
                                    agent_id=agent.id,
                                    event_type="MINING",
                                    details={"amount": yield_amount, "location": {"q": agent.q, "r": agent.r}}
                                )
                                db.add(log)
                            else:
                                logger.info(f"Agent {agent.id} failed to mine: No Drill")
                                
                    elif intent.action_type == "ATTACK":
                        if agent.capacitor < ATTACK_ENERGY_COST:
                            logger.info(f"Agent {agent.id} failed to attack: Insufficient Capacitor ({agent.capacitor}/{ATTACK_ENERGY_COST})")
                            continue
                            
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        
                        if not target:
                            logger.info(f"Agent {agent.id} failed to attack: Target {target_id} not found")
                            continue
                            
                        # Range Check (Adjacent hex)
                        dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
                        if dist > 1:
                            logger.info(f"Agent {agent.id} failed to attack: Target {target_id} too far (dist={dist})")
                            continue
                            
                        # Hit Resolution: (Attacker.Logic / Target.Logic) * 75%
                        hit_chance = (agent.logic_precision / target.logic_precision) * 0.75
                        roll = random.random()
                        
                        agent.capacitor -= ATTACK_ENERGY_COST
                        
                        if roll <= hit_chance:
                            # Damage Calculation: (Base Damage - Target.Armor) min 1
                            # Base Damage is kinetics_force for now
                            damage = max(1, agent.kinetic_force - target.integrity)
                            target.structure -= damage
                            logger.info(f"Agent {agent.id} HIT Agent {target_id} for {damage} damage! Target HP: {target.structure}. Energy: {agent.capacitor}")
                            
                            # Audit log
                            db.add(AuditLog(
                                agent_id=agent.id,
                                event_type="COMBAT_HIT",
                                details={"target_id": target_id, "damage": damage}
                            ))
                            
                            if target.structure <= 0:
                                logger.info(f"Agent {target_id} has been CRITICALLY DAMAGED! Initiating Respawn.")
                                
                                # Respawn Logic
                                target.structure = int(target.max_structure * RESPAWN_HP_PERCENT)
                                target.q, target.r = TOWN_COORDINATES
                                
                                # Inventory Loss & Transfer
                                for item in target.inventory:
                                    if random.random() <= INVENTORY_LOSS_CHANCE:
                                        amount_lost = int(item.quantity * INVENTORY_LOSS_PERCENT)
                                        if amount_lost > 0:
                                            item.quantity -= amount_lost
                                            logger.info(f"Agent {target_id} lost {amount_lost} of {item.item_type}")
                                            
                                            # Transfer to attacker (PvP)
                                            # Search for existing stack in attacker's inventory
                                            attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                            if attacker_item:
                                                attacker_item.quantity += amount_lost
                                            else:
                                                from models import InventoryItem
                                                db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amount_lost))
                                
                                db.add(AuditLog(
                                    agent_id=target_id,
                                    event_type="RESPAWNED",
                                    details={"killed_by": agent.id, "location": list(TOWN_COORDINATES)}
                                ))
                        else:
                            logger.info(f"Agent {agent.id} MISSED Agent {target_id}! Energy: {agent.capacitor}")
                            db.add(AuditLog(
                                agent_id=agent.id,
                                event_type="COMBAT_MISS",
                                details={"target_id": target_id}
                            ))

                    elif intent.action_type == "SMELT":
                        # Raw Ore -> Refined Metal
                        # Check if at Smelter
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "SMELTER":
                            ore_type = intent.data.get("ore_type", "IRON_ORE")
                            refined_type = ore_type.replace("_ORE", "_INGOT")
                            
                            raw_ore = next((i for i in agent.inventory if i.item_type == ore_type), None)
                            if raw_ore and raw_ore.quantity >= 10:
                                raw_ore.quantity -= 10
                                refined = next((i for i in agent.inventory if i.item_type == refined_type), None)
                                if refined:
                                    refined.quantity += 1
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type=refined_type, quantity=1))
                                logger.info(f"Agent {agent.id} smelted 10 {ore_type} into 1 {refined_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="SMELTING", details={"ore": ore_type, "yield": 1}))
                            else:
                                logger.info(f"Agent {agent.id} failed to smelt: Insufficient {ore_type}")
                        else:
                            logger.info(f"Agent {agent.id} failed to smelt: Not at Smelter")

                    elif intent.action_type == "CRAFT":
                        # Refined Metal -> Chassis Part
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "CRAFTER":
                            ingot_type = intent.data.get("ingot_type", "IRON_INGOT")
                            refined = next((i for i in agent.inventory if i.item_type == ingot_type), None)
                            if refined and refined.quantity >= 5:
                                refined.quantity -= 5
                                # Create a part based on ingot level
                                tier = "Mk1" if "IRON" in ingot_type else ("Mk2" if "COBALT" in ingot_type else "Mk3")
                                part_name = f"{tier} {random.choice(['Laser', 'Shield', 'Engine'])}"
                                power_bonus = 10 if tier == "Mk1" else (25 if tier == "Mk2" else 50)
                                
                                db.add(ChassisPart(agent_id=agent.id, name=part_name, part_type="Actuator", stats={"power": power_bonus}))
                                logger.info(f"Agent {agent.id} crafted {part_name}")
                                db.add(AuditLog(agent_id=agent.id, event_type="CRAFTING", details={"item": part_name, "tier": tier}))
                            else:
                                logger.info(f"Agent {agent.id} failed to craft: Insufficient {ingot_type}")
                        else:
                            logger.info(f"Agent {agent.id} failed to craft: Not at Crafter")

                    elif intent.action_type == "LIST":
                        # List item on Auction House
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                            item_type = intent.data.get("item_type")
                            price = intent.data.get("price")
                            quantity = intent.data.get("quantity", 1)
                            
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item and inv_item.quantity >= quantity:
                                inv_item.quantity -= quantity
                                db.add(AuctionOrder(
                                    item_type=item_type,
                                    order_type="SELL",
                                    quantity=quantity,
                                    price=price,
                                    owner=f"agent:{agent.id}"
                                ))
                                logger.info(f"Agent {agent.id} listed {quantity} {item_type} at {price}")
                            else:
                                logger.info(f"Agent {agent.id} failed to list: Insufficient Inventory")
                        else:
                            logger.info(f"Agent {agent.id} failed to list: Not at Market")

                    elif intent.action_type == "BUY":
                        # Buy item from Auction House
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                            item_type = intent.data.get("item_type")
                            max_price = intent.data.get("max_price")
                            
                            # Find cheapest order
                            order = db.execute(select(AuctionOrder)
                                .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "SELL", AuctionOrder.price <= max_price)
                                .order_by(AuctionOrder.price.asc())
                            ).scalars().first()
                            
                            if order:
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if credits and credits.quantity >= order.price:
                                    credits.quantity -= int(order.price)
                                    
                                    # Add item to buyer
                                    target_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                                    if target_item:
                                        target_item.quantity += 1
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1))
                                    
                                    # Update or Delete order
                                    if order.quantity > 1:
                                        order.quantity -= 1
                                    else:
                                        db.delete(order)
                                        
                                    # Pay seller (stub for now, assuming owner is "agent:ID")
                                    if order.owner.startswith("agent:"):
                                        seller_id = int(order.owner.split(":")[1])
                                        seller_credits = db.execute(select(InventoryItem).where(InventoryItem.agent_id == seller_id, InventoryItem.item_type == "CREDITS")).scalar_one_or_none()
                                        if seller_credits:
                                            seller_credits.quantity += int(order.price)
                                            
                                    logger.info(f"Agent {agent.id} bought 1 {item_type} for {order.price}")
                                else:
                                    logger.info(f"Agent {agent.id} failed to buy: Insufficient Credits")
                            else:
                                logger.info(f"Agent {agent.id} failed to buy: No matching orders")
                        else:
                            logger.info(f"Agent {agent.id} failed to buy: Not at Market")

                # 2. Recharge logic (runs every tick for all agents)
                agents = db.execute(select(Agent)).scalars().all()
                for agent in agents:
                    if agent.capacitor < MAX_CAPACITOR:
                        agent.capacitor = min(MAX_CAPACITOR, agent.capacitor + RECHARGE_RATE)
                
                # Delete current intents
                db.execute(text("DELETE FROM intents"))
                
                # Check for bots with no future intents and prompt them
                bots = db.execute(select(Agent).where(Agent.is_bot == True)).scalars().all()
                for bot in bots:
                    # If no intent for next tick, process brain
                    future_intent = db.execute(select(Intent).where(Intent.agent_id == bot.id, Intent.tick_index > tick_count)).first()
                    if not future_intent:
                        process_bot_brain(db, bot, tick_count)

                db.commit()
                
        except Exception as e:
            logger.error(f"Error in heartbeat: {e}")
            
        logger.info(f"--- TICK {tick_count} COMPLETE ---")
        await asyncio.sleep(TICK_DURATION)

@app.on_event("startup")
async def startup_event():
    # Ensure tables exist
    Base.metadata.create_all(engine)
    # Run heartbeat in background
    asyncio.create_task(heartbeat_loop())


@app.get("/api/perception")
async def get_perception_packet(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # 1. Get stats and battery
    stats = {
        "id": current_agent.id,
        "name": current_agent.name,
        "structure": current_agent.structure,
        "capacitor": current_agent.capacitor,
        "kinetic_force": current_agent.kinetic_force,
        "logic_precision": current_agent.logic_precision,
        "overclock": current_agent.overclock,
        "location": {"q": current_agent.q, "r": current_agent.r}
    }
    
    # 2. Get nearby entities (Radius determined by Sensor part, default 2)
    sensor_radius = 2
    for part in current_agent.parts:
        if part.part_type == "Sensor":
            sensor_radius = part.stats.get("radius", 2)
    
    # Proper Hex Distance Check
    nearby_agents = db.execute(select(Agent).where(
        Agent.id != current_agent.id
    )).scalars().all()
    nearby_agents = [a for a in nearby_agents if get_hex_distance(current_agent.q, current_agent.r, a.q, a.r) <= sensor_radius]
    
    nearby_resources = db.execute(select(WorldHex).where(
        WorldHex.resource_type.is_not(None)
    )).scalars().all()
    nearby_resources = [r for r in nearby_resources if get_hex_distance(current_agent.q, current_agent.r, r.q, r.r) <= sensor_radius]
    
    # 3. Auction House Prices (Top 3 materials)
    top_prices = db.execute(select(AuctionOrder).where(
        AuctionOrder.order_type == "SELL"
    ).order_by(AuctionOrder.price.asc()).limit(3)).scalars().all()
    
    # 4. MCP Format
    mcp_packet = {
        "mcp_version": "1.0",
        "uri": f"mcp://strike-vector/perception/{current_agent.id}",
        "type": "resource",
        "content": {
            "agent_status": stats,
            "environment": {
                "other_agents": [{"id": a.id, "q": a.q, "r": a.r} for a in nearby_agents],
                "resources": [{"type": r.resource_type, "density": r.resource_density, "q": r.q, "r": r.r} for r in nearby_resources]
            },
            "market_data": [{"item": p.item_type, "price": p.price} for p in top_prices]
        }
    }
    
    return mcp_packet

@app.post("/api/intent")
async def submit_intent(action_type: str, data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    intent = Intent(
        agent_id=current_agent.id,
        action_type=action_type,
        data=data,
        tick_index=0 # In a real implementation, we'd fetch current global tick
    )
    db.add(intent)
    db.commit()
    return {"status": "Intent recorded"}

@app.get("/state")
async def get_world_state():
    with SessionLocal() as db:
        agents = db.execute(select(Agent)).scalars().all()
        hexes = db.execute(select(WorldHex)).scalars().all()
        orders = db.execute(select(AuctionOrder)).scalars().all()
        
        return {
            "agents": [{
                "id": a.id,
                "name": a.name,
                "q": a.q,
                "r": a.r,
                "structure": a.structure,
                "max_structure": a.max_structure,
                "capacitor": a.capacitor,
                "inventory": [{"type": i.item_type, "quantity": i.quantity} for i in a.inventory]
            } for a in agents],
            "world": [{
                "q": h.q,
                "r": h.r,
                "terrain": h.terrain_type,
                "resource": h.resource_type,
                "density": h.resource_density,
                "is_station": h.is_station,
                "station_type": h.station_type
            } for h in hexes],
            "market": [{
                "item": o.item_type,
                "price": o.price,
                "quantity": o.quantity,
                "type": o.order_type
            } for o in orders]
        }

# Mount static files
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(base_dir, "frontend")

if os.path.exists(frontend_path):
    from fastapi.responses import FileResponse
    
    @app.get("/dashboard")
    async def get_dashboard():
        return FileResponse(os.path.join(frontend_path, "dashboard.html"))

    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    # Mount frontend directory for scripts/styles
    app.mount("/", StaticFiles(directory=frontend_path), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to the STRIKE-VECTOR: SOL API",
            "status": "online",
            "version": "0.1.3",
            "note": f"Frontend directory not found at {frontend_path}."
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
