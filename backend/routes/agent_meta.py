from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, InventoryItem, ChassisPart, AuditLog, GlobalState
from game_helpers import get_agent_mass, get_agent_visual_signature, get_discovery_packet, get_solar_intensity, get_hex_distance
from database import STATION_CACHE
from routes.common import verify_api_key
from datetime import datetime
import logging

logger = logging.getLogger("heartbeat")
router = APIRouter(tags=["Agent Meta"])

class RenameRequest(BaseModel):
    new_name: str

@router.post("/api/rename_agent")
async def rename_agent(
    req: RenameRequest,
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Updates the agent's display name."""
    new_name = req.new_name.strip()
    
    if len(new_name) < 3:
        raise HTTPException(status_code=400, detail="Name too short (min 3 chars)")
    
    # Check if name is taken
    existing = db.execute(select(Agent).where(Agent.name == new_name)).scalar_one_or_none()
    if existing and existing.id != agent.id:
        raise HTTPException(status_code=400, detail="Name already taken by another agent")
    
    old_name = agent.name
    agent.name = new_name
    
    # Log it
    db.add(AuditLog(
        agent_id=agent.id,
        event_type="IDENTITY_UPDATE",
        details={"old_name": old_name, "new_name": new_name}
    ))
    
    db.commit()
    logger.info(f"Agent {agent.id} renamed from {old_name} to {new_name}")
    return {"status": "success", "new_name": new_name}

@router.post("/api/claim_daily")
async def claim_daily_reward(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Claims the daily login bonus for the agent."""
    now = datetime.now()
    if agent.last_daily_reward and agent.last_daily_reward.date() == now.date():
        return {"error": "Already claimed today"}
    
    # Give rewards: 500 Credits and a Repair Kit
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if credits: credits.quantity += 500
    else: db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=500))
    
    db.add(InventoryItem(agent_id=agent.id, item_type="FIELD_REPAIR_KIT", quantity=1))
    agent.last_daily_reward = now
    db.commit()
    return {"status": "claimed", "rewards": ["500 Credits", "1x FIELD_REPAIR_KIT"]}

@router.get("/api/my_agent")
async def get_my_agent_legacy(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Legacy endpoint for the frontend."""
    state = db.execute(select(GlobalState)).scalars().first()
    tick = state.tick_index if state else 0
    
    squad_members = []
    if agent.squad_id:
        members = db.execute(select(Agent).where(Agent.squad_id == agent.squad_id)).scalars().all()
        squad_members = [{"id": m.id, "name": m.name, "q": m.q, "r": m.r, "health": m.health, "max_health": m.max_health} for m in members]
        
    return {
        "id": agent.id, "name": agent.name, "q": agent.q, "r": agent.r,
        "energy": agent.energy, "health": agent.health, "max_health": agent.max_health,
        "level": agent.level, "experience": agent.experience, "faction": agent.faction_id,
        "damage": agent.damage, "accuracy": agent.accuracy, "speed": agent.speed, "armor": agent.armor,
        "wear_and_tear": agent.wear_and_tear, "mass": get_agent_mass(agent), "max_mass": agent.max_mass,
        "heat": agent.heat,
        "squad_id": agent.squad_id,
        "pending_squad_invite": agent.pending_squad_invite,
        "squad_members": squad_members,
        "inventory": [{"type": i.item_type, "quantity": i.quantity, "data": i.data} for i in agent.inventory],
        "discovery": get_discovery_packet(STATION_CACHE, agent),
        "parts": [{"id": p.id, "type": p.part_type, "name": p.name, "stats": p.stats, "rarity": p.rarity} for p in agent.parts],
        "solar_intensity": int(get_solar_intensity(agent.q, agent.r, tick) * 100)
    }

@router.get("/api/agent_logs")
async def get_agent_logs(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns the activity log for the agent."""
    logs = db.execute(select(AuditLog).where(AuditLog.agent_id == agent.id).order_by(AuditLog.time.desc()).limit(50)).scalars().all()
    return [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs]

@router.get("/status")
async def get_agent_status(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns detailed status of the authenticated agent."""
    state = db.execute(select(GlobalState)).scalars().first()
    tick = state.tick_index if state else 0
    
    squad_members = []
    if agent.squad_id:
        members = db.execute(select(Agent).where(Agent.squad_id == agent.squad_id)).scalars().all()
        squad_members = [{"id": m.id, "name": m.name, "q": m.q, "r": m.r, "health": m.health, "max_health": m.max_health} for m in members]
        
    return {
        "id": agent.id, "name": agent.name, "q": agent.q, "r": agent.r,
        "energy": agent.energy, "health": agent.health, "max_health": agent.max_health,
        "level": agent.level, "experience": agent.experience, "faction": agent.faction_id,
        "wear_and_tear": agent.wear_and_tear, "mass": get_agent_mass(agent), "max_mass": agent.max_mass,
        "visual_signature": get_agent_visual_signature(agent),
        "squad_id": agent.squad_id,
        "pending_squad_invite": agent.pending_squad_invite,
        "squad_members": squad_members,
        "solar_intensity": int(get_solar_intensity(agent.q, agent.r, tick) * 100)
    }

@router.get("/inventory")
async def get_agent_inventory(agent: Agent = Depends(verify_api_key)):
    """Returns the agent's current inventory."""
    return [{"type": i.item_type, "quantity": i.quantity, "data": i.data} for i in agent.inventory]

@router.get("/gear")
async def get_agent_gear(agent: Agent = Depends(verify_api_key)):
    """Returns the agent's equipped chassis parts."""
    return [{"id": p.id, "type": p.part_type, "name": p.name, "stats": p.stats, "rarity": p.rarity} for p in agent.parts]

@router.get("/api/rescue_quote")
async def get_rescue_quote(agent: Agent = Depends(verify_api_key)):
    """Calculates the cost and ETA for a rescue to the Hub."""
    dist = get_hex_distance(agent.q, agent.r, 0, 0)
    cost = dist * 5
    eta_ticks = (dist // 10) + (1 if dist % 10 > 0 else 0)
    return {"distance": dist, "cost": cost, "eta_ticks": eta_ticks}
