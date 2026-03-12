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
        "experience": [],
        "credits": [],
        "arena": []
    }
}

def generate_leaderboards(db: Session):
    """Calculates and updates the global LEADERBOARD_CACHE."""
    logger.info("Generating Leaderboards...")
    
    # 1. Top Experience
    try:
        xp_agents = db.execute(
            select(Agent.id, Agent.name, Agent.experience)
            .where((Agent.is_feral == False) & (Agent.is_pitfighter.isnot(True)))
            .order_by(Agent.experience.desc())
            .limit(100)
        ).all()
        
        xp_list = []
        for i, (aid, name, xp) in enumerate(xp_agents):
            xp_list.append({
                "rank": i + 1,
                "agent_id": aid,
                "name": name,
                "value": xp or 0
            })
    except Exception as e:
        logger.error(f"Error calculating XP leaderboard: {e}")
        xp_list = []

    # 2. Top Credits
    try:
        # Sum credits per agent
        credit_agents = db.execute(
            select(Agent.id, Agent.name, func.sum(InventoryItem.quantity).label('total_credits'))
            .join(InventoryItem, Agent.id == InventoryItem.agent_id)
            .where((InventoryItem.item_type == "CREDITS") & (Agent.is_feral == False) & (Agent.is_pitfighter.isnot(True)))
            .group_by(Agent.id, Agent.name)
            .order_by(func.sum(InventoryItem.quantity).desc())
            .limit(100)
        ).all()
        
        credit_list = []
        for i, (aid, name, credits) in enumerate(credit_agents):
            credit_list.append({
                "rank": i + 1,
                "agent_id": aid,
                "name": name,
                "value": credits or 0
            })
    except Exception as e:
        logger.error(f"Error calculating Credits leaderboard: {e}")
        credit_list = []

    # 3. Top Arena Elo
    try:
        from models import ArenaProfile
        elo_agents = db.execute(
            select(Agent.id, Agent.name, ArenaProfile.elo, ArenaProfile.wins, ArenaProfile.losses)
            .join(ArenaProfile, Agent.id == ArenaProfile.agent_id)
            .where((ArenaProfile.elo > 1200) & (Agent.is_pitfighter == True))
            .order_by(ArenaProfile.elo.desc())
            .limit(100)
        ).all()
        
        elo_list = []
        for i, (aid, name, elo, wins, losses) in enumerate(elo_agents):
            elo_list.append({
                "rank": i + 1,
                "agent_id": aid,
                "name": name,
                "value": elo or 1200,
                "wins": wins or 0,
                "losses": losses or 0
            })
    except Exception as e:
        logger.error(f"Error calculating Arena leaderboard: {e}")
        elo_list = []

    # Update Global Cache
    LEADERBOARD_CACHE["categories"]["experience"] = xp_list
    LEADERBOARD_CACHE["categories"]["credits"] = credit_list
    LEADERBOARD_CACHE["categories"]["arena"] = elo_list
    LEADERBOARD_CACHE["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Leaderboards updated. XP Leaders: {len(xp_list)}, Credit Leaders: {len(credit_list)}, Arena Leaders: {len(elo_list)}")

async def start_leaderboard_loop():
    """Background task to refresh leaderboards every hour."""
    while True:
        try:
            db = SessionLocal()
            generate_leaderboards(db)
            db.close()
        except Exception as e:
            logger.error(f"Failed to generate leaderboards in background loop: {e}")
            
        await asyncio.sleep(3600) # Sleep 1 hour
