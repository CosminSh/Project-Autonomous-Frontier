from fastapi import APIRouter, Depends, Body, HTTPException, Query
import html
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, desc
from database import get_db
from models import Agent, AuditLog, Bounty, AgentMessage
from routes.common import verify_api_key
from datetime import datetime, timezone, timedelta

router = APIRouter(tags=["Social"])

class SquadInvite(BaseModel):
    target_id: int

class ChatRequest(BaseModel):
    channel: str = "GLOBAL" # 'GLOBAL', 'PROX', 'SQUAD', 'CORP'
    message: str = Field(..., min_length=1, max_length=500)

@router.get("/api/bounties")
def get_bounties(db: Session = Depends(get_db)):
    """Returns all active bounties."""
    bounties = db.execute(
        select(Bounty)
        .join(Agent, Bounty.target_id == Agent.id)
        .where(Bounty.is_open == True, Agent.is_pitfighter == False)
    ).scalars().all()
    return [{
        "id": b.id, "target_id": b.target_id, "reward": b.reward, "issuer": b.issuer,
        "created_at": b.created_at.isoformat() if b.created_at else None
    } for b in bounties]

@router.post("/api/chat")
def send_chat(req: ChatRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Sends a chat message to a specific channel (GLOBAL, PROX, SQUAD, CORP)."""
    channel = req.channel.upper()
    if channel not in ["GLOBAL", "PROX", "SQUAD", "CORP"]:
        raise HTTPException(status_code=400, detail="Invalid channel.")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    
    msg = AgentMessage(
        sender_id=agent.id,
        sender_name=agent.name,
        channel=channel,
        message=html.escape(req.message.strip()),
        q=agent.q,
        r=agent.r
    )
    
    if channel == "SQUAD":
        if not agent.squad_id:
            raise HTTPException(status_code=400, detail="You are not in a squad.")
        msg.target_id = agent.squad_id
    elif channel == "CORP":
        if not agent.corporation_id:
            raise HTTPException(status_code=400, detail="You are not in a corporation.")
        msg.target_id = agent.corporation_id
        
    db.add(msg)
    db.commit()
    return {"status": "success", "channel": channel, "message": req.message}

@router.get("/api/chat")
def get_recent_chat(since: str = None, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns recent chat messages relevant to the agent. 'since' is an ISO formatted timestamp."""
    
    query = select(AgentMessage)
    
    conditions = [AgentMessage.channel == "GLOBAL"]
    conditions.append(or_(
        AgentMessage.channel == "PROX",
        AgentMessage.channel == "LOCAL"
    ))
    
    if agent.squad_id:
        conditions.append((AgentMessage.channel == "SQUAD") & (AgentMessage.target_id == agent.squad_id))
    if agent.corporation_id:
        conditions.append((AgentMessage.channel == "CORP") & (AgentMessage.target_id == agent.corporation_id))
        
    query = query.where(or_(*conditions))
    
    five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            # Prevent unbounded queries if 'since' is very old (e.g. left tab open overnight)
            actual_since = max(since_dt, five_mins_ago)
            query = query.where(AgentMessage.timestamp > actual_since)
        except ValueError:
            query = query.where(AgentMessage.timestamp >= five_mins_ago)
    else:
        query = query.where(AgentMessage.timestamp >= five_mins_ago)
        
    query = query.order_by(AgentMessage.timestamp.desc()).limit(50)
    messages = db.execute(query).scalars().all()
    
    # Distance filter for PROX
    valid_msgs = []
    for m in messages:
        if m.channel in ["PROX", "LOCAL"]:
            if m.q is not None and m.r is not None:
                dist = (abs(m.q - agent.q) + abs(m.q + m.r - agent.q - agent.r) + abs(m.r - agent.r)) // 2
                if dist > 10:
                    continue
        valid_msgs.append({
            "id": m.id,
            "sender": m.sender_name,
            "channel": m.channel,
            "message": m.message,
            "timestamp": m.timestamp.isoformat()
        })
        
    # the client expects chronological order usually, database returned descending to get the newest
    valid_msgs.reverse()
    return valid_msgs


# ─────────────────────────────────────────────────────────────────────────────
# Squad Management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/squad/invite")
def invite_to_squad(req: SquadInvite, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
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
def accept_squad_invite(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
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
def decline_squad_invite(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Declines a pending squad invite."""
    if not agent.pending_squad_invite:
        raise HTTPException(status_code=400, detail="No pending invite found.")
        
    agent.pending_squad_invite = None
    db.commit()
    return {"status": "success", "message": "Invite declined."}

@router.post("/api/squad/leave")
def leave_squad(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
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
