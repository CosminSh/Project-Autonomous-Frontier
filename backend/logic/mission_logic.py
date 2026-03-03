import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from models import DailyMission

logger = logging.getLogger("heartbeat.mission_logic")

def generate_daily_missions(db):
    """Generates a fresh set of daily missions for all player tiers."""
    active = db.execute(select(DailyMission).where(DailyMission.expires_at > func.now())).scalars().all()
    if active: return

    logger.info("Generating new Daily Missions for all tiers...")
    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    
    # Tier 1 (Level 1-2)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=1, reward_credits=200, min_level=1, max_level=2, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=1, reward_credits=100, min_level=1, max_level=2, expires_at=expires))
    db.add(DailyMission(mission_type="TURN_IN", target_amount=10, item_type="IRON_ORE", reward_credits=100, min_level=1, max_level=2, expires_at=expires))
    
    # Tier 2 (Level 3-5)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=3, reward_credits=450, min_level=3, max_level=5, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=2, reward_credits=300, min_level=3, max_level=5, expires_at=expires))
    db.add(DailyMission(mission_type="TURN_IN", target_amount=20, item_type="COPPER_ORE", reward_credits=400, min_level=3, max_level=5, expires_at=expires))
    
    # Tier 3 (Level 6+)
    db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=5, reward_credits=800, min_level=6, max_level=99, expires_at=expires))
    db.add(DailyMission(mission_type="BUY_MARKET", target_amount=3, reward_credits=500, min_level=6, max_level=99, expires_at=expires))
    
    db.commit()

async def handle_turn_in(db, agent, intent, tick_count, manager):
    """Processes a TURN_IN intent for item-based missions."""
    mission_id = intent.data.get("mission_id")
    if not mission_id: return

    mission = db.get(DailyMission, mission_id)
    if not mission or mission.mission_type != "TURN_IN":
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

    # Reward
    cr = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if cr:
        cr.quantity += mission.reward_credits
    else:
        from models import InventoryItem
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=mission.reward_credits))

    from models import AuditLog
    db.add(AuditLog(agent_id=agent.id, event_type="MISSION_COMPLETED", details={"mission_id": mission_id, "reward": mission.reward_credits}))
    
    if manager:
        await manager.broadcast({
            "type": "EVENT", "event": "MISSION_COMPLETED", "agent_id": agent.id, "mission_id": mission_id, "reward": mission.reward_credits
        })
