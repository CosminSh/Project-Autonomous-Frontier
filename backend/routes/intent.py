from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from database import get_db
from models import Agent, Intent
from routes.common import verify_api_key, get_next_tick_index

router = APIRouter(prefix="/api", tags=["Intent"])

@router.post("/intent")
def schedule_intent(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db), action_type: str = Body(...), data: dict = Body({})):
    """Schedules an action for the next game tick."""
    next_tick = get_next_tick_index(db)
    
    # Check for existing intent in next tick (Overwrite)
    existing = db.query(Intent).filter(Intent.agent_id == agent.id, Intent.tick_index == next_tick).first()
    if existing:
        existing.action_type = action_type
        existing.data = data
    else:
        db.add(Intent(agent_id=agent.id, tick_index=next_tick, action_type=action_type, data=data))
    
    db.commit()
    return {"status": "success", "tick": next_tick, "action": action_type}
