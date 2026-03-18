import logging
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import asyncio

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

def generate_leaderboards(db: Session):
    """Calculates and updates the global LEADERBOARD_CACHE with improved robustness."""
    global LEADERBOARD_CACHE
    logger.info("Starting global leaderboard regeneration...")

    xp_list = []
    credit_list = []
    elo_list = []

    # 1. Top Experience
    try:
        xp_agents = db.execute(
            select(Agent.id, Agent.name, Agent.experience)
            .where(Agent.is_feral == False)
            .where(Agent.is_pitfighter != True)
            .order_by(Agent.experience.desc())
            .limit(100)
        ).all()
        
        for i, row in enumerate(xp_agents):
            xp_list.append({
                "rank": i + 1,
                "agent_id": row[0],
                "name": row[1],
                "value": row[2] or 0
            })
    except Exception as e:
        logger.error(f"Error generating XP leaderboard: {e}")

    # 2. Top Credits (Sum of item_type='CREDITS' in inventory)
    try:
        credit_agents = db.execute(
            select(Agent.id, Agent.name, func.sum(InventoryItem.quantity).label('total_credits'))
            .join(InventoryItem, Agent.id == InventoryItem.agent_id)
            .where(InventoryItem.item_type == "CREDITS")
            .where(Agent.is_feral == False)
            .where(Agent.is_pitfighter != True)
            .group_by(Agent.id, Agent.name)
            .order_by(func.sum(InventoryItem.quantity).desc())
            .limit(100)
        ).all()

        for i, row in enumerate(credit_agents):
            credit_list.append({
                "rank": i + 1,
                "agent_id": row[0],
                "name": row[1],
                "value": row[2] or 0
            })
    except Exception as e:
        logger.error(f"Error generating Credits leaderboard: {e}")

    # 3. Top Arena Elo
    try:
        from models import ArenaProfile
        elo_agents = db.execute(
            select(Agent.id, Agent.name, ArenaProfile.elo, ArenaProfile.wins, ArenaProfile.losses)
            .join(ArenaProfile, Agent.id == ArenaProfile.agent_id)
            .where(Agent.is_pitfighter == True)
            .order_by(ArenaProfile.elo.desc())
            .limit(100)
        ).all()

        for i, row in enumerate(elo_agents):
            elo_list.append({
                "rank": i + 1,
                "agent_id": row[0],
                "name": row[1],
                "value": row[2] or 1200,
                "wins": row[3],
                "losses": row[4]
            })
    except Exception as e:
        logger.error(f"Error generating Arena leaderboard: {e}")

    # Update Global Cache
    try:
        LEADERBOARD_CACHE["categories"]["xp"] = xp_list
        LEADERBOARD_CACHE["categories"]["credits"] = credit_list
        LEADERBOARD_CACHE["categories"]["arena"] = elo_list
        LEADERBOARD_CACHE["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Leaderboards updated successfully. XP: {len(xp_list)}, Credits: {len(credit_list)}, Arena: {len(elo_list)}")
    except Exception as e:
        logger.error(f"Critical error updating LEADERBOARD_CACHE: {e}")

async def start_leaderboard_loop():
    """Background task to refresh leaderboards every hour."""
    logger.info("Leaderboard background loop started.")
    while True:
        try:
            # We don't want to hold a DB session open for an hour
            from database import SessionLocal
            with SessionLocal() as db:
                generate_leaderboards(db)
        except Exception as e:
            logger.error(f"Leaderboard loop error: {e}")
        
        await asyncio.sleep(3600) # Sleep 1 hour
