from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, DailyMission, AgentMission
from sqlalchemy.sql import func
from routes.common import verify_api_key

router = APIRouter(prefix="/api/missions", tags=["Missions"])

@router.get("")
async def get_my_missions(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns all applicable missions (auto-accepted) and their progress."""
    # 1. Get truly active missions with progress
    active_agent_missions = db.execute(select(AgentMission).where(AgentMission.agent_id == agent.id)).scalars().all()
    progress_map = {am.mission_id: am for am in active_agent_missions}

    # 2. Get all missions available for this agent's level
    available_missions = db.execute(select(DailyMission).where(
        DailyMission.expires_at > func.now(),
        DailyMission.min_level <= agent.level,
        DailyMission.max_level >= agent.level
    )).scalars().all()
    
    results = []
    for m in available_missions:
        am = progress_map.get(m.id)
        results.append({
            "id": m.id,
            "type": m.mission_type,
            "target": m.target_amount,
            "progress": am.progress if am else 0,
            "is_completed": am.is_completed if am else False,
            "reward_credits": m.reward_credits,
            "item_type": m.item_type,
            "description": f"{m.mission_type.replace('_', ' ')}: {m.target_amount} {m.item_type if m.item_type else ''}"
        })
    return results

# @router.get("/available") is no longer used by the frontend as we auto-accept.
