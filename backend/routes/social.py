from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from database import get_db
from models import Agent, AuditLog, Bounty
from routes.common import verify_api_key

router = APIRouter(tags=["Social"])

@router.get("/api/bounties")
async def get_bounties(db: Session = Depends(get_db)):
    """Returns all active bounties."""
    from sqlalchemy import select
    bounties = db.execute(select(Bounty).where(Bounty.is_open == True)).scalars().all()
    return [{"id": b.id, "target": b.target_id, "reward": b.reward, "issuer": b.issuer} for b in bounties]

@router.post("/api/chat")
async def send_chat(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db), message: str = Body(...)):
    """Broadcasts a chat message to all players."""
    db.add(AuditLog(agent_id=agent.id, event_type="CHAT", details={"msg": message}))
    db.commit()
    return {"status": "broadcast_sent", "message": message}
