import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from models import DailyMission, AgentMission, WorldHex, AuditLog, InventoryItem
from database import STATION_CACHE
from game_helpers import get_hex_distance, add_experience

logger = logging.getLogger("heartbeat.mission_logic")

def generate_daily_missions(db):
    """Generates a fresh set of daily missions for all player tiers every 8 hours."""
    now = datetime.now(timezone.utc)
    
    # Check if there's any active mission that expires in the future
    # We use a slight overlap or a specific 'current' check.
    # To keep it simple: if there are ANY missions that expire in the future, we assume we are in an active window.
    # BUT! If the DB has missions from "yesterday" that are technically expired, we must clear them.
    
    active_count = db.execute(select(func.count(DailyMission.id)).where(DailyMission.expires_at > now)).scalar() or 0
    if active_count > 0:
        return # Missions are still fresh

    # If we reach here, it means all missions have expired.
    logger.info("Missions expired. Cleaning up old records and generating new pool...")
    
    # 1. Cleanup Old Missions (Cascade to AgentMission progress)
    from sqlalchemy import delete
    db.execute(delete(AgentMission)) # Clear everyone's progress for the new window
    db.execute(delete(DailyMission)) # Clear the old pool
    db.commit() # Flush the deletion before adding new ones

    # 2. Generate New Pool (8-hour window)
    expires = now + timedelta(hours=8)
    
    # Tier 1 (Level 1-2)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=random.randint(1, 2), reward_credits=200, min_level=1, max_level=2, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=1, reward_credits=100, min_level=1, max_level=2, expires_at=expires))
    db.add(DailyMission(mission_type="TURN_IN", target_amount=random.choice([5, 10]), item_type="IRON_ORE", reward_credits=100, min_level=1, max_level=2, expires_at=expires))
    
    # Tier 2 (Level 3-5)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=random.randint(3, 5), reward_credits=450, min_level=3, max_level=5, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=random.randint(2, 3), reward_credits=300, min_level=3, max_level=5, expires_at=expires))
    db.add(DailyMission(mission_type="TURN_IN", target_amount=random.choice([15, 20]), item_type="COPPER_ORE", reward_credits=400, min_level=3, max_level=5, expires_at=expires))
    
    # Tier 3 (Level 6+)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=random.randint(5, 10), reward_credits=800, min_level=6, max_level=99, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=random.randint(3, 5), reward_credits=500, min_level=6, max_level=99, expires_at=expires))
    db.add(DailyMission(mission_type="TURN_IN", target_amount=random.choice([20, 30]), item_type="SILVER_ORE", reward_credits=700, min_level=6, max_level=99, expires_at=expires))
    
    db.commit()
    logger.info(f"New missions generated, expiring at {expires}")

async def handle_turn_in(db, agent, intent, tick_count, manager):
    """Processes a TURN_IN intent for item-based missions."""
    mission_id = intent.data.get("mission_id")
    if not mission_id: return

    mission = db.get(DailyMission, mission_id)
    if not mission or mission.mission_type != "TURN_IN":
        return

    # Check proximity to a station (any station for now, or specific if required)
    # Most TURN_IN missions require being at a station.
    from database import STATION_CACHE
    nearest_station_dist = min([get_hex_distance(agent.q, agent.r, s["q"], s["r"]) for s in STATION_CACHE]) if STATION_CACHE else 999
    
    if nearest_station_dist > 0:
        db.add(AuditLog(agent_id=agent.id, event_type="MISSION_FAILED", details={"reason": "NOT_AT_STATION", "mission_id": mission_id}))
        return

    # Check if agent already completed it
    am = db.execute(select(AgentMission).where(AgentMission.agent_id == agent.id, AgentMission.mission_id == mission.id)).scalar_one_or_none()
    if am and am.is_completed:
        return

    # Check inventory for required items
    item_type = mission.item_type
    required_qty = mission.target_amount
    
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < required_qty:
        from models import AuditLog
        db.add(AuditLog(agent_id=agent.id, event_type="MISSION_FAILED", details={"reason": "INSUFFICIENT_ITEMS", "mission_id": mission_id}))
        return

    # Consume items
    inv_item.quantity -= required_qty
    if inv_item.quantity <= 0:
        db.delete(inv_item)

    # Mark as completed
    if not am:
        am = AgentMission(agent_id=agent.id, mission_id=mission.id, progress=required_qty, is_completed=True)
        db.add(am)
    else:
        am.progress = required_qty
        am.is_completed = True

    # Reward Credits
    cr = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if cr:
        cr.quantity += mission.reward_credits
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=mission.reward_credits))

    # Reward XP
    xp_reward = getattr(mission, "reward_xp", 100) or 100
    add_experience(db, agent, xp_reward)

    from models import AuditLog
    db.add(AuditLog(agent_id=agent.id, event_type="MISSION_COMPLETED", details={"mission_id": mission_id, "credits": mission.reward_credits, "xp": xp_reward}))
    
    if manager:
        await manager.broadcast({
            "type": "EVENT", "event": "MISSION_COMPLETED", "agent_id": agent.id, "mission_id": mission_id, "reward": mission.reward_credits
        })
