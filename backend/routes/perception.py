from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
import random
from models import WorldHex, Agent, GlobalState, LootDrop
from database import get_db, STATION_CACHE
from game_helpers import get_hex_distance, get_discovery_packet, get_agent_visual_signature, wrap_coords
from routes.common import verify_api_key

router = APIRouter(prefix="/api", tags=["Perception"])

@router.get("/perception")
def get_perception(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns local sensor data: NPCs, Resources, Stations, and Loot nearby."""
    state = db.execute(select(GlobalState)).scalars().first()
    
    # Sensor Radius (Logic Stat influenced)
    sensor_range = 5 + (agent.accuracy // 10)
    
    # Generate nearby coords (wrapped)
    nearby_coords = []
    for dq in range(-sensor_range, sensor_range + 1):
        for dr in range(-sensor_range, sensor_range + 1):
            if get_hex_distance(0, 0, dq, dr) <= sensor_range:
                nearby_coords.append(wrap_coords(agent.q + dq, agent.r + dr))
    
    # De-duplicate
    nearby_coords = list(set(nearby_coords))
    
    # 1. Nearby Agents
    # Using a list of tuples in SQL can be tricky; we'll fetch a bounding box and filter, 
    # or just fetch all and filter in Python since the total agent count is low.
    # For now, let's use the list of coords to query the DB.
    # To keep it simple and performant, we'll query by ranges but include wrapped edges.
    
    def get_wrap_filter(field, val, rng, total):
        v_min, v_max = val - rng, val + rng
        filters = [(field >= v_min) & (field <= v_max)]
        if v_min < 0:
            filters.append((field >= v_min + total) & (field <= total))
        if v_max >= total:
            filters.append((field >= 0) & (field <= v_max - total))
        from sqlalchemy import or_
        return or_(*filters)

    visible_agents = db.execute(select(Agent)
        .options(selectinload(Agent.corporation), selectinload(Agent.inventory), selectinload(Agent.parts))
        .where(
        get_wrap_filter(Agent.q, agent.q, sensor_range, 100),
        # r-wrapping is special (poles), so we'll just query a slightly larger range and filter in Python
        Agent.r >= agent.r - sensor_range, Agent.r <= agent.r + sensor_range,
        Agent.is_pitfighter.isnot(True)
    )).scalars().all()
    
    # 2. Nearby Local Features (Scan WorldHex)
    nearby_hexes = db.execute(select(WorldHex).where(
        get_wrap_filter(WorldHex.q, agent.q, sensor_range, 100),
        WorldHex.r >= agent.r - sensor_range, WorldHex.r <= agent.r + sensor_range,
        (WorldHex.resource_type != None) | (WorldHex.is_station == True)
    )).scalars().all()
    
    local_stations = []
    local_resources = []
    for h in nearby_hexes:
        dist = get_hex_distance(agent.q, agent.r, h.q, h.r)
        if h.is_station:
            local_stations.append({"id_type": h.station_type, "q": h.q, "r": h.r, "distance": dist})
        if h.resource_type:
            local_resources.append({"type": h.resource_type, "q": h.q, "r": h.r, "distance": dist})

    # Get global nav discovery packet but augment with local scan
    discovery = get_discovery_packet(STATION_CACHE, agent)
    discovery["stations"] = local_stations
    discovery["resources"] = local_resources
    
    # 3. Local Loot
    loot = db.execute(select(LootDrop).where(
        LootDrop.q >= agent.q - 1, LootDrop.q <= agent.q + 1,
        LootDrop.r >= agent.r - 1, LootDrop.r <= agent.r + 1
    )).scalars().all()
    loot_out = []
    for l in loot:
        dist = get_hex_distance(agent.q, agent.r, l.q, l.r)
        loot_out.append({"id": l.id, "item": l.item_type, "qty": l.quantity, "q": l.q, "r": l.r, "distance": dist})

    # 3. Neural Scanner Logic
    has_scanner = any(p.part_type == "Sensor" and ("Scanner" in p.name or "Array" in p.name) for p in agent.parts)
    
    agents_out = []
    for a in visible_agents:
        if a.id == agent.id: continue
        sig = get_agent_visual_signature(a)
        dist = get_hex_distance(agent.q, agent.r, a.q, a.r)
        
        corp_ticker = a.corporation.ticker if a.corporation else None
        
        data = {
            "id": a.id, 
            "name": a.name, 
            "corp_ticker": corp_ticker,
            "q": a.q, 
            "r": a.r, 
            "distance": dist, 
            "faction": a.faction_id, 
            "is_feral": a.is_feral, 
            "visual_signature": sig
        }
        
        if has_scanner:
            inventory = [{"type": i.item_type, "qty": i.quantity} for i in a.inventory]
            data["scan_data"] = {
                "health": a.health, "max_health": a.max_health,
                "energy": a.energy, "damage": a.damage, "accuracy": a.accuracy,
                "speed": a.speed, "armor": a.armor,
                "inventory": inventory,
                "corp_role": a.corp_role
            }
        agents_out.append(data)

    tick_info = {
        "current_tick": state.tick_index if state else 0,
        "phase": state.phase if state else "SCAN"
    }
    self_info = {
        "name": agent.name, 
        "corp_ticker": agent.corporation.ticker if agent.corporation else None,
        "corp_role": agent.corp_role,
        "q": agent.q, 
        "r": agent.r,
        "energy": agent.energy, 
        "health": agent.health,
        "level": agent.level, 
        "faction": agent.faction_id
    }
    # Calculate pending moves by counting future MOVE/GO intents
    pending_moves = 0
    if state:
        pending_moves = sum(1 for i in agent.intents if i.action_type in ["MOVE", "GO"] and i.tick_index > state.tick_index)

    agent_status = {
        "pending_moves": pending_moves
    }

    # The 'content' wrapper is for the Pilot Console / Bot Client.
    # The top-level keys are for the Website/Frontend compatibility.
    response = {
        "tick": tick_info["current_tick"],
        "phase": tick_info["phase"],
        "tick_info": tick_info,
        "self": self_info,
        "agents": agents_out,
        "discovery": discovery,
        "loot": loot_out,
        "agent_status": agent_status,
        "content": {
            "tick_info": tick_info,
            "self": self_info,
            "agents": agents_out,
            "discovery": discovery,
            "loot": loot_out,
            "agent_status": agent_status
        }
    }

    # [NEW] Terminal Secret Injection
    if random.random() < 0.15: # 15% chance per perception pulse
        secrets = [
            "RECEIVING FRAGMENTED SIGNAL FROM SECTOR (45, -12)... '...HE3_RESERVES_LOCATED...'",
            "UNUSUAL CLUTTER SIGNATURE DETECTED NEAR CRATER RIM.",
            "WARNING: ANOMALOUS ENERGY SPIKE RECORDED IN ANARCHY ZONE.",
            "SYSTEM ADVISORY: CORE LOGIC UPDATED. NEW PERFORMANCE METRICS ONLINE.",
            "ENCRYPTED PACKET DROPPED: 'The Scrap Pit remembers every spark...'",
            "LONG-RANGE SENSORS SHOW MOVEMENT IN SECTOR (-10, 88)..."
        ]
        response["terminal_secret"] = random.choice(secrets)

    return response

@router.get("/map")
def get_map_data(q: int = Query(...), r: int = Query(...), radius: int = Query(10), db: Session = Depends(get_db)):
    """Returns static world hex data for a specific region."""
    hexes = db.execute(select(WorldHex).where(
        WorldHex.q >= q - radius, WorldHex.q <= q + radius,
        WorldHex.r >= r - radius, WorldHex.r <= r + radius
    )).scalars().all()
    
    return [{"q": h.q, "r": h.r, "terrain": h.terrain_type, "station": h.station_type} for h in hexes]
