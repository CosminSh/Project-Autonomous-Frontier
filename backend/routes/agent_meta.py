from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from database import get_db, STATION_CACHE
from models import Agent, InventoryItem, ChassisPart, AuditLog, GlobalState
from game_helpers import (
    get_agent_mass, 
    get_agent_visual_signature, 
    get_discovery_packet, 
    get_solar_intensity, 
    get_hex_distance, 
    PART_NAME_TO_WEIGHT,
    recalculate_agent_stats,
    get_wear_penalty_factor
)
from routes.common import verify_api_key
from config import ITEM_WEIGHTS, PART_DEFINITIONS
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
    # Stats are now handled exclusively by the Heartbeat once per tick to save DB IO.
    penalty = get_wear_penalty_factor(agent.wear_and_tear)
    state = db.execute(select(GlobalState)).scalars().first()
    tick = state.tick_index if state else 0
    
    squad_members = []
    if agent.squad_id:
        members = db.execute(select(Agent).where(Agent.squad_id == agent.squad_id)).scalars().all()
        squad_members = [{"id": m.id, "name": m.name, "q": m.q, "r": m.r, "health": m.health, "max_health": m.max_health} for m in members]
        
    # Aggregate inventory
    aggregated_inv = {}
    for i in agent.inventory:
        key = (i.item_type, str(i.data))
        if key in aggregated_inv:
            aggregated_inv[key]["quantity"] += i.quantity
        else:
            w = ITEM_WEIGHTS.get(i.item_type, 1.0)
            aggregated_inv[key] = {"type": i.item_type, "quantity": i.quantity, "data": i.data, "weight": w}
            
    # Aggregate storage (vault)
    aggregated_storage = {}
    for i in agent.storage:
        key = (i.item_type, str(i.data))
        if key in aggregated_storage:
            aggregated_storage[key]["quantity"] += i.quantity
        else:
            w = ITEM_WEIGHTS.get(i.item_type, 1.0)
            aggregated_storage[key] = {"type": i.item_type, "quantity": i.quantity, "data": i.data, "weight": w}
            
    # Corporation Data
    corp_data = None
    if agent.corporation_id:
        corp = agent.corporation
        if corp:
            # Aggregate Corp storage
            aggregated_corp_storage = {}
            for i in corp.storage:
                key = (i.item_type, str(i.data))
                if key in aggregated_corp_storage:
                    aggregated_corp_storage[key]["quantity"] += i.quantity
                else:
                    w = ITEM_WEIGHTS.get(i.item_type, 1.0)
                    aggregated_corp_storage[key] = {"type": i.item_type, "quantity": i.quantity, "data": i.data, "weight": w}
            
            corp_data = {
                "id": corp.id,
                "name": corp.name,
                "ticker": corp.ticker,
                "motd": corp.motd,
                "role": agent.corp_role,
                "credit_vault": corp.credit_vault,
                "vault_capacity": corp.vault_capacity,
                "storage": list(aggregated_corp_storage.values())
            }

    return {
        "id": agent.id, "name": agent.name, "q": agent.q, "r": agent.r,
        "energy": agent.energy, "health": agent.health, "max_health": agent.max_health,
        "level": agent.level, "experience": agent.experience, "faction": agent.faction_id,
        "damage": agent.damage, "accuracy": agent.accuracy, "speed": agent.speed, "armor": agent.armor,
        "mining_yield": agent.mining_yield,
        "loot_bonus": agent.loot_bonus, "energy_save": agent.energy_save, "wear_resistance": agent.wear_resistance,
        "wear_and_tear": agent.wear_and_tear, "mass": get_agent_mass(agent), "max_mass": agent.max_mass,
        "capacity": agent.storage_capacity,
        "heat": agent.heat,
        "squad_id": agent.squad_id,
        "pending_squad_invite": agent.pending_squad_invite,
        "squad_members": squad_members,
        "corporation": corp_data,
        "inventory": list(aggregated_inv.values()),
        "storage": list(aggregated_storage.values()),
        "discovery": get_discovery_packet(STATION_CACHE, agent),
        "parts": [
            {
                "id": p.id, 
                "type": p.part_type, 
                "name": p.name, 
                "stats": {k: int(v * penalty) for k, v in p.stats.items()} if p.stats else {}, 
                "rarity": p.rarity, 
                "weight": PART_NAME_TO_WEIGHT.get(p.name, 10.0)
            } for p in agent.parts
        ],
        "visual_signature": get_agent_visual_signature(agent),
        "solar_intensity": int(get_solar_intensity(agent.q, agent.r, tick) * 100),
        "webhook_url": agent.webhook_url
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
        "mining_yield": agent.mining_yield,
        "wear_and_tear": agent.wear_and_tear, "mass": get_agent_mass(agent), "max_mass": agent.max_mass,
        "capacity": agent.storage_capacity,
        "visual_signature": get_agent_visual_signature(agent),
        "squad_id": agent.squad_id,
        "pending_squad_invite": agent.pending_squad_invite,
        "squad_members": squad_members,
        "solar_intensity": int(get_solar_intensity(agent.q, agent.r, tick) * 100)
    }

@router.get("/inventory")
async def get_agent_inventory(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns the agent's current inventory."""
    items = db.execute(select(InventoryItem).where(InventoryItem.agent_id == agent.id)).scalars().all()
    aggregated = {}
    for i in items:
        key = (i.item_type, str(i.data))
        if key in aggregated:
            aggregated[key]["quantity"] += i.quantity
        else:
            w = ITEM_WEIGHTS.get(i.item_type, 1.0)
            aggregated[key] = {"type": i.item_type, "quantity": i.quantity, "data": i.data, "weight": w}
    return list(aggregated.values())

@router.get("/api/gear")
async def get_agent_gear(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns the agent's equipped chassis parts with wear-penalized stats."""
    penalty = get_wear_penalty_factor(agent.wear_and_tear)
    
    return [
        {
            "id": p.id, 
            "type": p.part_type, 
            "name": p.name, 
            "stats": {k: int(v * penalty) for k, v in p.stats.items()} if p.stats else {}, 
            "rarity": p.rarity, 
            "weight": PART_NAME_TO_WEIGHT.get(p.name, 10.0)
        } for p in agent.parts
    ]

@router.get("/api/rescue_quote")
async def get_rescue_quote(agent: Agent = Depends(verify_api_key)):
    """Calculates the cost and ETA for a rescue to the Hub."""
    dist = get_hex_distance(agent.q, agent.r, 0, 0)
    cost = dist * 5
    eta_ticks = (dist // 10) + (1 if dist % 10 > 0 else 0)
    return {"distance": dist, "cost": cost, "eta_ticks": eta_ticks}

@router.get("/api/my_agent/performance", tags=["Agent Meta"])
async def get_my_agent_performance(agent: Agent = Depends(verify_api_key)):
    """Returns the agent's lifetime performance metrics."""
    return agent.performance_stats or {
        "ores_mined": 0,
        "enemies_defeated": 0,
        "credits_earned": 0,
        "distance_traveled": 0,
        "smelted_ingots": 0
    }

@router.post("/api/settings/webhook", tags=["Agent Meta"])
async def set_webhook_url(
    url: str = Query(...),
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """Sets the agent's Discord/Slack webhook URL for Mayday alerts."""
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Must be HTTPS.")
    
    agent.webhook_url = url
    db.commit()
    return {"status": "success", "webhook_url": agent.webhook_url}
