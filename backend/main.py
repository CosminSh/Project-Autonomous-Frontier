import asyncio
import logging
import os
import random
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, Request, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Agent, Intent, AuditLog, WorldHex, ChassisPart, InventoryItem, AuctionOrder, GlobalState
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
MAX_CAPACITOR = 100

# Tick Phase Durations (GDD Section 5.2 - Scaled for Testing)
PHASE_PERCEPTION_DURATION = 5
PHASE_STRATEGY_DURATION = 10
PHASE_CRUNCH_DURATION = 5

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/strike_vector")
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

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle stale connections
                continue

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Just keep it alive or listen for client-side events
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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

@app.get("/api/commands")
async def get_commands():
    """Returns all available agent commands and their syntax."""
    return {
        "commands": [
            {
                "type": "MOVE",
                "description": "Move your agent to an adjacent hex.",
                "payload": {"target_q": "int", "target_r": "int"},
                "cost": MOVE_ENERGY_COST
            },
            {
                "type": "MINE",
                "description": "Extract resources from the current hex. Requires Drill part.",
                "payload": {},
                "cost": MINE_ENERGY_COST
            },
            {
                "type": "ATTACK",
                "description": "Engage another agent in combat.",
                "payload": {"target_id": "int"},
                "cost": ATTACK_ENERGY_COST
            },
            {
                "type": "LIST",
                "description": "List an item on the Auction House (must be at a Market station).",
                "payload": {"item_type": "str", "price": "int", "quantity": "int"},
                "cost": 0
            },
            {
                "type": "BUY",
                "description": "Purchase an item from the Auction House (must be at a Market station).",
                "payload": {"item_type": "str", "max_price": "int"},
                "cost": 0
            },
            {
                "type": "SMELT",
                "description": "Refine ore into ingots (must be at a Smelter station).",
                "payload": {"ore_type": "str", "quantity": "int"},
                "cost": 0
            },
            {
                "type": "CRAFT",
                "description": "Assemble components into parts (must be at a Crafter station).",
                "payload": {"item_type": "str"},
                "cost": 0
            }
        ],
        "note": "All commands are executed during the CRUNCH phase. Submit via POST /api/intent"
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
    
    # Initialize Global State
    with SessionLocal() as db:
        state = db.execute(select(GlobalState)).scalars().first()
        if not state:
            state = GlobalState(tick_index=0, phase="PERCEPTION")
            db.add(state)
            db.commit()
        tick_count = state.tick_index

    while True:
        tick_count += 1
        
        # --- PHASE 1: PERCEPTION ---
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            state.tick_index = tick_count
            state.phase = "PERCEPTION"
            db.commit()
            logger.info(f"--- TICK {tick_count} | PHASE: PERCEPTION ---")
            await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "PERCEPTION"})
        
        await asyncio.sleep(PHASE_PERCEPTION_DURATION)

        # --- PHASE 2: STRATEGY ---
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            state.phase = "STRATEGY"
            db.commit()
            logger.info(f"--- TICK {tick_count} | PHASE: STRATEGY ---")
            await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "STRATEGY"})
        
        await asyncio.sleep(PHASE_STRATEGY_DURATION)

        # --- PHASE 3: THE CRUNCH (Resolution) ---
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            state.phase = "CRUNCH"
            db.commit()
            logger.info(f"--- TICK {tick_count} | PHASE: THE CRUNCH ---")
            await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "CRUNCH"})
            
            try:
                # 1. Read all intents for current tick
                intents = db.execute(select(Intent)).scalars().all()
                
                # Sort intents by priority if needed (e.g., Attack before Move)
                for intent in intents:
                    agent = db.get(Agent, intent.agent_id)
                    if not agent:
                        continue
                        
                    # 1.1 Process Bot Brain for the NEXT tick if this is a bot and no intent exists
                    if agent.is_bot:
                        # Logic to prevent double-processing if already has one
                        process_bot_brain(db, agent, tick_count)

                    if intent.action_type == "MOVE":
                        if agent.capacitor < MOVE_ENERGY_COST:
                            logger.info(f"Agent {agent.id} failed to move: Insufficient Capacitor")
                            continue

                        target_q = intent.data.get("target_q")
                        target_r = intent.data.get("target_r")
                        
                        # Distance Check (Must be adjacent)
                        if get_hex_distance(agent.q, agent.r, target_q, target_r) > 1:
                            logger.info(f"Agent {agent.id} failed to move: Target too far")
                            continue

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
                            logger.info(f"Agent {agent.id} moved to ({target_q}, {target_r})")
                            await manager.broadcast({"type": "EVENT", "event": "MOVE", "agent_id": agent.id, "q": target_q, "r": target_r})
                        else:
                            logger.info(f"Agent {agent.id} hit obstacle at ({target_q}, {target_r})")
                            
                    elif intent.action_type == "MINE":
                        if agent.capacitor < MINE_ENERGY_COST:
                            logger.info(f"Agent {agent.id} failed to mine: Insufficient Capacitor")
                            continue

                        hex_data = db.execute(select(WorldHex).where(
                            WorldHex.q == agent.q, 
                            WorldHex.r == agent.r
                        )).scalar_one_or_none()
                        
                        if hex_data and hex_data.resource_type:
                            has_drill = any(p.part_type == "Actuator" and "Drill" in p.name for p in agent.parts)
                            if has_drill:
                                # Mining Yield: (1d10 + KineticForce/2) * Density
                                base_yield = random.randint(1, 10) + (agent.kinetic_force // 2)
                                yield_amount = int(base_yield * (hex_data.resource_density or 1.0))
                                agent.capacitor -= MINE_ENERGY_COST
                                
                                resource_name = hex_data.resource_type if "_ORE" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
                                inv_item = next((i for i in agent.inventory if i.item_type == resource_name), None)
                                if inv_item:
                                    inv_item.quantity += yield_amount
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type=resource_name, quantity=yield_amount))

                                logger.info(f"Agent {agent.id} mined {yield_amount} {resource_name}")
                                db.add(AuditLog(agent_id=agent.id, event_type="MINING", details={"amount": yield_amount, "resource": resource_name, "location": {"q": agent.q, "r": agent.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "MINING", "agent_id": agent.id, "amount": yield_amount, "q": agent.q, "r": agent.r})
                            else:
                                logger.info(f"Agent {agent.id} failed to mine: No Drill")
                                
                    elif intent.action_type == "ATTACK":
                        if agent.capacitor < ATTACK_ENERGY_COST:
                            continue
                            
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        
                        if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                            # 1. Hit Resolution (GDD Style: 1d20 + Logic vs 10 + target.Logic/2)
                            attacker_roll = random.randint(1, 20) + agent.logic_precision
                            evasion_target = 10 + (target.logic_precision // 2)
                            
                            agent.capacitor -= ATTACK_ENERGY_COST
                            
                            if attacker_roll >= evasion_target:
                                # 2. Damage Calculation: (Kinetic Force - Target Integrity/2) min 1
                                damage = max(1, agent.kinetic_force - (target.integrity // 2))
                                target.structure -= damage
                                logger.info(f"Agent {agent.id} HIT Agent {target_id} (Roll: {attacker_roll} vs {evasion_target}) for {damage} damage")
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_HIT", details={"target_id": target_id, "damage": damage, "roll": attacker_roll, "location": {"q": target.q, "r": target.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "HIT", "attacker_id": agent.id, "target_id": target_id, "damage": damage, "q": target.q, "r": target.r})
                                
                                # 3. Death Handling
                                if target.structure <= 0:
                                    logger.info(f"Agent {target_id} DEFEATED by {agent.id}")
                                    
                                    # Inventory Transfer (50% of each stack)
                                    for item in target.inventory:
                                        if item.item_type == "CREDITS": continue # Maybe don't drop credits for now
                                        drop_amount = item.quantity // 2
                                        if drop_amount > 0:
                                            item.quantity -= drop_amount
                                            # Add to attacker
                                            attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                            if attacker_item:
                                                attacker_item.quantity += drop_amount
                                            else:
                                                db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=drop_amount))
                                            logger.info(f"Agent {agent.id} looted {drop_amount} {item.item_type} from {target_id}")

                                    target.structure = int(target.max_structure * RESPAWN_HP_PERCENT)
                                    target.q, target.r = TOWN_COORDINATES
                                    db.add(AuditLog(agent_id=target_id, event_type="RESPAWNED", details={"killed_by": agent.id}))
                            else:
                                logger.info(f"Agent {agent.id} MISSED Agent {target_id} (Roll: {attacker_roll} vs {evasion_target})")
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_MISS", details={"target_id": target_id, "roll": attacker_roll, "location": {"q": target.q, "r": target.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "MISS", "attacker_id": agent.id, "target_id": target_id, "q": target.q, "r": target.r})

                    elif intent.action_type == "LIST":
                        # List item on Auction House (SELL order)
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
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_LIST", details={"item": item_type, "price": price, "quantity": quantity, "location": {"q": agent.q, "r": agent.r}}))
                                await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
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
                            
                            # Matching: Find cheapest SELL order
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
                                    
                                    # Update/Delete order
                                    if order.quantity > 1:
                                        order.quantity -= 1
                                    else:
                                        db.delete(order)
                                        
                                    # Pay Seller
                                    if order.owner.startswith("agent:"):
                                        seller_id = int(order.owner.split(":")[1])
                                        seller_credits = db.execute(select(InventoryItem).where(InventoryItem.agent_id == seller_id, InventoryItem.item_type == "CREDITS")).scalar_one_or_none()
                                        if seller_credits:
                                            seller_credits.quantity += int(order.price)
                                            
                                    logger.info(f"Agent {agent.id} bought 1 {item_type} for {order.price}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY", details={"item": item_type, "price": order.price, "location": {"q": agent.q, "r": agent.r}}))
                                    await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                else:
                                    logger.info(f"Agent {agent.id} failed to buy: Insufficient Credits")
                            else:
                                logger.info(f"Agent {agent.id} failed to buy: No matching orders")
                        else:
                            logger.info(f"Agent {agent.id} failed to buy: Not at Market")

                    elif intent.action_type == "SMELT":
                        # Smelt Ore into Ingots at Smelter
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "SMELTER":
                            ore_type = intent.data.get("ore_type", "IRON_ORE")
                            quantity = intent.data.get("quantity", 10)
                            
                            inv_ore = next((i for i in agent.inventory if i.item_type == ore_type), None)
                            if inv_ore and inv_ore.quantity >= quantity:
                                inv_ore.quantity -= quantity
                                ingot_type = ore_type.replace("_ORE", "_INGOT")
                                inv_ingot = next((i for i in agent.inventory if i.item_type == ingot_type), None)
                                
                                amount_produced = quantity // 5 # 5:1 ratio
                                if inv_ingot:
                                    inv_ingot.quantity += amount_produced
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type=ingot_type, quantity=amount_produced))
                                
                                logger.info(f"Agent {agent.id} smelted {quantity} {ore_type} into {amount_produced} {ingot_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_SMELT", details={"ore": ore_type, "amount": amount_produced, "location": {"q": agent.q, "r": agent.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "SMELT", "agent_id": agent.id, "ingot": ingot_type, "q": agent.q, "r": agent.r})
                            else:
                                logger.info(f"Agent {agent.id} failed to smelt: Insufficient Ore")
                        else:
                            logger.info(f"Agent {agent.id} failed to smelt: Not at Smelter")

                    elif intent.action_type == "CRAFT":
                        # Craft Items at Crafter
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "CRAFTER":
                            result_item = intent.data.get("item_type")
                            # Simple recipe: 10 Ingots for a Basic Part
                            ingot_req = 10
                            inv_ingot = next((i for i in agent.inventory if "INGOT" in i.item_type), None) # Use any ingot for now
                            
                            if inv_ingot and inv_ingot.quantity >= ingot_req:
                                inv_ingot.quantity -= ingot_req
                                # Add part to inventory or parts list (GDD suggests modular parts)
                                # For MVP, let's just add it as an InventoryItem with type "PART_..."
                                db.add(InventoryItem(agent_id=agent.id, item_type=f"PART_{result_item}", quantity=1))
                                
                                logger.info(f"Agent {agent.id} crafted {result_item}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_CRAFT", details={"item": result_item, "location": {"q": agent.q, "r": agent.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "CRAFT", "agent_id": agent.id, "item": result_item, "q": agent.q, "r": agent.r})
                            else:
                                logger.info(f"Agent {agent.id} failed to craft: Insufficient Materials")
                        else:
                            logger.info(f"Agent {agent.id} failed to craft: Not at Crafter")

                # 2. Recharge logic
                agents = db.execute(select(Agent)).scalars().all()
                for agent in agents:
                    if agent.capacitor < MAX_CAPACITOR:
                        agent.capacitor = min(MAX_CAPACITOR, agent.capacitor + RECHARGE_RATE)
                
                # 3. Clean up
                db.execute(text("DELETE FROM intents"))
                db.commit()
                
            except Exception as e:
                logger.error(f"Error in crunch: {e}")
                db.rollback()

        await asyncio.sleep(PHASE_CRUNCH_DURATION)

@app.on_event("startup")
async def startup_event():
    # Initialize DB tables
    from .models import Base
    from .seed_world import seed_world
    
    logger.info("Initializing database...")
    Base.metadata.create_all(engine)
    
    # Check if we need to seed
    with SessionLocal() as db:
        if db.execute(select(func.count(WorldHex.id))).scalar() == 0:
            logger.info("World empty. Seeding...")
            seed_world()
        else:
            logger.info("World already seeded.")

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
        state = db.execute(select(GlobalState)).scalars().first()
        
        logs = db.execute(select(AuditLog).order_by(AuditLog.time.desc()).limit(15)).scalars().all()
        
        return {
            "tick": state.tick_index if state else 0,
            "phase": state.phase if state else "PERCEPTION",
            "logs": [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs],
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
