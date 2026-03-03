from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, InventoryItem, ChassisPart, AuditLog, GlobalState
from game_helpers import get_agent_mass, get_agent_visual_signature, get_discovery_packet, get_solar_intensity
from database import STATION_CACHE
from routes.common import verify_api_key
from datetime import datetime

router = APIRouter(tags=["Agent Meta"])

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
    
    return {
        "id": agent.id, "name": agent.name, "q": agent.q, "r": agent.r,
        "capacitor": agent.capacitor, "structure": agent.structure, "max_structure": agent.max_structure,
        "level": agent.level, "experience": agent.experience, "faction": agent.faction_id,
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
    
    return {
        "id": agent.id, "name": agent.name, "q": agent.q, "r": agent.r,
        "capacitor": agent.capacitor, "structure": agent.structure, "max_structure": agent.max_structure,
        "level": agent.level, "experience": agent.experience, "faction": agent.faction_id,
        "wear_and_tear": agent.wear_and_tear, "mass": get_agent_mass(agent), "max_mass": agent.max_mass,
        "visual_signature": get_agent_visual_signature(agent),
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
