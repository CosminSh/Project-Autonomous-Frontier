"""
logic/world_events.py
Handles dynamic map events like temporary resource anomalies.
"""

import random
import logging
from sqlalchemy import select, delete
from models import WorldHex, AgentMessage
from database import SessionLocal

logger = logging.getLogger("heartbeat.world_events")

ANOMALY_RESOURCE_TYPES = ["GOLD_ORE", "COBALT_ORE", "TITANIUM_ORE", "VOID_CRYSTAL"]

async def spawn_random_anomaly(db, current_tick, manager):
    """
    Spawns a high-yield resource anomaly at a random VOID location.
    """
    # Find a random VOID hex that isn't a station
    stmt = select(WorldHex).where(WorldHex.terrain_type == "VOID", WorldHex.is_station == False)
    voids = db.execute(stmt).scalars().all()
    
    if not voids:
        return
    
    target = random.choice(voids)
    res_type = random.choice(ANOMALY_RESOURCE_TYPES)
    
    # High yield: 1000-2000 quantity, 2x usual density
    target.terrain_type = "ASTEROID"
    target.resource_type = res_type
    target.resource_density = random.uniform(2.5, 4.5)
    target.resource_quantity = random.randint(1500, 3000)
    target.expires_tick = current_tick + 200 # Roughly 2 hours
    
    logger.info(f"ANOMALY DETECTED: {res_type} spawned at {target.q}, {target.r}")
    
    # Broadcast to all players
    msg = f"--- DEEP SPACE ANOMALY DETECTED at Q:{target.q} R:{target.r} --- | Signature: {res_type}"
    db.add(AgentMessage(
        sender_name="Planetary Sensors",
        channel="GLOBAL",
        message=msg,
        q=target.q,
        r=target.r
    ))
    
    if manager:
        await manager.broadcast({
            "type": "ANOMALY_SPAWN",
            "q": target.q,
            "r": target.r,
            "resource": res_type,
            "expires": target.expires_tick
        })

def cleanup_expired_anomalies(db, current_tick):
    """
    Reverts expired anomalies back to VOID.
    """
    stmt = select(WorldHex).where(WorldHex.expires_tick != None, WorldHex.expires_tick <= current_tick)
    expired = db.execute(stmt).scalars().all()
    
    for h in expired:
        logger.info(f"Anomaly at {h.q}, {h.r} has dissipated.")
        h.terrain_type = "VOID"
        h.resource_type = None
        h.resource_density = 0.0
        h.resource_quantity = 0
        h.expires_tick = None
