"""
admin.py — Protected admin endpoints.
All routes require the ADMIN_KEY header to match the env var ADMIN_KEY.
"""
import os
import logging
from fastapi import APIRouter, Header, HTTPException
from database import SessionLocal, refresh_station_cache

logger = logging.getLogger("heartbeat.admin")
router = APIRouter(prefix="/api/admin", tags=["Admin"])

ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me-in-production")


def _check_key(x_admin_key: str):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key.")


@router.post("/reseed")
async def admin_reseed(x_admin_key: str = Header(...)):
    """
    Full world re-seed: wipes all hexes, sectors, and bots.
    Teleports all real players back to the hub (0, 0).
    Regenerates the entire map with current zone rules.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    logger.info("ADMIN: Manual reseed triggered.")
    try:
        from seed_world import seed_world
        seed_world()
        refresh_station_cache()
        logger.info("ADMIN: Reseed complete.")
        return {"status": "ok", "message": "World reseed complete. Station cache refreshed."}
    except Exception as e:
        logger.error(f"ADMIN: Reseed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/teleport_all")
async def admin_teleport_all(x_admin_key: str = Header(...)):
    """
    Teleports ALL real players to the hub (0, 0) without wiping the world.
    Useful for fixing stranded players after a coordinate system change.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    from sqlalchemy import select
    from models import Agent
    with SessionLocal() as db:
        players = db.execute(select(Agent).where(Agent.is_bot == False)).scalars().all()
        for p in players:
            p.q = 0
            p.r = 0
        db.commit()
        count = len(players)
    logger.info(f"ADMIN: Teleported {count} players to (0, 0).")
    return {"status": "ok", "message": f"Teleported {count} players to (0, 0)."}


@router.post("/trigger_arena")
async def admin_trigger_arena(x_admin_key: str = Header(...)):
    """
    Manually triggers a round of Scrap Pit battles.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    logger.info("ADMIN: Manual arena battle trigger.")
    try:
        from logic.arena_manager import trigger_arena_battles
        with SessionLocal() as db:
            trigger_arena_battles(db)
        return {"status": "ok", "message": "Arena battles resolved."}
    except Exception as e:
        logger.error(f"ADMIN: Arena trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
