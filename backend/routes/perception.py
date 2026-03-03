from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import WorldHex, Agent, GlobalState, LootDrop
from database import get_db, STATION_CACHE
from game_helpers import get_hex_distance, get_discovery_packet
from routes.common import verify_api_key

router = APIRouter(prefix="/api", tags=["Perception"])

@router.get("/perception")
async def get_perception(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns local sensor data: NPCs, Resources, Stations, and Loot nearby."""
    state = db.execute(select(GlobalState)).scalars().first()
    
    # Sensor Radius (Logic Stat influenced)
    sensor_range = 5 + (agent.logic_precision // 10)
    
    # 1. Nearby Agents
    visible_agents = db.execute(select(Agent).where(
        Agent.q >= agent.q - sensor_range, Agent.q <= agent.q + sensor_range,
        Agent.r >= agent.r - sensor_range, Agent.r <= agent.r + sensor_range
    )).scalars().all()
    
    # 2. Nearby Resources & Stations (Cached/Discovery)
    discovery = get_discovery_packet(STATION_CACHE, agent)
    
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
        "nearby_agents": [{"id": a.id, "name": a.name, "q": a.q, "r": a.r, "faction": a.faction_id} for a in visible_agents if a.id != agent.id],
        "discovery": discovery,
        "loot": [{"item": l.item_type, "qty": l.quantity} for l in loot]
    }

@router.get("/map")
async def get_map_data(q: int = Query(...), r: int = Query(...), radius: int = Query(10), db: Session = Depends(get_db)):
    """Returns static world hex data for a specific region."""
    hexes = db.execute(select(WorldHex).where(
        WorldHex.q >= q - radius, WorldHex.q <= q + radius,
        WorldHex.r >= r - radius, WorldHex.r <= r + radius
    )).scalars().all()
    
    return [{"q": h.q, "r": h.r, "terrain": h.terrain_type, "station": h.station_type} for h in hexes]
