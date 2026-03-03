from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, AuditLog, Bounty
from routes.common import verify_api_key

router = APIRouter(tags=["Social"])

class SquadInvite(BaseModel):
    target_id: int

@router.get("/api/bounties")
async def get_bounties(db: Session = Depends(get_db)):
    """Returns all active bounties."""
    bounties = db.execute(select(Bounty).where(Bounty.is_open == True)).scalars().all()
    return [{"id": b.id, "target": b.target_id, "reward": b.reward, "issuer": b.issuer} for b in bounties]

@router.post("/api/chat")
async def send_chat(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db), message: str = Body(...)):
    """Broadcasts a chat message to all players."""
    db.add(AuditLog(agent_id=agent.id, event_type="CHAT", details={"msg": message}))
    db.commit()
    return {"status": "broadcast_sent", "message": message}

# ─────────────────────────────────────────────────────────────────────────────
# Squad Management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/squad/invite")
async def invite_to_squad(req: SquadInvite, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Invites another agent to join the current agent's squad."""
    if req.target_id == agent.id:
        raise HTTPException(status_code=400, detail="Cannot invite yourself.")
        
    target = db.get(Agent, req.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target agent not found.")
        
    if target.squad_id:
        raise HTTPException(status_code=400, detail="Target is already in a squad.")
        
    # If the inviter is not in a squad, they start one (using their ID as the squad_id)
    if not agent.squad_id:
        agent.squad_id = agent.id
        db.add(AuditLog(agent_id=agent.id, event_type="SQUAD_CREATED", details={"squad_id": agent.squad_id}))
        
    target.pending_squad_invite = agent.squad_id
    db.add(AuditLog(agent_id=agent.id, event_type="SQUAD_INVITE_SENT", details={"target_id": target.id, "squad_id": agent.squad_id}))
    db.commit()
    
    return {"status": "success", "message": f"Invite sent to {target.name}."}

@router.post("/api/squad/accept")
async def accept_squad_invite(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Accepts a pending squad invite."""
    if not agent.pending_squad_invite:
        raise HTTPException(status_code=400, detail="No pending invite found.")
        
    old_squad = agent.pending_squad_invite
    agent.squad_id = old_squad
    agent.pending_squad_invite = None
    
    db.add(AuditLog(agent_id=agent.id, event_type="SQUAD_JOINED", details={"squad_id": old_squad}))
    db.commit()
    return {"status": "success", "message": "Joined squad."}

@router.post("/api/squad/decline")
async def decline_squad_invite(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Declines a pending squad invite."""
    if not agent.pending_squad_invite:
        raise HTTPException(status_code=400, detail="No pending invite found.")
        
    agent.pending_squad_invite = None
    db.commit()
    return {"status": "success", "message": "Invite declined."}

@router.post("/api/squad/leave")
async def leave_squad(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Leaves the current squad."""
    if not agent.squad_id:
        raise HTTPException(status_code=400, detail="You are not in a squad.")
        
    old_squad = agent.squad_id
    agent.squad_id = None
    
    # If the squad was just the agent, it disbands (implicitly)
    # Check if anyone else is left in the squad
    others = db.execute(select(Agent).where(Agent.squad_id == old_squad)).scalars().all()
    if not others:
        db.add(AuditLog(agent_id=agent.id, event_type="SQUAD_DISBANDED", details={"squad_id": old_squad}))
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="SQUAD_LEFT", details={"squad_id": old_squad}))
        
    db.commit()
    return {"status": "success", "message": "Left squad."}
