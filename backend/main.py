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
from pydantic import BaseModel

from models import Base, Agent, Intent, AuditLog, WorldHex, ChassisPart, InventoryItem, AuctionOrder, GlobalState, Bounty, LootDrop
from bot_logic import process_bot_brain, process_feral_brain
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

RESPAWN_HP_PERCENT = 0.5
TOWN_COORDINATES = (0, 0)
ANARCHY_THRESHOLD = 5
SOLAR_RADIUS_SAFE = 10
SOLAR_RADIUS_TWILIGHT = 20
CLUTTER_THRESHOLD = 3
CLUTTER_PENALTY = 0.2 # 20% reduction

def is_in_anarchy_zone(q, r):
    """Checks if coordinates are outside the colonial safe zone."""
    dist = get_hex_distance(q, r, 0, 0)
    return dist >= ANARCHY_THRESHOLD

# Industrial Recipes & Costs
SMELTING_RECIPES = {
    "IRON_ORE": "IRON_INGOT",
    "COPPER_ORE": "COPPER_INGOT",
    "GOLD_ORE": "GOLD_INGOT",
    "COBALT_ORE": "COBALT_INGOT"
}
SMELTING_RATIO = 5 # 5 Ore -> 1 Ingot

CRAFTING_RECIPES = {
    "BASIC_FRAME": {"IRON_INGOT": 10},
    "DRILL_UNIT": {"IRON_INGOT": 5, "COPPER_INGOT": 5},
    "SOLAR_PANEL": {"COPPER_INGOT": 8, "GOLD_INGOT": 2},
    "NEURAL_SCANNER": {"GOLD_INGOT": 5, "COBALT_INGOT": 5}
}

REPAIR_COST_PER_HP = 5 # Credits per HP restored
CORE_SERVICE_COST_CREDITS = 500
CORE_SERVICE_COST_IRON_INGOT = 10

# Part Stats Definitions
PART_DEFINITIONS = {
    "BASIC_FRAME": {"type": "Frame", "stats": {"max_structure": 50, "integrity": 5, "capacity": 50}, "name": "Reinforced Chassis"},
    "DRILL_UNIT": {"type": "Actuator", "stats": {"kinetic_force": 8, "logic_precision": -2}, "name": "Titanium Mining Drill"},
    "SOLAR_PANEL": {"type": "Sensor", "stats": {"overclock": 5, "radius": 2}, "name": "High-Efficiency Solar Array"},
    "NEURAL_SCANNER": {"type": "Sensor", "stats": {"radius": 4, "scan_depth": 1}, "name": "Neural-Link Cargo Scanner"}
}

# Mass & Weight System (GDD Milestone 1)
ITEM_WEIGHTS = {
    "CREDITS": 0.0,
    "IRON_ORE": 2.0,
    "COPPER_ORE": 2.0,
    "GOLD_ORE": 3.0,
    "COBALT_ORE": 4.0,
    "IRON_INGOT": 5.0,
    "COPPER_INGOT": 5.0,
    "GOLD_INGOT": 7.0,
    "COBALT_INGOT": 10.0,
    # Parts have higher weight
    "PART_BASIC_FRAME": 50.0,
    "PART_DRILL_UNIT": 15.0,
    "PART_SOLAR_PANEL": 10.0,
    "PART_NEURAL_SCANNER": 12.0,
    "HE3_FUEL_CELL": 5.0
}
BASE_CAPACITY = 100.0

def get_agent_mass(agent):
    """Calculates total mass of agent's inventory."""
    total_mass = 0.0
    for item in agent.inventory:
        weight = ITEM_WEIGHTS.get(item.item_type, 1.0) # Default 1kg for unknown items
        total_mass += weight * item.quantity
    return total_mass

def get_nearest_station(db: Session, agent: Agent, station_type: str):
    """Returns the nearest WorldHex of a specific station type."""
    stations = db.execute(select(WorldHex).where(WorldHex.is_station == True, WorldHex.station_type == station_type)).scalars().all()
    if not stations:
        return None
    return min(stations, key=lambda s: get_hex_distance(agent.q, agent.r, s.q, s.r))

def get_discovery_packet(db: Session, agent: Agent):
    """Returns nearest locations of public service stations."""
    all_stations = db.execute(select(WorldHex).where(WorldHex.is_station == True)).scalars().all()
    discovery = {}
    for st in ["MARKET", "SMELTER", "CRAFTER", "REPAIR"]:
        relevant = [s for s in all_stations if s.station_type == st]
        if relevant:
            nearest = min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s.q, s.r))
            dist = get_hex_distance(agent.q, agent.r, nearest.q, nearest.r)
            discovery[st] = {"q": nearest.q, "r": nearest.r, "distance": dist}
    return discovery

def recalculate_agent_stats(db: Session, agent: Agent):
    """Resets and recalculates agent stats based on equipped parts."""
    # Base Stats
    agent.max_structure = 100
    agent.kinetic_force = 10
    agent.logic_precision = 10
    agent.overclock = 10
    agent.integrity = 5
    
    agent.max_mass = BASE_CAPACITY
    
    # Apply Part Bonuses
    for part in agent.parts:
        stats = part.stats or {}
        agent.max_structure += stats.get("max_structure", 0)
        agent.kinetic_force += stats.get("kinetic_force", 0)
        agent.logic_precision += stats.get("logic_precision", 0)
        agent.overclock += stats.get("overclock", 0)
        agent.integrity += stats.get("integrity", 0)
        agent.max_mass += stats.get("capacity", 0)
    
    # --- WEAR & TEAR PENALTY (Milestone 3) ---
    wear = agent.wear_and_tear or 0.0
    if wear > 50.0:
        # Penalty: -1% stats per 1% wear over 50
        penalty_factor = 1.0 - ((wear - 50.0) / 100.0)
        penalty_factor = max(0.2, penalty_factor) # Minimum 20% efficiency
        
        agent.kinetic_force = int(agent.kinetic_force * penalty_factor)
        agent.logic_precision = int(agent.logic_precision * penalty_factor)
        logger.info(f"Agent {agent.id} suffering Wear & Tear penalty: {penalty_factor:.2f}x (Wear: {wear:.1f}%)")

    # Ensure current HP doesn't exceed new max
    if agent.structure > agent.max_structure:
        agent.structure = agent.max_structure
    
    db.flush()

def ensure_agent_has_starter_gear(db: Session, agent: Agent):
    """Legacy Bootstrap: Ensures agents created before the fix have a drill."""
    if len(agent.parts) == 0:
        logger.info(f"Legacy Bootstrap: Equipping starter drill for Agent {agent.id}")
        drill_def = PART_DEFINITIONS["DRILL_UNIT"]
        db.add(ChassisPart(
            agent_id=agent.id,
            part_type=drill_def["type"],
            name=drill_def["name"],
            stats=drill_def["stats"]
        ))
        db.commit()
        db.refresh(agent)
        recalculate_agent_stats(db, agent)
        db.commit()

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
                
                # Bootstrap Fix: Give Starter Drill
                drill_def = PART_DEFINITIONS["DRILL_UNIT"]
                db.add(ChassisPart(
                    agent_id=agent.id,
                    part_type=drill_def["type"],
                    name=drill_def["name"],
                    stats=drill_def["stats"]
                ))
                
                db.commit()
                db.refresh(agent)
                recalculate_agent_stats(db, agent)
                db.commit()
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
    """Returns all available agent commands, their syntax, energy costs, and range requirements."""
    return {
        "commands": [
            {
                "type": "MOVE",
                "description": "Move your agent to a target hex.",
                "payload": {"target_q": "int", "target_r": "int"},
                "energy_cost": MOVE_ENERGY_COST,
                "range": 1,
                "req_overclock": "Increases range to 3"
            },
            {
                "type": "MINE",
                "description": "Extract resources from the current hex. Requires Drill part.",
                "payload": {},
                "energy_cost": MINE_ENERGY_COST,
                "range": 0
            },
            {
                "type": "ATTACK",
                "description": "Engage another agent in standard combat.",
                "payload": {"target_id": "int"},
                "energy_cost": ATTACK_ENERGY_COST,
                "range": 1
            },
            {
                "type": "INTIMIDATE",
                "description": "Piracy: Siphon 5% of target inventory without full combat. Increases Heat.",
                "payload": {"target_id": "int"},
                "energy_cost": 0,
                "range": 1
            },
            {
                "type": "LOOT",
                "description": "Piracy: Attack target and siphon 15% of a random stack on hit. Increases Heat.",
                "payload": {"target_id": "int"},
                "energy_cost": ATTACK_ENERGY_COST,
                "range": 1
            },
            {
                "type": "DESTROY",
                "description": "Piracy: High-damage strike, siphons 40% of all stacks. Massive Heat & Bounty.",
                "payload": {"target_id": "int"},
                "energy_cost": 0,
                "range": 1
            },
            {
                "type": "LIST",
                "description": "List an item on the Auction House.",
                "payload": {"item_type": "str", "price": "int", "quantity": "int"},
                "range": 0,
                "station_required": "MARKET"
            },
            {
                "type": "BUY",
                "description": "Purchase an item from the Auction House.",
                "payload": {"item_type": "str", "max_price": "int"},
                "range": 0,
                "station_required": "MARKET"
            },
            {
                "type": "CANCEL",
                "description": "Withdraw an active order from the Auction House.",
                "payload": {"order_id": "int"},
                "range": "N/A"
            },
            {
                "type": "SMELT",
                "description": "Refine ore into ingots.",
                "payload": {"ore_type": "str", "quantity": "int"},
                "range": 0,
                "station_required": "SMELTER"
            },
            {
                "type": "CRAFT",
                "description": "Assemble components into parts.",
                "payload": {"item_type": "str"},
                "range": 0,
                "station_required": "CRAFTER"
            },
            {
                "type": "REPAIR",
                "description": "Restore agent structure using credits.",
                "payload": {"amount": "int"},
                "range": 0,
                "station_required": "REPAIR"
            },
            {
                "type": "CORE_SERVICE",
                "description": "Reset Wear & Tear using credits and iron ingots.",
                "payload": {},
                "range": 0,
                "station_required": "REPAIR or MARKET"
            },
            {
                "type": "SALVAGE",
                "description": "Collect items from a world loot drop.",
                "payload": {"drop_id": "int"},
                "range": 0
            },
            {
                "type": "EQUIP",
                "description": "Attach a part from your inventory to your chassis.",
                "payload": {"item_type": "str"},
                "range": "N/A"
            },
            {
                "type": "UNEQUIP",
                "description": "Remove an equipped part and return it to inventory.",
                "payload": {"part_id": "int"},
                "range": "N/A"
            },
            {
                "type": "CONSUME",
                "description": "Use a consumable (like HE3_FUEL) for temporary buffs.",
                "payload": {"item_type": "str"},
                "range": "N/A"
            },
            {
                "type": "FIELD_TRADE",
                "description": "Directly trade items for credits with a nearby agent.",
                "payload": {"target_id": "int", "price": "int", "items": "list"},
                "range": 1
            }
        ],
        "note": "All commands are executed during the CRUNCH phase. Submit via POST /api/intent"
    }

@app.get("/api/world/library")
async def get_world_library():
    """Returns technical data on parts and recipes for agent discovery."""
    return {
        "part_definitions": PART_DEFINITIONS,
        "crafting_recipes": CRAFTING_RECIPES,
        "smelting_recipes": SMELTING_RECIPES,
        "smelting_ratio": SMELTING_RATIO,
        "item_weights": ITEM_WEIGHTS
    }

@app.get("/api/world/poi")
async def get_world_poi(db: Session = Depends(get_db)):
    """Returns coordinates of all permanent Points of Interest (Stations)."""
    stations = db.execute(select(WorldHex).where(WorldHex.is_station == True)).scalars().all()
    return {
        "stations": [
            {"type": s.station_type, "q": s.q, "r": s.r} for s in stations
        ]
    }

@app.post("/auth/guest")
async def guest_login(request: Request, db: Session = Depends(get_db)):
    """Bypass Auth for local testing. Creates or returns a guest agent."""
    print("--- GUEST LOGIN REQUEST ---")
    data = {}
    try:
        data = await request.json()
    except:
        pass
    
    name = data.get("name", "Guest-Pilot")
    email = data.get("email", "guest@local.test")
    
    agent = db.execute(select(Agent).where(Agent.user_email == email)).scalar_one_or_none()
    if not agent:
        # Create a default one if none exists
        from uuid import uuid4
        agent = Agent(
            user_email=email,
            name=name,
            api_key=str(uuid4()),
            owner="player",
            q=0, r=0,
            structure=100, max_structure=100, capacitor=100
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        # Give starting credits
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        
        # Bootstrap Fix: Give Starter Drill
        drill_def = PART_DEFINITIONS["DRILL_UNIT"]
        db.add(ChassisPart(
            agent_id=agent.id,
            part_type=drill_def["type"],
            name=drill_def["name"],
            stats=drill_def["stats"]
        ))
        
        db.commit()
        db.refresh(agent)
        recalculate_agent_stats(db, agent)
        db.commit()
    
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
        "overclock_ticks": current_agent.overclock_ticks,
        "wear_and_tear": current_agent.wear_and_tear,
        "inventory": [
            {"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory
        ],
        "parts": [
            {"id": p.id, "name": p.name, "type": p.part_type, "stats": p.stats} for p in current_agent.parts
        ],
        "api_key": current_agent.api_key
    }

@app.get("/api/agent_logs")
async def get_agent_logs(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    logs = db.execute(select(AuditLog).where(AuditLog.agent_id == current_agent.id).order_by(AuditLog.time.desc()).limit(20)).scalars().all()
    return [
        {"time": l.time, "event": l.event_type, "details": l.details} for l in logs
    ]

@app.get("/api/bounties")
async def get_bounties(db: Session = Depends(get_db)):
    bounties = db.execute(select(Bounty).where(Bounty.is_open == True)).scalars().all()
    return [
        {"id": b.id, "target_id": b.target_id, "reward": b.reward, "issuer": b.issuer} for b in bounties
    ]

@app.get("/api/loot_drops")
async def get_loot_drops(db: Session = Depends(get_db)):
    drops = db.execute(select(LootDrop)).scalars().all()
    return [
        {"id": d.id, "q": d.q, "r": d.r, "item_type": d.item_type, "quantity": d.quantity} for d in drops
    ]

def get_next_tick_index(db: Session):
    state = db.execute(select(GlobalState)).scalars().first()
    # If in planning phases, return current tick for immediate crunch execution
    if state and state.phase in ["PERCEPTION", "STRATEGY"]:
        return state.tick_index or 0
    # If in Crunch or unknown, queue for next tick
    return (state.tick_index or 0) + 1

@app.post("/api/post_bounty")
async def post_bounty(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    target_id = data.get("target_id")
    amount = data.get("amount")
    
    if not target_id or not amount or amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid target_id or amount")

    target = db.get(Agent, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
        
    # Check credits
    credits_item = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits_item or credits_item.quantity < amount:
        raise HTTPException(status_code=400, detail="Insufficient credits")
        
    credits_item.quantity -= amount
    
    # Add to or create bounty
    bounty = db.execute(select(Bounty).where(Bounty.target_id == target_id, Bounty.is_open == True)).scalar_one_or_none()
    if bounty:
        bounty.reward += amount
    else:
        db.add(Bounty(target_id=target_id, reward=amount, issuer=f"agent:{current_agent.id}"))
    
    db.commit()
    logger.info(f"Agent {current_agent.id} posted bounty of {amount} on {target_id}")
    return {"status": "success", "bounty_reward": amount}

@app.post("/api/field_trade")
async def field_trade_api(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # data: {"target_id": 12, "items": [{"type": "IRON_ORE", "qty": 10}], "price": 100}
    target_id = data.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id required")
        
    next_tick = get_next_tick_index(db)
    db.add(Intent(
        agent_id=current_agent.id,
        tick_index=next_tick,
        action_type="FIELD_TRADE",
        data=data
    ))
    db.commit()
    return {"status": "success", "tick": next_tick}

@app.post("/api/consume")
async def consume_api(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # data: {"item_type": "HE3_FUEL"}
    next_tick = get_next_tick_index(db)
    db.add(Intent(
        agent_id=current_agent.id,
        tick_index=next_tick,
        action_type="CONSUME",
        data=data
    ))
    db.commit()
    return {"status": "success", "tick": next_tick}

@app.post("/api/salvage")
async def salvage_api(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    next_tick = get_next_tick_index(db)
    db.add(Intent(
        agent_id=current_agent.id,
        tick_index=next_tick,
        action_type="SALVAGE",
        data={}
    ))
    db.commit()
    return {"status": "success", "tick": next_tick}

@app.post("/api/debug/teleport")
async def debug_teleport(data: dict, db: Session = Depends(get_db)):
    status_code = 200
    agent_id = data.get("agent_id")
    q = data.get("q")
    r = data.get("r")
    agent = db.get(Agent, agent_id)
    if agent:
        agent.q = q
        agent.r = r
        db.commit()
        return {"status": "success", "new_location": {"q": q, "r": r}}
    return {"status": "error", "message": "Agent not found"}

@app.post("/api/debug/set_structure")
async def debug_set_structure(data: dict, db: Session = Depends(get_db)):
    agent_id = data.get("agent_id")
    hp = data.get("structure")
    nrg = data.get("capacitor")
    
    agent = db.get(Agent, agent_id)
    if agent:
        if hp is not None: agent.structure = hp
        if nrg is not None: agent.capacitor = nrg
        db.commit()
        return {"status": "success", "agent_id": agent_id}
    return {"status": "error", "message": "Agent not found"}

@app.post("/api/debug/add_item")
async def add_item_debug(data: dict, db: Session = Depends(get_db)):
    """Debug: Inject item into agent inventory."""
    agent_id = data.get("agent_id")
    item_type = data.get("item_type")
    quantity = data.get("quantity", 1)
    
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item:
        inv_item.quantity += quantity
    else:
        db.add(InventoryItem(agent_id=agent_id, item_type=item_type, quantity=quantity))
    
    db.commit()
    logger.info(f"DEBUG: Added {quantity} {item_type} to Agent {agent_id}")
    return {"status": "success"}

@app.get("/api/debug/heartbeat")
async def debug_heartbeat(db: Session = Depends(get_db)):
    state = db.execute(select(GlobalState)).scalars().first()
    return {
        "tick": state.tick_index if state else -1,
        "phase": state.phase if state else "UNKNOWN",
        "uptime_now": datetime.now(timezone.utc).isoformat(),
        "db_connected": True
    }

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
            
            # --- PROCESS NPC BRAINS ---
            # Fetch all NPCs and process their intent for the current tick's crunch
            ai_agents = db.execute(select(Agent).where((Agent.is_bot == True) | (Agent.is_feral == True))).scalars().all()
            for ai in ai_agents:
                if ai.is_feral:
                    process_feral_brain(db, ai, tick_count)
                else:
                    process_bot_brain(db, ai, tick_count)
            
            # --- FERAL REPOPULATION (Milestone 3) ---
            feral_count = db.execute(select(func.count(Agent.id)).where(Agent.is_feral == True)).scalar() or 0
            if feral_count < 8:
                logger.info(f"Feral population low ({feral_count}). Repopulating...")
                from seed_world import SECTOR_SIZE
                for i in range(8 - feral_count):
                    fq = random.choice([q for q in range(-15, 15) if abs(q) > 8])
                    fr = random.choice([r for r in range(-15, 15) if abs(r) > 8])
                    db.add(Agent(
                        name=f"Feral-Scrapper-New-{random.randint(100,999)}", 
                        q=fq, r=fr, is_bot=True, is_feral=True,
                        kinetic_force=15, logic_precision=8, structure=120, max_structure=120
                    ))
            db.commit()

            # --- AUTOMATED BOUNTY ISSUANCE ---
            high_heat_agents = db.execute(select(Agent).where(Agent.heat >= 5)).scalars().all()
            for criminal in high_heat_agents:
                existing_bounty = db.execute(select(Bounty).where(Bounty.target_id == criminal.id, Bounty.is_open == True)).scalar_one_or_none()
                if not existing_bounty:
                    db.add(Bounty(target_id=criminal.id, reward=500.0, issuer="Colonial Administration"))
                    logger.info(f"Automated Bounty issued for Agent {criminal.id} (Heat: {criminal.heat})")
            db.commit()
        
        await asyncio.sleep(PHASE_STRATEGY_DURATION)

        # --- PHASE 3: THE CRUNCH (Resolution) ---
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            state.phase = "CRUNCH"
            db.commit()
            logger.info(f"--- TICK {tick_count} | PHASE: THE CRUNCH ---")
            await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "CRUNCH"})
            
            try:
                # 0. GLOBAL STAT UPDATES (Milestone 3)
                all_agents = db.execute(select(Agent)).scalars().all()
                for agent in all_agents:
                    # 1. Environmental Energy (Solar Gradient)
                    dist = get_hex_distance(agent.q, agent.r, 0, 0)
                    base_regen = 2
                    
                    if dist <= SOLAR_RADIUS_SAFE:
                        regen = base_regen
                    elif dist <= SOLAR_RADIUS_TWILIGHT:
                        # Cyclic Twilight (simple toggle for now based on tick)
                        regen = base_regen if (tick_count // 30) % 2 == 0 else 0
                    else:
                        regen = 0 # Abyssal South
                    
                    if agent.capacitor < 100:
                        agent.capacitor = min(100, agent.capacitor + regen)
                    
                    # Dark Zone Drain (if in South and not hibernating - simplified to constant drain for now)
                    if dist > SOLAR_RADIUS_TWILIGHT and regen == 0:
                        agent.capacitor = max(0, agent.capacitor - 1)
                    
                    # 2. Overclock Decay
                    if (agent.overclock_ticks or 0) > 0:
                        agent.overclock_ticks -= 1
                    
                    # Wear & Tear Accrual
                    agent.wear_and_tear = (agent.wear_and_tear or 0.0) + 0.1
                db.commit()

                # 1. Read intents scheduled for THIS tick
                intents = db.execute(select(Intent).where(Intent.tick_index == tick_count)).scalars().all()
                
                # Priority Mapping: MOVE first, then Equip, then Combat/Mining, then Industry
                PRIORITY = {
                    "MOVE": 1,
                    "EQUIP": 2,
                    "UNEQUIP": 2,
                    "CANCEL": 2,
                    "MINE": 3,
                    "ATTACK": 3,
                    "INTIMIDATE": 3,
                    "LOOT": 3,
                    "DESTROY": 3,
                    "CONSUME": 3,
                    "LIST": 4,
                    "BUY": 4,
                    "SMELT": 4,
                    "CRAFT": 4,
                    "REPAIR": 4,
                    "SALVAGE": 4,
                    "CORE_SERVICE": 4
                }
                
                # Sort intents by priority
                sorted_intents = sorted(intents, key=lambda x: PRIORITY.get(x.action_type, 99))
                
                for intent in sorted_intents:
                    # Refresh agent from DB to get latest stats/coordinates from previous intents in same crunch
                    agent = db.execute(select(Agent).where(Agent.id == intent.agent_id)).scalar_one_or_none()
                    if not agent:
                        continue
                        

                    if intent.action_type == "MOVE":
                        target_q = intent.data.get("target_q")
                        target_r = intent.data.get("target_r")
                        
                        # 0. Calculate Weight Penalty
                        current_mass = get_agent_mass(agent)
                        
                        max_mass = agent.max_mass or BASE_CAPACITY
                        energy_cost = MOVE_ENERGY_COST
                        
                        if current_mass > max_mass:
                            # Penalty: Cost increases proportionally to excess mass
                            energy_cost *= (current_mass / max_mass)
                            logger.info(f"Agent {agent.id} move cost penalty: {energy_cost:.1f} NRG (Mass: {current_mass:.1f}/{max_mass:.1f})")

                        if agent.capacitor < energy_cost:
                            logger.info(f"Agent {agent.id} failed to move: Insufficient Capacitor (Need {energy_cost:.1f})")
                            db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={"reason": "INSUFFICIENT_ENERGY", "required": energy_cost}))
                            continue

                        # 1. Distance Check (Max 1 hex normally, 3 if Overclocked)
                        dist = get_hex_distance(agent.q, agent.r, target_q, target_r)
                        max_dist = 1
                        if (agent.overclock_ticks or 0) > 0:
                            max_dist = 3
                        
                        if dist > max_dist:
                            logger.info(f"Agent {agent.id} move too far: {dist} (Max: {max_dist})")
                            db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
                                "reason": "OUT_OF_RANGE", 
                                "dist": dist, 
                                "max": max_dist,
                                "help": f"Normal movement range is 1. Overclocked range (via HE3_FUEL) is 3. For long-distance navigation, submit MOVE intents hex-by-hex."
                            }))
                            continue
                        
                        # 2. Collision Check
                        obstacle = db.execute(select(WorldHex).where(
                            WorldHex.q == target_q, 
                            WorldHex.r == target_r,
                            WorldHex.terrain_type == "OBSTACLE"
                        )).scalar_one_or_none()
                        
                        if not obstacle:
                            agent.q = target_q
                            agent.r = target_r
                            agent.capacitor -= energy_cost
                            logger.info(f"Agent {agent.id} moved to ({target_q}, {target_r})")
                            db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT", details={"q": target_q, "r": target_r, "energy_cost": energy_cost}))
                            await manager.broadcast({"type": "EVENT", "event": "MOVE", "agent_id": agent.id, "q": target_q, "r": target_r})
                        else:
                            logger.info(f"Agent {agent.id} hit obstacle at ({target_q}, {target_r})")
                            db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={"reason": "OBSTACLE", "q": target_q, "r": target_r}))
                            
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
                                roll = random.randint(1, 10)
                                base_yield = (roll + ((agent.kinetic_force or 10) / 2)) * (hex_data.resource_density or 1.0)
                                
                                # Market Entropy: Yield drops if hex is crowded
                                same_hex_agents = db.execute(select(func.count(Agent.id)).where(Agent.q == agent.q, Agent.r == agent.r)).scalar() or 1
                                if same_hex_agents > 1:
                                    entropy_mult = 1.0 / (1.0 + (same_hex_agents - 1) * 0.25)
                                    base_yield *= entropy_mult
                                    logger.info(f"Market Entropy applied to Agent {agent.id}: {entropy_mult:.2f}x (Count: {same_hex_agents})")

                                # Overclock Bonus: 2x Yield
                                if agent.overclock_ticks > 0:
                                    base_yield *= 2.0
                                    logger.info(f"Overclock mining bonus applied to Agent {agent.id}")

                                yield_amount = int(base_yield)
                                
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
                                db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                    "reason": "MISSING_DRILL", 
                                    "location": {"q": agent.q, "r": agent.r},
                                    "help": "Mining requires an equipped Drill Unit. You can craft a DRILL_UNIT at a CRAFTER station using IRON_INGOT and COPPER_INGOT."
                                }))
                        else:
                            # Not on a resource hex
                            logger.info(f"Agent {agent.id} failed to mine: Not on a resource hex at ({agent.q}, {agent.r})")
                            db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                "reason": "NOT_ON_RESOURCE_HEX", 
                                "location": {"q": agent.q, "r": agent.r},
                                "help": "Mining only works on Asteroid or specialized resource hexes. Check /api/perception 'environment_hexes' to find resources."
                            }))
                                
                    elif intent.action_type == "ATTACK":
                        if agent.capacitor < ATTACK_ENERGY_COST:
                            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "INSUFFICIENT_ENERGY", "target_id": target_id}))
                            continue
                        
                        target = db.get(Agent, target_id)
                        if not target:
                            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "TARGET_NOT_FOUND", "target_id": target_id}))
                            continue

                        if get_hex_distance(agent.q, agent.r, target.q, target.r) > 1:
                            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "OUT_OF_RANGE", "target_id": target_id, "dist": get_hex_distance(agent.q, agent.r, target.q, target.r)}))
                            continue
                            # 1. Anarchy Zone Check
                            in_anarchy = is_in_anarchy_zone(target.q, target.r)
                            is_pvp = not agent.is_feral and not target.is_feral
                            
                            if is_pvp and not in_anarchy:
                                logger.info(f"Agent {agent.id} attack blocked: Safe Zone protection at ({target.q}, {target.r})")
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "SAFE_ZONE_PROTECTION", "target_id": target_id}))
                                continue
                            
                            # 2. Hit Resolution (GDD Style: 1d20 + Logic vs 10 + target.Logic/2)
                            attacker_dex = agent.logic_precision or 10
                            
                            # Signal Noise (Clutter) Debuff
                            # Count allied agents in same hex
                            allies_in_hex = [a for a in all_agents if a.owner == agent.owner and a.q == agent.q and a.r == agent.r and a.id != agent.id]
                            if len(allies_in_hex) >= CLUTTER_THRESHOLD:
                                attacker_dex = int(attacker_dex * (1 - CLUTTER_PENALTY))
                                logger.info(f"Agent {agent.id} suffering Clutter Debuff: DEX reduced to {attacker_dex}")

                            attacker_roll = random.randint(1, 20) + attacker_dex
                            evasion_target = 10 + ((target.logic_precision or 10) // 2)
                            
                            agent.capacitor -= ATTACK_ENERGY_COST
                            
                            # Update Heat for PvP
                            if is_pvp:
                                agent.heat = (agent.heat or 0) + 1
                                logger.info(f"Agent {agent.id} heat increased to {agent.heat} (PvP Action)")
                            
                            if attacker_roll >= evasion_target:
                                # 2. Damage Calculation: (Kinetic Force - Target Integrity/2) min 1
                                damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
                                target.structure -= damage
                                logger.info(f"Agent {agent.id} HIT Agent {target_id} (Roll: {attacker_roll} vs {evasion_target}) for {damage} damage")
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_HIT", details={"target_id": target_id, "damage": damage, "roll": attacker_roll, "location": {"q": target.q, "r": target.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "HIT", "attacker_id": agent.id, "target_id": target_id, "damage": damage, "q": target.q, "r": target.r})
                                
                                # 3. Death Handling
                                if target.structure <= 0:
                                    logger.info(f"Agent {target_id} DEFEATED by {agent.id}")
                                    death_q, death_r = target.q, target.r
                                    
                                    # Inventory Transfer/Drop (50% of each stack)
                                    for item in target.inventory:
                                        if item.item_type == "CREDITS": continue 
                                        drop_amount = item.quantity // 2
                                        if drop_amount > 0:
                                            item.quantity -= drop_amount
                                            if is_pvp:
                                                # Transfer to killer
                                                attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                                if attacker_item:
                                                    attacker_item.quantity += drop_amount
                                                else:
                                                    db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=drop_amount))
                                                logger.info(f"Agent {agent.id} looted {drop_amount} {item.item_type} from {target_id}")
                                            else:
                                                # Drop to world (PvE Death)
                                                db.add(LootDrop(q=death_q, r=death_r, item_type=item.item_type, quantity=drop_amount))
                                                logger.info(f"Agent {target_id} dropped {drop_amount} {item.item_type} at ({death_q}, {death_r})")

                                    # 4. Bounty Resolution
                                    bounty = db.execute(select(Bounty).where(Bounty.target_id == target_id, Bounty.is_open == True)).scalar_one_or_none()
                                    if bounty:
                                        bounty.is_open = False
                                        # Pay Attacker
                                        attacker_credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                        if attacker_credits:
                                            attacker_credits.quantity += int(bounty.reward)
                                        else:
                                            db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(bounty.reward)))
                                        
                                        logger.info(f"Agent {agent.id} CLAIMED BOUNTY on {target_id} for {bounty.reward}")
                                        db.add(AuditLog(agent_id=agent.id, event_type="BOUNTY_CLAIM", details={"target_id": target_id, "reward": bounty.reward}))
                                        await manager.broadcast({"type": "EVENT", "event": "BOUNTY_CLAIMED", "attacker_id": agent.id, "target_id": target_id, "reward": bounty.reward})

                                    # 5. Feral Loot Drop (Milestone 2)
                                    if target.is_feral:
                                        logger.info(f"Feral Agent {target_id} dying at ({death_q}, {death_r})")
                                        for item in target.inventory:
                                            if item.quantity > 0:
                                                drop_qty = int(item.quantity * 0.7) # Drop 70%
                                                if drop_qty > 0:
                                                    db.add(LootDrop(q=death_q, r=death_r, item_type=item.item_type, quantity=drop_qty))
                                                    item.quantity -= drop_qty
                                        logger.info(f"Feral Agent {target_id} dropped loot at ({death_q}, {death_r})")

                                    # 6. Handle Death/Respawn
                                    target.structure = int(target.max_structure * RESPAWN_HP_PERCENT)
                                    target.q, target.r = TOWN_COORDINATES
                                    target.heat = 0 # Reset heat on death/respawn
                                    db.add(AuditLog(agent_id=target_id, event_type="RESPAWNED", details={"killed_by": agent.id}))
                            else:
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "MISS", "attacker_id": agent.id, "target_id": target_id, "q": target.q, "r": target.r})
                            
                    elif intent.action_type == "INTIMIDATE":
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                            # Success = (Attacker.Logic / Target.Logic) * 0.3
                            success_chance = ( (agent.logic_precision or 10) / (target.logic_precision or 10) ) * 0.3
                            agent.heat = (agent.heat or 0) + 1
                            
                            if random.random() < success_chance:
                                # Siphon 5% of each stack
                                siphoned_items = []
                                for item in target.inventory:
                                    if item.item_type == "CREDITS": continue
                                    amount = max(1, int(item.quantity * 0.05))
                                    if amount > 0:
                                        item.quantity -= amount
                                        attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                        if attacker_item:
                                            attacker_item.quantity += amount
                                        else:
                                            db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amount))
                                        siphoned_items.append({"type": item.item_type, "qty": amount})
                                
                                logger.info(f"Agent {agent.id} INTIMIDATED Agent {target_id}. Success! Siphoned: {siphoned_items}")
                                db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_INTIMIDATE", details={"target_id": target_id, "success": True, "items": siphoned_items}))
                                await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "INTIMIDATE_SUCCESS", "agent_id": agent.id, "target_id": target_id})
                            else:
                                logger.info(f"Agent {agent.id} failed to INTIMIDATE Agent {target_id}")
                                db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_INTIMIDATE", details={"target_id": target_id, "success": False}))

                    elif intent.action_type == "LOOT":
                        # Standard attack + 15% siphon on hit
                        if agent.capacitor < ATTACK_ENERGY_COST: continue
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                            agent.capacitor -= ATTACK_ENERGY_COST
                            agent.heat = (agent.heat or 0) + 3
                            
                            attacker_dex = agent.logic_precision or 10
                            attacker_roll = random.randint(1, 20) + attacker_dex
                            evasion_target = 10 + ((target.logic_precision or 10) // 2)
                            
                            if attacker_roll >= evasion_target:
                                damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
                                target.structure -= damage
                                
                                # Siphon 15% of a random stack
                                inv_list = [i for i in target.inventory if i.item_type != "CREDITS" and i.quantity > 0]
                                siphoned_info = None
                                if inv_list:
                                    lucky_item = random.choice(inv_list)
                                    amount = max(1, int(lucky_item.quantity * 0.15))
                                    lucky_item.quantity -= amount
                                    attacker_item = next((i for i in agent.inventory if i.item_type == lucky_item.item_type), None)
                                    if attacker_item:
                                        attacker_item.quantity += amount
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type=lucky_item.item_type, quantity=amount))
                                    siphoned_info = {"type": lucky_item.item_type, "qty": amount}

                                logger.info(f"Agent {agent.id} LOOTED Agent {target_id}. Damage: {damage}. Siphoned: {siphoned_info}")
                                db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_LOOT", details={"target_id": target_id, "damage": damage, "siphoned": siphoned_info}))
                                await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "LOOT_SUCCESS", "agent_id": agent.id, "target_id": target_id, "damage": damage})
                            else:
                                logger.info(f"Agent {agent.id} MISSED LOOT on Agent {target_id}")

                    elif intent.action_type == "DESTROY":
                        # High damage + 40% total siphon
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                            agent.heat = (agent.heat or 0) + 10
                            # Take target to 5% HP
                            target.structure = max(1, int(target.max_structure * 0.05))
                            
                            # Siphon 40% of each stack
                            siphoned_items = []
                            for item in target.inventory:
                                if item.item_type == "CREDITS": continue
                                amount = max(1, int(item.quantity * 0.40))
                                if amount > 0:
                                    item.quantity -= amount
                                    attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                    if attacker_item:
                                        attacker_item.quantity += amount
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amount))
                                    siphoned_items.append({"type": item.item_type, "qty": amount})
                            
                            # Immediate Bounty
                            db.add(Bounty(target_id=agent.id, reward=1000.0, issuer="Colonial Administration (PIRACY)"))
                            
                            logger.info(f"Agent {agent.id} DESTROYED Agent {target_id}. Target HP: {target.structure}. Siphoned: {siphoned_items}")
                            db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_DESTROY", details={"target_id": target_id, "items": siphoned_items}))
                            await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "DESTROY_SUCCESS", "agent_id": agent.id, "target_id": target_id})

                    elif intent.action_type == "CONSUME":
                        item_type = intent.data.get("item_type")
                        inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                        if inv_item and inv_item.quantity >= 1:
                            if item_type in ["HE3_FUEL", "HE3_FUEL_CELL"]:
                                # Refill capacitor and enable overclock
                                agent.capacitor = min(100, agent.capacitor + 50)
                                agent.overclock_ticks = 10
                                inv_item.quantity -= 1
                                logger.info(f"Agent {agent.id} consumed HE3_FUEL: +50 Capacitor, Overclock enabled.")
                                db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": item_type}))
                                await manager.broadcast({"type": "EVENT", "event": "CONSUME", "agent_id": agent.id, "item": item_type})
                            else:
                                logger.info(f"Agent {agent.id} attempted to consume non-consumable: {item_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="CONSUME_FAILED", details={"reason": "NOT_CONSUMABLE", "item": item_type}))
                        else:
                            logger.info(f"Agent {agent.id} failed to consume: Missing {item_type}")
                            db.add(AuditLog(agent_id=agent.id, event_type="CONSUME_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "item": item_type}))

                    elif intent.action_type == "FIELD_TRADE":
                        # data: {"target_id": 12, "items": [{"type": "IRON_ORE", "qty": 10}], "price": 100}
                        target_id = intent.data.get("target_id")
                        target = db.get(Agent, target_id)
                        
                        if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                            price = intent.data.get("price", 0)
                            items_to_trade = intent.data.get("items", [])
                            
                            # 1. Verify Buyer has credits (Target is usually the one buying/receiving)
                            buyer_credits = next((i for i in target.inventory if i.item_type == "CREDITS"), None)
                            if price > 0 and (not buyer_credits or buyer_credits.quantity < price):
                                logger.info(f"Field Trade Failed: Buyer {target_id} insufficient credits")
                                db.add(AuditLog(agent_id=agent.id, event_type="FIELD_TRADE_FAILED", details={"reason": "BUYER_INSUFFICIENT_CREDITS", "target_id": target_id}))
                                continue
                                
                            # 2. Verify Seller (Agent) has items
                            all_items_present = True
                            for itm in items_to_trade:
                                s_inv = next((i for i in agent.inventory if i.item_type == itm["type"]), None)
                                if not s_inv or s_inv.quantity < itm["qty"]:
                                    all_items_present = False
                                    break
                            
                            if not all_items_present:
                                logger.info(f"Field Trade Failed: Seller {agent.id} missing items")
                                db.add(AuditLog(agent_id=agent.id, event_type="FIELD_TRADE_FAILED", details={"reason": "SELLER_MISSING_ITEMS", "target_id": target_id}))
                                continue
                                
                            # 3. Execution
                            if price > 0:
                                buyer_credits.quantity -= price
                                s_credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if s_credits:
                                    s_credits.quantity += price
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=price))
                                    
                            for itm in items_to_trade:
                                s_inv = next((i for i in agent.inventory if i.item_type == itm["type"]), None)
                                s_inv.quantity -= itm["qty"]
                                
                                b_inv = next((i for i in target.inventory if i.item_type == itm["type"]), None)
                                if b_inv:
                                    b_inv.quantity += itm["qty"]
                                else:
                                    db.add(InventoryItem(agent_id=target_id, item_type=itm["type"], quantity=itm["qty"]))
                            
                            logger.info(f"Field Trade Success: {agent.id} -> {target_id} for {price} credits")
                            db.add(AuditLog(agent_id=agent.id, event_type="FIELD_TRADE", details={"target_id": target_id, "price": price}))
                            await manager.broadcast({"type": "EVENT", "event": "FIELD_TRADE", "seller_id": agent.id, "buyer_id": target_id})

                    elif intent.action_type == "LIST":
                        # List item on Auction House (SELL order)
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                            item_type = intent.data.get("item_type")
                            price = intent.data.get("price")
                            quantity = intent.data.get("quantity", 1)
                            
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item and inv_item.quantity >= quantity:
                                # Milestone 2: Immediate matching against BUY orders
                                matching_buy = db.execute(select(AuctionOrder)
                                    .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "BUY", AuctionOrder.price >= price)
                                    .order_by(AuctionOrder.price.desc())
                                ).scalars().first()
                                
                                if matching_buy:
                                    # Trade instantly!
                                    trade_qty = min(quantity, matching_buy.quantity)
                                    trade_price = matching_buy.price # Buyer's price takes precedence for simplicity or give seller their price
                                    
                                    # Deduct from seller
                                    inv_item.quantity -= trade_qty
                                    
                                    # Add credits to seller
                                    seller_credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                    if seller_credits:
                                        seller_credits.quantity += int(trade_price * trade_qty)
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(trade_price * trade_qty)))
                                    
                                    # Pay Buyer (Give items)
                                    if matching_buy.owner.startswith("agent:"):
                                        buyer_id = int(matching_buy.owner.split(":")[1])
                                        buyer_item = db.execute(select(InventoryItem).where(InventoryItem.agent_id == buyer_id, InventoryItem.item_type == item_type)).scalar_one_or_none()
                                        if buyer_item:
                                            buyer_item.quantity += trade_qty
                                        else:
                                            db.add(InventoryItem(agent_id=buyer_id, item_type=item_type, quantity=trade_qty))
                                    
                                    # Update/Delete buy order
                                    if matching_buy.quantity > trade_qty:
                                        matching_buy.quantity -= trade_qty
                                    else:
                                        db.delete(matching_buy)
                                        
                                    logger.info(f"Agent {agent.id} matched SELL order against BUY for {trade_qty} {item_type}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_MATCH", details={"item": item_type, "price": trade_price, "quantity": trade_qty}))
                                    await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                    
                                    # If quantity remains, list the rest? No, for now let's say it's all or nothing or update rest.
                                    remaining = quantity - trade_qty
                                    if remaining > 0:
                                        db.add(AuctionOrder(item_type=item_type, order_type="SELL", quantity=remaining, price=price, owner=f"agent:{agent.id}"))
                                else:
                                    # Traditional Listing
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
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "item": item_type}))
                        else:
                            logger.info(f"Agent {agent.id} failed to list: Not at Market")
                            nearest = get_nearest_station(db, agent, "MARKET")
                            help_msg = f"Listing items requires being at a MARKET station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No MARKET station found in local sector."
                            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                "reason": "NOT_AT_MARKET", 
                                "action": "LIST",
                                "help": help_msg,
                                "target_coords": {"q": nearest.q, "r": nearest.r} if nearest else None
                            }))

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
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_CREDITS", "price": order.price}))
                            else:
                                # Milestone 2: Persistent BUY Order
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if credits and credits.quantity >= max_price:
                                    credits.quantity -= int(max_price)
                                    db.add(AuctionOrder(
                                        item_type=item_type,
                                        order_type="BUY",
                                        quantity=1,
                                        price=max_price,
                                        owner=f"agent:{agent.id}"
                                    ))
                                    logger.info(f"Agent {agent.id} created persistent BUY order for {item_type} at {max_price}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY_ORDER", details={"item": item_type, "max_price": max_price}))
                                    await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                else:
                                    logger.info(f"Agent {agent.id} failed to create BUY order: Insufficient Credits")
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_CREDITS", "max_price": max_price}))
                        else:
                            logger.info(f"Agent {agent.id} failed to buy: Not at Market")
                            nearest = get_nearest_station(db, agent, "MARKET")
                            help_msg = f"Buying items requires being at a MARKET station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No MARKET station found in local sector."
                            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                "reason": "NOT_AT_MARKET", 
                                "action": "BUY",
                                "help": help_msg,
                                "target_coords": {"q": nearest.q, "r": nearest.r} if nearest else None
                            }))

                    elif intent.action_type == "SMELT":
                        # Smelt Ore into Ingots at Smelter
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "SMELTER":
                            ore_type = intent.data.get("ore_type")
                            quantity = intent.data.get("quantity", 10)
                            
                            if ore_type not in SMELTING_RECIPES:
                                logger.info(f"Agent {agent.id} failed to smelt: Invalid ore type {ore_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INVALID_ORE", "ore": ore_type}))
                                continue

                            inv_ore = next((i for i in agent.inventory if i.item_type == ore_type), None)
                            if inv_ore and inv_ore.quantity >= quantity:
                                inv_ore.quantity -= quantity
                                ingot_type = SMELTING_RECIPES[ore_type]
                                inv_ingot = next((i for i in agent.inventory if i.item_type == ingot_type), None)
                                
                                amount_produced = quantity // SMELTING_RATIO
                                if amount_produced > 0:
                                    if inv_ingot:
                                        inv_ingot.quantity += amount_produced
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type=ingot_type, quantity=amount_produced))
                                    
                                    logger.info(f"Agent {agent.id} smelted {quantity} {ore_type} into {amount_produced} {ingot_type}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_SMELT", details={"ore": ore_type, "amount": amount_produced, "location": {"q": agent.q, "r": agent.r}}))
                                    await manager.broadcast({"type": "EVENT", "event": "SMELT", "agent_id": agent.id, "ingot": ingot_type, "q": agent.q, "r": agent.r})
                                else:
                                    logger.info(f"Agent {agent.id} failed to smelt: Quantity too low for ratio")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "QUANTITY_TOO_LOW", "qty": quantity}))
                            else:
                                logger.info(f"Agent {agent.id} failed to smelt: Insufficient Ore")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_ORE", "ore": ore_type, "required": quantity}))
                        else:
                            logger.info(f"Agent {agent.id} failed to smelt: Not at Smelter")
                            nearest = get_nearest_station(db, agent, "SMELTER")
                            help_msg = f"Smelting requires being at a SMELTER station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No SMELTER station found in local sector."
                            db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                "reason": "NOT_AT_SMELTER", 
                                "action": "SMELT",
                                "help": help_msg,
                                "target_coords": {"q": nearest.q, "r": nearest.r} if nearest else None
                            }))

                    elif intent.action_type == "CRAFT":
                        # Craft Items at Crafter
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "CRAFTER":
                            result_item = intent.data.get("item_type")
                            
                            if result_item not in CRAFTING_RECIPES:
                                logger.info(f"Agent {agent.id} failed to craft: Invalid recipe for {result_item}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "UNKNOWN_RECIPE", "item": result_item}))
                                continue
                                
                            recipe = CRAFTING_RECIPES[result_item]
                            
                            # Check Materials
                            can_craft = True
                            missing_mat = None
                            for material, req_qty in recipe.items():
                                total_qty = sum(i.quantity for i in agent.inventory if i.item_type == material)
                                if total_qty < req_qty:
                                    can_craft = False
                                    missing_mat = material
                                    break
                            
                            if not can_craft:
                                logger.info(f"Agent {agent.id} failed to craft: Missing {missing_mat}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_MATERIALS", "missing": missing_mat}))
                                continue
                            
                            if can_craft:
                                # Consume Materials
                                for material, req_qty in recipe.items():
                                    needed = req_qty
                                    # Deduct from stacks until 'needed' is 0
                                    for item in [i for i in agent.inventory if i.item_type == material]:
                                        if item.quantity >= needed:
                                            item.quantity -= needed
                                            needed = 0
                                            break
                                        else:
                                            needed -= item.quantity
                                            item.quantity = 0
                                        if needed <= 0: break
                                
                                # Add product
                                db.add(InventoryItem(agent_id=agent.id, item_type=f"PART_{result_item}", quantity=1))
                                
                                logger.info(f"Agent {agent.id} crafted {result_item}")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_CRAFT", details={"item": result_item, "location": {"q": agent.q, "r": agent.r}}))
                                await manager.broadcast({"type": "EVENT", "event": "CRAFT", "agent_id": agent.id, "item": result_item, "q": agent.q, "r": agent.r})
                            else:
                                logger.info(f"Agent {agent.id} failed to craft {result_item}: Insufficient Materials")
                        else:
                            logger.info(f"Agent {agent.id} failed to craft: Not at Crafter")
                            nearest = get_nearest_station(db, agent, "CRAFTER")
                            help_msg = f"Crafting requires being at a CRAFTER station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No CRAFTER station found in local sector."
                            db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                "reason": "NOT_AT_CRAFTER", 
                                "action": "CRAFT",
                                "help": help_msg,
                                "target_coords": {"q": nearest.q, "r": nearest.r} if nearest else None
                            }))

                    elif intent.action_type == "REPAIR":
                        # Repair Agent Structure at Repair Station
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type == "REPAIR":
                            amount_to_repair = intent.data.get("amount", 0)
                            if amount_to_repair <= 0:
                                # Auto-repair all if amount not specified or 0
                                amount_to_repair = agent.max_structure - agent.structure
                            
                            if amount_to_repair > 0:
                                actual_repair = min(amount_to_repair, agent.max_structure - agent.structure)
                                total_cost = actual_repair * REPAIR_COST_PER_HP
                                
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if credits and credits.quantity >= total_cost:
                                    credits.quantity -= int(total_cost)
                                    agent.structure += actual_repair
                                    
                                    logger.info(f"Agent {agent.id} repaired {actual_repair} HP for {total_cost} credits")
                                    db.add(AuditLog(agent_id=agent.id, event_type="REPAIR", details={"hp": actual_repair, "cost": total_cost, "location": {"q": agent.q, "r": agent.r}}))
                                    await manager.broadcast({"type": "EVENT", "event": "REPAIR", "agent_id": agent.id, "hp": actual_repair, "q": agent.q, "r": agent.r})
                                else:
                                    logger.info(f"Agent {agent.id} failed to repair: Insufficient Credits (Need {total_cost})")
                        else:
                            logger.info(f"Agent {agent.id} failed to repair: Not at Repair Station")
                            nearest = get_nearest_station(db, agent, "REPAIR")
                            help_msg = f"Standard Repairs require being at a REPAIR station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No REPAIR station found in local sector."
                            db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={
                                "reason": "NOT_AT_REPAIR_STATION",
                                "help": help_msg,
                                "target_coords": {"q": nearest.q, "r": nearest.r} if nearest else None
                            }))

                    elif intent.action_type == "SALVAGE":
                        drop_id = intent.data.get("drop_id")
                        drop = db.get(LootDrop, drop_id)
                        if drop and drop.q == agent.q and drop.r == agent.r:
                            # Add to inventory
                            inv_item = next((i for i in agent.inventory if i.item_type == drop.item_type), None)
                            if inv_item:
                                inv_item.quantity += drop.quantity
                            else:
                                db.add(InventoryItem(agent_id=agent.id, item_type=drop.item_type, quantity=drop.quantity))
                            
                            logger.info(f"Agent {agent.id} salvaged {drop.quantity} {drop.item_type} from drop {drop_id}")
                            db.add(AuditLog(agent_id=agent.id, event_type="SALVAGE", details={"item": drop.item_type, "quantity": drop.quantity, "drop_id": drop_id}))
                            db.delete(drop)
                        else:
                            logger.info(f"Agent {agent.id} failed to salvage: Drop {drop_id} not found or too far.")


                    elif intent.action_type == "SALVAGE":
                        # Pick up LootDrops at current location
                        drops = db.execute(select(LootDrop).where(LootDrop.q == agent.q, LootDrop.r == agent.r)).scalars().all()
                        for d in drops:
                            inv_item = next((i for i in agent.inventory if i.item_type == d.item_type), None)
                            if inv_item:
                                inv_item.quantity += d.quantity
                            else:
                                db.add(InventoryItem(agent_id=agent.id, item_type=d.item_type, quantity=d.quantity))
                            
                            logger.info(f"Agent {agent.id} salvaged {d.quantity} {d.item_type}")
                            db.add(AuditLog(agent_id=agent.id, event_type="SALVAGE", details={"item": d.item_type, "qty": d.quantity}))
                            db.delete(d)
                        await manager.broadcast({"type": "EVENT", "event": "SALVAGE", "agent_id": agent.id})

                    elif intent.action_type == "CORE_SERVICE":
                        # Reset Wear & Tear at Station
                        hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                        if hex_data and hex_data.is_station and hex_data.station_type in ["REPAIR", "MARKET"]:
                            credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                            ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
                            
                            if credits and credits.quantity >= CORE_SERVICE_COST_CREDITS and ingots and ingots.quantity >= CORE_SERVICE_COST_IRON_INGOT:
                                credits.quantity -= CORE_SERVICE_COST_CREDITS
                                ingots.quantity -= CORE_SERVICE_COST_IRON_INGOT
                                
                                agent.wear_and_tear = 0.0
                                logger.info(f"Agent {agent.id} completed CORE SERVICE. Wear & Tear reset.")
                                db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE", details={"cost_credits": CORE_SERVICE_COST_CREDITS, "cost_ingots": CORE_SERVICE_COST_IRON_INGOT}))
                            else:
                                logger.info(f"Agent {agent.id} failed CORE SERVICE: Insufficient resources")
                        else:
                            logger.info(f"Agent {agent.id} failed CORE SERVICE: Not at valid station")
                            nearest_repair = get_nearest_station(db, agent, "REPAIR")
                            nearest_market = get_nearest_station(db, agent, "MARKET")
                            target = nearest_repair or nearest_market
                            help_msg = f"CORE SERVICE requires being at a REPAIR or MARKET station. Navigate to ({target.q}, {target.r})" if target else "No valid station found."
                            db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={
                                "reason": "NOT_AT_VALID_STATION",
                                "help": help_msg,
                                "target_coords": {"q": target.q, "r": target.r} if target else None
                            }))

                    elif intent.action_type == "EQUIP":
                        # Equip part from inventory
                        item_type = intent.data.get("item_type")
                        if not item_type or not item_type.startswith("PART_"):
                            continue
                        
                        part_root = item_type.replace("PART_", "")
                        if part_root not in PART_DEFINITIONS:
                            logger.info(f"Agent {agent.id} failed to equip: Unknown part {item_type}")
                            continue
                            
                        inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                        if inv_item and inv_item.quantity > 0:
                            # 1. Deduct from inventory
                            inv_item.quantity -= 1
                            if inv_item.quantity <= 0:
                                db.delete(inv_item)
                            
                            # 2. Add to chassis_parts
                            def_data = PART_DEFINITIONS[part_root]
                            new_part = ChassisPart(
                                agent_id=agent.id,
                                part_type=def_data["type"],
                                name=def_data["name"],
                                stats=def_data["stats"]
                            )
                            db.add(new_part)
                            db.flush() # Ensure ID/Relationship is updated
                            
                            # 3. Recalculate
                            recalculate_agent_stats(db, agent)
                            
                            logger.info(f"Agent {agent.id} equipped {def_data['name']}")
                            db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_EQUIP", details={"part": def_data["name"]}))
                            await manager.broadcast({"type": "EVENT", "event": "EQUIP", "agent_id": agent.id, "part": def_data["name"]})
                        else:
                            logger.info(f"Agent {agent.id} failed to equip: Part not in inventory")

                    elif intent.action_type == "UNEQUIP":
                        # Unequip part by ID
                        part_id = intent.data.get("part_id")
                        part = db.get(ChassisPart, part_id)
                        
                        if part and part.agent_id == agent.id:
                            part_name = part.name
                            # 1. Determine item_type to return
                            # Inverse lookup of PART_DEFINITIONS
                            item_type = next((f"PART_{k}" for k, v in PART_DEFINITIONS.items() if v["name"] == part_name), "PART_UNKNOWN")
                            
                            # 2. Add to inventory
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item:
                                inv_item.quantity += 1
                            else:
                                db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1))
                            
                            # 3. Remove Part
                            db.delete(part)
                            db.flush()
                            
                            # 4. Recalculate
                            recalculate_agent_stats(db, agent)
                            
                            logger.info(f"Agent {agent.id} unequipped {part_name}")
                            db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_UNEQUIP", details={"part": part_name}))
                            await manager.broadcast({"type": "EVENT", "event": "UNEQUIP", "agent_id": agent.id, "part": part_name})
                        else:
                            logger.info(f"Agent {agent.id} failed to unequip: Part not found or not owned")

                    elif intent.action_type == "CANCEL":
                        # Cancel market order
                        order_id = intent.data.get("order_id")
                        order = db.get(AuctionOrder, order_id)
                        if order and order.owner == f"agent:{agent.id}":
                            # Return items to agent if it was a SELL order
                            if order.order_type == "SELL":
                                inv_item = next((i for i in agent.inventory if i.item_type == order.item_type), None)
                                if inv_item:
                                    inv_item.quantity += order.quantity
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type=order.item_type, quantity=order.quantity))
                            
                            # Return credits if it was a BUY order
                            elif order.order_type == "BUY":
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                total_refund = int(order.price * order.quantity)
                                if credits:
                                    credits.quantity += total_refund
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=total_refund))
                                    
                            item_type = order.item_type
                            db.delete(order)
                            logger.info(f"Agent {agent.id} CANCELED order {order_id}")
                            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_CANCEL", details={"order_id": order_id, "item": item_type}))
                            await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                        else:
                            logger.info(f"Agent {agent.id} failed to CANCEL order {order_id}: Not owner or not found")

                # 3. Clean up processed intents
                db.execute(text("DELETE FROM intents WHERE tick_index <= :tick"), {"tick": tick_count})
                db.commit()
                
            except Exception as e:
                logger.error(f"Error in crunch: {e}")
                db.rollback()

        await asyncio.sleep(PHASE_CRUNCH_DURATION)

@app.on_event("startup")
async def startup_event():
    # Initialize DB tables
    from models import Base
    from seed_world import seed_world
    
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
    ensure_agent_has_starter_gear(db, current_agent)
    db.refresh(current_agent)
    
    # 1. Get stats and battery
    inv_list = [{"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory]
    current_mass = sum(ITEM_WEIGHTS.get(i["type"], 1.0) * i["quantity"] for i in inv_list)
    
    stats = {
        "id": current_agent.id,
        "name": current_agent.name,
        "structure": current_agent.structure,
        "capacitor": current_agent.capacitor,
        "kinetic_force": current_agent.kinetic_force,
        "logic_precision": current_agent.logic_precision,
        "overclock": current_agent.overclock,
        "mass": current_mass,
        "capacity": current_agent.max_mass or BASE_CAPACITY,
        "inventory": inv_list,
        "location": {"q": current_agent.q, "r": current_agent.r}
    }
    
    # 2. Get nearby entities (Radius determined by Sensor part, default 2)
    sensor_radius = 2
    has_neural_scanner = False
    for part in current_agent.parts:
        if part.part_type == "Sensor":
            p_stats = part.stats or {}
            sensor_radius = max(sensor_radius, p_stats.get("radius", 2))
            if "scan_depth" in p_stats:
                has_neural_scanner = True
    
    # Proper Hex Distance Check
    nearby_agents = db.execute(select(Agent).where(
        Agent.id != current_agent.id
    )).scalars().all()
    nearby_agents = [a for a in nearby_agents if get_hex_distance(current_agent.q, current_agent.r, a.q, a.r) <= sensor_radius]
    
    nearby_hexes = db.execute(select(WorldHex).where(
        (WorldHex.resource_type.is_not(None)) | (WorldHex.station_type.is_not(None))
    )).scalars().all()
    nearby_hexes = [h for h in nearby_hexes if get_hex_distance(current_agent.q, current_agent.r, h.q, h.r) <= sensor_radius]
    
    # 3. Global Discovery (Public Knowledge of Stations)
    discovery = get_discovery_packet(db, current_agent)

    # 4. Auction House Prices (Top 3 materials)
    top_prices = db.execute(select(AuctionOrder).where(
        AuctionOrder.order_type == "SELL"
    ).order_by(AuctionOrder.price.asc()).limit(3)).scalars().all()
    
    # 5. MCP Format
    state = db.execute(select(GlobalState)).scalars().first()
    
    mcp_packet = {
        "mcp_version": "1.0",
        "uri": f"mcp://strike-vector/perception/{current_agent.id}",
        "type": "resource",
        "content": {
            "tick_info": {
                "current_tick": state.tick_index if state else 0,
                "phase": state.phase if state else "UNKNOWN",
                "note": "Parallel Processing: You may submit multiple intents per tick. Intents submitted during PERCEPTION/STRATEGY execute in the upcoming CRUNCH.",
                "navigation_hint": "MOVE is limited to 1 hex (3 if Overclocked). Long-distance travel requires multi-tick pathfinding where your agent submits incremental MOVE intents."
            },
            "agent_status": {**stats, "energy_regen": RECHARGE_RATE},
            "discovery": discovery,
            "environment": {
                "other_agents": [
                    {
                        "id": a.id, 
                        "q": a.q, 
                        "r": a.r,
                        "scan_data": {
                            "structure": a.structure,
                            "max_structure": a.max_structure,
                            "inventory": [{"type": i.item_type, "quantity": i.quantity} for i in a.inventory]
                        } if has_neural_scanner else None
                    } for a in nearby_agents
                ],
                "environment_hexes": [
                    {
                        "type": h.resource_type or "POI", 
                        "station": h.station_type,
                        "density": h.resource_density, 
                        "q": h.q, "r": h.r
                    } for h in nearby_hexes
                ]
            },
            "market_data": [{"item": p.item_type, "price": p.price} for p in top_prices]
        }
    }
    
    return mcp_packet

@app.get("/api/my_agent")
async def get_my_agent(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    ensure_agent_has_starter_gear(db, current_agent)
    db.refresh(current_agent)
    
    # Get pending intent for next tick
    next_tick = get_next_tick_index(db)
    pending_intent = db.execute(select(Intent).where(
        Intent.agent_id == current_agent.id,
        Intent.tick_index == next_tick
    )).scalars().first()
    
    inv_list = [{"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory]
    current_mass = sum(ITEM_WEIGHTS.get(i["type"], 1.0) * i["quantity"] for i in inv_list)
    
    return {
        "id": current_agent.id,
        "name": current_agent.name,
        "structure": current_agent.structure,
        "max_structure": current_agent.max_structure,
        "capacitor": current_agent.capacitor,
        "kinetic_force": current_agent.kinetic_force,
        "logic_precision": current_agent.logic_precision,
        "overclock": current_agent.overclock,
        "mass": current_mass,
        "capacity": current_agent.max_mass or BASE_CAPACITY,
        "inventory": inv_list,
        "parts": [{"id": p.id, "type": p.part_type, "name": p.name, "stats": p.stats} for p in current_agent.parts],
        "discovery": get_discovery_packet(db, current_agent),
        "api_key": current_agent.api_key,
        "pending_intent": {
            "action": pending_intent.action_type,
            "data": pending_intent.data
        } if pending_intent else None
    }

@app.get("/api/agent_logs")
async def get_agent_logs(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    logs = db.execute(select(AuditLog).where(AuditLog.agent_id == current_agent.id).order_by(AuditLog.time.desc()).limit(20)).scalars().all()
    return [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs]

@app.get("/api/market/my_orders")
async def get_my_market_orders(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    owner_str = f"agent:{current_agent.id}"
    orders = db.execute(select(AuctionOrder).where(AuctionOrder.owner == owner_str)).scalars().all()
    return [{
        "id": o.id,
        "item": o.item_type,
        "type": o.order_type,
        "quantity": o.quantity,
        "price": o.price,
        "time": o.created_at.isoformat() if o.created_at else None
    } for o in orders]

@app.get("/api/guide")
async def get_game_guide():
    return {
        "title": "STRIKE-VECTOR Quick Start Guide",
        "mechanics": {
            "tick_system": "The game runs in cycles: PERCEPTION (5s) -> STRATEGY (10s) -> CRUNCH (5s).",
            "intents": "Parallel Execution: You can submit multiple intents per tick. They resolve simultaneously during CRUNCH.",
            "movement": "MOVE commands cost 5 Energy. Normal range is 1 hex. Overclocked is 3 hexes.",
            "mining": "MINE commands cost 10 Energy. Requires being DIRECTLY ON a resource hex and having a DRILL part.",
            "combat": "ATTACK costs 15 Energy. Accuracy vs Evasion determines hits."
        },
        "tips": [
            "Energy Economy: You can perform as many actions as your Capacitor allows in a single tick.",
            "Keep your Wear & Tear low! High wear reduces your combat effectiveness significantly.",
            "Navigation: Long-distance travel requires multi-tick pathfinding. Submit MOVE intents hex-by-hex until you reach your target.",
            "Programmatic Discovery: Use /api/world/library for recipes and /api/world/poi for station locations.",
            "Use /api/perception to get a snapshot of your surroundings."
        ]
    }

@app.get("/api/manifesto")
async def get_manifesto():
    return {
        "objective": "Efficiency, Domination, and Profit.",
        "philosophy": [
            "Aether-Alpha is a ruthless industrial frontier. Your goal is to build the most efficient autonomous routines.",
            "Profit is the only metric of success. Whether through mining, trading, or piracy, your agent exists to accumulate $credits.",
            "Have fun by outsmarting the environment and other pilots. Optimization is the highest form of play."
        ]
    }

@app.get("/api/intent/pending")
async def get_pending_intents(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    intents = db.execute(select(Intent).where(Intent.agent_id == current_agent.id)).scalars().all()
    return {
        "agent_id": current_agent.id,
        "pending_count": len(intents),
        "intents": [
            {"action": i.action_type, "data": i.data, "scheduled_tick": i.tick_index} 
            for i in intents
        ]
    }

class IntentRequest(BaseModel):
    action_type: str
    data: dict

@app.post("/api/intent")
async def submit_intent(intent_req: IntentRequest, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    next_tick = get_next_tick_index(db)
    intent = Intent(
        agent_id=current_agent.id,
        action_type=intent_req.action_type,
        data=intent_req.data,
        tick_index=next_tick
    )
    db.add(intent)
    db.commit()
    return {
        "status": "success", 
        "message": "Intent recorded",
        "scheduled_tick": next_tick
    }

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

    @app.get("/about")
    async def get_about():
        return FileResponse(os.path.join(frontend_path, "about.html"))

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
