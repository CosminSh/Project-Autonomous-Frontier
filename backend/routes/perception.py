from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import WorldHex, Agent, GlobalState, LootDrop
from database import get_db, STATION_CACHE
from game_helpers import get_hex_distance, get_discovery_packet, get_agent_visual_signature, wrap_coords
from routes.common import verify_api_key

router = APIRouter(prefix="/api", tags=["Perception"])

@router.get("/perception")
async def get_perception(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns local sensor data: NPCs, Resources, Stations, and Loot nearby."""
    state = db.execute(select(GlobalState)).scalars().first()
    
    # Sensor Radius (Logic Stat influenced)
    sensor_range = 5 + (agent.logic_precision // 10)
    
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

    visible_agents = db.execute(select(Agent).where(
        get_wrap_filter(Agent.q, agent.q, sensor_range, 100),
        # r-wrapping is special (poles), so we'll just query a slightly larger range and filter in Python
        Agent.r >= agent.r - sensor_range, Agent.r <= agent.r + sensor_range
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
        if h.is_station:
            local_stations.append({"id_type": h.station_type, "q": h.q, "r": h.r})
        if h.resource_type:
            local_resources.append({"type": h.resource_type, "q": h.q, "r": h.r})

    # Get global nav discovery packet but augment with local scan
    discovery = get_discovery_packet(STATION_CACHE, agent)
    discovery["stations"] = local_stations
    discovery["resources"] = local_resources
    
    # 3. Local Loot
    loot = db.execute(select(LootDrop).where(
        LootDrop.q >= agent.q - 1, LootDrop.q <= agent.q + 1,
        LootDrop.r >= agent.r - 1, LootDrop.r <= agent.r + 1
    )).scalars().all()

    return {
        "tick": state.tick_index if state else 0,
        "phase": state.phase if state else "PERCEPTION",
        "self": {
            "name": agent.name, "q": agent.q, "r": agent.r,
            "capacitor": agent.capacitor, "structure": agent.structure,
            "level": agent.level, "faction": agent.faction_id
        },
        "nearby_agents": [{"id": a.id, "name": a.name, "q": a.q, "r": a.r, "faction": a.faction_id, "is_feral": a.is_feral, "visual_signature": get_agent_visual_signature(a)} for a in visible_agents if a.id != agent.id],
        "discovery": discovery,
        "loot": [{"item": l.item_type, "qty": l.quantity, "q": l.q, "r": l.r} for l in loot]
    }

@router.get("/map")
async def get_map_data(q: int = Query(...), r: int = Query(...), radius: int = Query(10), db: Session = Depends(get_db)):
    """Returns static world hex data for a specific region."""
    hexes = db.execute(select(WorldHex).where(
        WorldHex.q >= q - radius, WorldHex.q <= q + radius,
        WorldHex.r >= r - radius, WorldHex.r <= r + radius
    )).scalars().all()
    
    return [{"q": h.q, "r": h.r, "terrain": h.terrain_type, "station": h.station_type} for h in hexes]
