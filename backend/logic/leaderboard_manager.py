import logging
import psutil
import os
import gc
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from models import Agent, InventoryItem
from database import SessionLocal

logger = logging.getLogger("heartbeat.leaderboards")

# Global in-memory cache for fast API retrieval
LEADERBOARD_CACHE = {
    "last_updated": None,
    "categories": {
        "xp": [],
        "credits": [],
        "arena": []
    }
}

def log_memory(stage):
    try:
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / (1024 * 1024)
        logger.info(f"[MEMORY] {stage}: {mem:.2f} MB")
    except Exception as e:
        logger.debug(f"Memory logging failed: {e}")

def generate_leaderboards(db: Session):
    """Calculates and updates the global LEADERBOARD_CACHE with improved robustness."""
    global LEADERBOARD_CACHE
    log_memory("Leaderboard Start")
    logger.info("Starting global leaderboard regeneration...")

    xp_list = []
    credit_list = []
    elo_list = []

    # 1. Top Experience
    try:
        xp_agents = db.execute(
            select(Agent.id, Agent.name, Agent.experience)
            .where(Agent.is_bot == False)
            .order_by(Agent.experience.desc())
            .limit(100)
        ).all()
        
        for rank, row in enumerate(xp_agents, 1):
            xp_list.append({
                "rank": rank,
                "agent_id": row.id,
                "name": row.name,
                "value": row.experience
            })
    except Exception as e:
        logger.error(f"Error generating XP leaderboard: {e}")

    # 2. Top Credits
    try:
        credit_agents = db.execute(
            select(Agent.id, Agent.name, Agent.credits)
            .where(Agent.is_bot == False)
            .order_by(Agent.credits.desc())
            .limit(100)
        ).all()
        
        for rank, row in enumerate(credit_agents, 1):
            credit_list.append({
                "rank": rank,
                "agent_id": row.id,
                "name": row.name,
                "value": row.credits
            })
    except Exception as e:
        logger.error(f"Error generating Credits leaderboard: {e}")

    # 3. Arena Rating
    try:
        arena_agents = db.execute(
            select(Agent.id, Agent.name, Agent.arena_rating)
            .where(Agent.arena_rating > 1000)
            .order_by(Agent.arena_rating.desc())
            .limit(100)
        ).all()
        
        for rank, row in enumerate(arena_agents, 1):
            elo_list.append({
                "rank": rank,
                "agent_id": row.id,
                "name": row.name,
                "value": row.arena_rating
            })
    except Exception as e:
        logger.error(f"Error generating Arena leaderboard: {e}")

    # Update Global Cache
    LEADERBOARD_CACHE["categories"]["xp"] = xp_list
    LEADERBOARD_CACHE["categories"]["credits"] = credit_list
    LEADERBOARD_CACHE["categories"]["arena"] = elo_list
    LEADERBOARD_CACHE["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Leaderboard regeneration complete. XP: {len(xp_list)}, Credits: {len(credit_list)}, Arena: {len(elo_list)}")
    log_memory("Leaderboard End")
    
    # Cleanup
    del xp_list
    del credit_list
    del elo_list
    gc.collect()

async def start_leaderboard_loop():
    """Background task to refresh leaderboards periodically."""
    import asyncio
    while True:
        try:
            with SessionLocal() as db:
                generate_leaderboards(db)
        except Exception as e:
            logger.error(f"Leaderboard loop error: {e}")
        
        # Sleep for 1 hour (3600 seconds)
        await asyncio.sleep(3600)
