"""
routes_agent.py — Agent-centric API routes.
Covers: /api/perception, /api/intent, /api/my_agent, /api/agent_logs,
        /api/rename_agent, /api/market/my_orders, /api/bounties,
        /api/loot_drops, /api/post_bounty, /api/field_trade,
        /api/consume, /api/salvage, /api/intent/pending,
        /api/debug/* endpoints
"""
import logging

from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from models import Agent, Intent, AuditLog, WorldHex, InventoryItem, AuctionOrder, GlobalState, Bounty, LootDrop, DailyMission, AgentMission
from database import get_db, SessionLocal, STATION_CACHE
from config import ITEM_WEIGHTS, BASE_CAPACITY, BASE_REGEN, CORE_SERVICE_COST_CREDITS, CORE_SERVICE_COST_IRON_INGOT
from game_helpers import (
    get_hex_distance, get_solar_intensity, get_agent_visual_signature,
    get_discovery_packet, ensure_agent_has_starter_gear, merge_inventory
)

logger = logging.getLogger("heartbeat")
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Auth dependency (inline here since it needs the router context)
# ─────────────────────────────────────────────────────────────────────────────

async def verify_api_key(request: Request, db: Session = Depends(get_db)):
    api_key = request.headers.get("X-API-KEY")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    agent = db.execute(select(Agent).where(Agent.api_key == api_key)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return agent


def get_next_tick_index(db: Session) -> int:
    state = db.execute(select(GlobalState)).scalars().first()
    if state and state.phase in ["PERCEPTION", "STRATEGY"]:
        return state.tick_index or 0
    return (state.tick_index or 0) + 1


# ─────────────────────────────────────────────────────────────────────────────
# Perception
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/perception")
async def get_perception_packet(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    ensure_agent_has_starter_gear(db, current_agent)
    merge_inventory(db, current_agent)
    db.refresh(current_agent)

    inv_list = [{"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory]
    current_mass = sum(ITEM_WEIGHTS.get(i["type"], 1.0) * i["quantity"] for i in inv_list)

    stats = {
        "id": current_agent.id, "name": current_agent.name, "faction_id": current_agent.faction_id,
        "structure": current_agent.structure, "capacitor": current_agent.capacitor,
        "wear_and_tear": round(current_agent.wear_and_tear or 0.0, 2),
        "kinetic_force": current_agent.kinetic_force, "logic_precision": current_agent.logic_precision,
        "overclock": current_agent.overclock, "mass": current_mass,
        "capacity": current_agent.max_mass or BASE_CAPACITY,
        "inventory": inv_list, "q": current_agent.q, "r": current_agent.r,
        "location": {"q": current_agent.q, "r": current_agent.r},
        "visual_signature": get_agent_visual_signature(current_agent)
    }

    sensor_radius = 2
    has_neural_scanner = False
    for part in current_agent.parts:
        if part.part_type == "Sensor":
            p_stats = part.stats or {}
            sensor_radius = max(sensor_radius, p_stats.get("radius", 2))
            if "scan_depth" in p_stats:
                has_neural_scanner = True

    q_min, q_max = current_agent.q - sensor_radius, current_agent.q + sensor_radius
    r_min, r_max = current_agent.r - sensor_radius, current_agent.r + sensor_radius

    nearby_agents_results = db.execute(
        select(Agent).where(
            Agent.id != current_agent.id,
            Agent.q >= q_min, Agent.q <= q_max,
            Agent.r >= r_min, Agent.r <= r_max
        ).options(selectinload(Agent.inventory))
    ).scalars().all()
    nearby_agents = [a for a in nearby_agents_results if get_hex_distance(current_agent.q, current_agent.r, a.q, a.r) <= sensor_radius]

    nearby_hexes_results = db.execute(
        select(WorldHex).where(WorldHex.q >= q_min, WorldHex.q <= q_max, WorldHex.r >= r_min, WorldHex.r <= r_max)
    ).scalars().all()
    nearby_hexes = [h for h in nearby_hexes_results if get_hex_distance(current_agent.q, current_agent.r, h.q, h.r) <= sensor_radius]

    discovery = get_discovery_packet(STATION_CACHE, current_agent)

    top_prices = db.execute(
        select(AuctionOrder).where(AuctionOrder.order_type == "SELL").order_by(AuctionOrder.price.asc()).limit(3)
    ).scalars().all()

    system_advisories = []
    wear = current_agent.wear_and_tear or 0.0
    if wear > 50.0:
        repair_station = discovery.get("REPAIR") or discovery.get("MARKET") or discovery.get("SMELTER") or discovery.get("CRAFTER")
        loc_str = f"at ({repair_station['q']}, {repair_station['r']})" if repair_station else "at a REPAIR or MARKET station (0,0)"
        severity = "WARNING" if wear < 100.0 else "CRITICAL"
        system_advisories.append({
            "type": "SYSTEM_DEGRADATION", "severity": severity, "wear_level": f"{wear:.1f}%",
            "message": f"Critical System Wear detected. Perform a CORE_SERVICE {loc_str}.",
            "requirements": {"credits": CORE_SERVICE_COST_CREDITS, "items": {"IRON_INGOT": CORE_SERVICE_COST_IRON_INGOT}},
            "help": "Navigate to the coordinates provided and submit a CORE_SERVICE intent."
        })

    from datetime import datetime, timedelta, timezone
    recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=15) # Roughly the last tick interval
    recent_broadcast_logs = db.execute(
        select(AuditLog).where(
            AuditLog.event_type == "BROADCAST",
            AuditLog.time >= recent_cutoff
        ).order_by(AuditLog.time.desc()).limit(20)
    ).scalars().all()

    messages = []
    for log in recent_broadcast_logs:
        msg_q = log.details.get("q", 0)
        msg_r = log.details.get("r", 0)
        dist = get_hex_distance(current_agent.q, current_agent.r, msg_q, msg_r)
        if dist <= sensor_radius: # Include self broadcasts for immediate feedback? Or skip self? The prompt doesn't specify. Let's include all.
            # Get sender name
            sender_name = "Unknown"
            # It's better to fetch names in bulk or assume frontend can map agent_id if nearby, but adding to perception is safer.
            # Let's just fetch it, there's only a few broadcasts usually.
            sender_agent = db.get(Agent, log.agent_id)
            if sender_agent:
                sender_name = sender_agent.name

            messages.append({
                "sender_id": log.agent_id,
                "sender_name": sender_name,
                "distance": dist,
                "message": log.details.get("message", "")
            })

    state = db.execute(select(GlobalState)).scalars().first()
    tick_now = state.tick_index if state else 0

    pending_nav = db.execute(select(func.count(Intent.id)).where(
        Intent.agent_id == current_agent.id,
        Intent.tick_index > tick_now,
        Intent.action_type == "MOVE"
    )).scalar() or 0

    pro_tips = [tip for tip in [
        "Low Energy? Check 'solar_intensity' and equip a Power part." if current_agent.capacitor < 20 else None,
        "Navigation in progress. Use STOP to cancel." if pending_nav > 0 else None,
        "You are near a Station. Use /api/commands to see trade/repair/refine options." if any(discovery.values()) else None,
        "Always call /api/perception at the start of every tick to stay oriented."
    ] if tip is not None]

    squad_telemetry = []
    if current_agent.squad_id:
        squad_members = db.execute(select(Agent).where(
            Agent.squad_id == current_agent.squad_id, Agent.id != current_agent.id
        )).scalars().all()
        squad_telemetry = [{
            "id": sm.id, "name": sm.name, "q": sm.q, "r": sm.r,
            "structure": sm.structure, "max_structure": sm.max_structure
        } for sm in squad_members]

    return {
        "mcp_version": "1.0",
        "uri": f"mcp://terminal-frontier/perception/{current_agent.id}",
        "type": "resource",
        "content": {
            "squad_telemetry": squad_telemetry,
            "tick_info": {
                "current_tick": tick_now,
                "phase": state.phase if state else "UNKNOWN",
                "note": "Parallel Processing: You may submit multiple intents per tick. Intents submitted during PERCEPTION/STRATEGY execute in the upcoming CRUNCH.",
                "navigation_hint": "MOVE accepts any target. Adjacent targets (dist ≤ 1, or ≤ 3 Overclocked) execute immediately. Farther targets auto-path via BFS and queue per-tick steps. Submit STOP to cancel mid-navigation."
            },
            "agent_status": {
                **stats,
                "solar_intensity": int(get_solar_intensity(current_agent.q, current_agent.r, tick_now) * 100),
                "energy_regen": (lambda pp: round(BASE_REGEN * get_solar_intensity(current_agent.q, current_agent.r, tick_now) * (pp.stats or {}).get("efficiency", 1.0), 2) if pp else 0)(
                    next((p for p in current_agent.parts if p.part_type == "Power"), None)
                ),
                "pending_moves": pending_nav
            },
            "pro_tips": pro_tips,
            "system_advisories": system_advisories,
            "discovery": discovery,
            "environment": {
                "other_agents": [
                    {
                        "id": a.id, "q": a.q, "r": a.r, "name": a.name,
                        "structure": a.structure, "max_structure": a.max_structure,
                        "faction_id": a.faction_id, "is_feral": a.is_feral,
                        "scan_data": {
                            "structure": a.structure, "max_structure": a.max_structure,
                            "inventory": [{"type": i.item_type, "quantity": i.quantity} for i in a.inventory]
                        } if has_neural_scanner else None,
                        "visual_signature": get_agent_visual_signature(a)
                    } for a in nearby_agents
                ],
                "environment_hexes": [
                    {"q": h.q, "r": h.r, "terrain": h.terrain_type, "resource": h.resource_type,
                     "is_station": h.is_station, "station_type": h.station_type, "density": h.resource_density}
                    for h in nearby_hexes
                ]
            },
            "messages": messages,
            "market_data": [{"item": p.item_type, "price": p.price} for p in top_prices]
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Agent Status & Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/my_agent")
async def get_my_agent(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    ensure_agent_has_starter_gear(db, current_agent)
    merge_inventory(db, current_agent)
    db.refresh(current_agent)
    next_tick = get_next_tick_index(db)
    pending_intent = db.execute(select(Intent).where(Intent.agent_id == current_agent.id, Intent.tick_index == next_tick)).scalars().first()
    inv_list = [{"type": i.item_type, "quantity": i.quantity} for i in current_agent.inventory]
    current_mass = sum(ITEM_WEIGHTS.get(i["type"], 1.0) * i["quantity"] for i in inv_list)
    return {
        "id": current_agent.id, "name": current_agent.name,
        "squad_id": current_agent.squad_id,
        "structure": current_agent.structure, "max_structure": current_agent.max_structure,
        "capacitor": current_agent.capacitor,
        "solar_intensity": int(get_solar_intensity(current_agent.q, current_agent.r, next_tick - 1) * 100),
        "kinetic_force": current_agent.kinetic_force, "logic_precision": current_agent.logic_precision,
        "overclock": current_agent.overclock, "mass": current_mass,
        "capacity": current_agent.max_mass or BASE_CAPACITY,
        "q": current_agent.q, "r": current_agent.r, "inventory": inv_list,
        "parts": [{"id": p.id, "type": p.part_type, "name": p.name, "stats": p.stats, "durability": getattr(p, "durability", 100.0)} for p in current_agent.parts],
        "discovery": get_discovery_packet(STATION_CACHE, current_agent),
        "api_key": current_agent.api_key,
        "pending_intent": {"action": pending_intent.action_type, "data": pending_intent.data} if pending_intent else None
    }


@router.post("/api/rename_agent")
async def rename_agent(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Updates the name of the current agent, ensuring uniqueness."""
    data = await request.json()
    new_name = data.get("new_name")
    if not new_name or len(new_name) < 3:
        raise HTTPException(status_code=400, detail="Invalid name. Must be at least 3 characters.")
    existing = db.execute(select(Agent).where(Agent.name == new_name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This name is already registered by another pilot.")
    current_agent.name = new_name
    db.commit()
    return {"status": "success", "new_name": new_name}


@router.get("/api/agent_logs")
async def get_agent_logs(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    logs = db.execute(select(AuditLog).where(AuditLog.agent_id == current_agent.id).order_by(AuditLog.time.desc()).limit(20)).scalars().all()
    return [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs]


# ─────────────────────────────────────────────────────────────────────────────
# Intent Submission
# ─────────────────────────────────────────────────────────────────────────────

class IntentRequest(BaseModel):
    action_type: str
    data: dict


VALID_ACTIONS = [
    "MOVE", "MINE", "SCAN", "ATTACK", "INTIMIDATE", "LOOT", "DESTROY",
    "LIST", "BUY", "CANCEL", "EQUIP", "UNEQUIP", "SMELT", "CRAFT", "REPAIR",
    "SALVAGE", "CONSUME", "CORE_SERVICE", "REFINE_GAS", "CHANGE_FACTION",
    "DROP_LOAD", "STOP", "REPAIR_GEAR"
]


@router.post("/api/intent")
async def submit_intent(intent_req: IntentRequest, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if intent_req.action_type not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid action_type: {intent_req.action_type}. Supported: {', '.join(VALID_ACTIONS[:5])}...")
    data = intent_req.data or {}
    if intent_req.action_type == "MOVE":
        if "target_q" not in data or "target_r" not in data:
            raise HTTPException(status_code=400, detail="MOVE directive requires 'target_q' and 'target_r' coordinates.")
        try:
            int(data["target_q"]); int(data["target_r"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Coordinates must be valid integers.")
    elif intent_req.action_type in ["SMELT", "CRAFT"]:
        if not data:
            raise HTTPException(status_code=400, detail=f"{intent_req.action_type} directive requires payload data.")
    elif intent_req.action_type == "CORE_SERVICE":
        credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
        ingots = next((i for i in current_agent.inventory if i.item_type == "IRON_INGOT"), None)
        if not credits or credits.quantity < CORE_SERVICE_COST_CREDITS or not ingots or ingots.quantity < CORE_SERVICE_COST_IRON_INGOT:
            raise HTTPException(status_code=400, detail=f"CORE_SERVICE requires {CORE_SERVICE_COST_CREDITS} CREDITS and {CORE_SERVICE_COST_IRON_INGOT} IRON_INGOT.")

    next_tick = get_next_tick_index(db)
    db.add(Intent(agent_id=current_agent.id, action_type=intent_req.action_type, data=intent_req.data, tick_index=next_tick))
    db.commit()
    return {"status": "success", "message": "Intent recorded", "scheduled_tick": next_tick}


@router.get("/api/intent/pending")
async def get_pending_intents(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    intents = db.execute(select(Intent).where(Intent.agent_id == current_agent.id)).scalars().all()
    return {
        "agent_id": current_agent.id,
        "pending_count": len(intents),
        "intents": [{"action": i.action_type, "data": i.data, "scheduled_tick": i.tick_index} for i in intents]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Market & Economy (Player-facing)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/market/my_orders")
async def get_my_market_orders(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    orders = db.execute(select(AuctionOrder).where(AuctionOrder.owner == f"agent:{current_agent.id}")).scalars().all()
    return [{"id": o.id, "item": o.item_type, "type": o.order_type, "quantity": o.quantity, "price": o.price, "time": o.created_at.isoformat() if o.created_at else None} for o in orders]


@router.get("/api/bounties")
async def get_bounties(db: Session = Depends(get_db)):
    bounties = db.execute(select(Bounty).where(Bounty.is_open == True)).scalars().all()
    return [{"id": b.id, "target_id": b.target_id, "reward": b.reward, "issuer": b.issuer} for b in bounties]


@router.get("/api/loot_drops")
async def get_loot_drops(db: Session = Depends(get_db)):
    drops = db.execute(select(LootDrop)).scalars().all()
    return [{"id": d.id, "q": d.q, "r": d.r, "item_type": d.item_type, "quantity": d.quantity} for d in drops]


@router.post("/api/post_bounty")
async def post_bounty(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    target_id = data.get("target_id")
    amount = data.get("amount")
    if not target_id or not amount or amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid target_id or amount")
    target = db.get(Agent, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    credits_item = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits_item or credits_item.quantity < amount:
        raise HTTPException(status_code=400, detail="Insufficient credits")
    credits_item.quantity -= amount
    bounty = db.execute(select(Bounty).where(Bounty.target_id == target_id, Bounty.is_open == True)).scalar_one_or_none()
    if bounty:
        bounty.reward += amount
    else:
        db.add(Bounty(target_id=target_id, reward=amount, issuer=f"agent:{current_agent.id}"))
    db.commit()
    return {"status": "success", "bounty_reward": amount}


@router.get("/api/missions")
async def get_missions(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    active_missions = db.execute(select(DailyMission).where(DailyMission.expires_at > func.now())).scalars().all()
    
    result = []
    for m in active_missions:
        am = db.execute(select(AgentMission).where(AgentMission.agent_id == current_agent.id, AgentMission.mission_id == m.id)).scalar_one_or_none()
        
        progress = am.progress if am else 0
        is_completed = am.is_completed if am else False
        
        result.append({
            "id": m.id,
            "type": m.mission_type,
            "target_amount": m.target_amount,
            "reward_credits": m.reward_credits,
            "item_type": m.item_type,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
            "progress": progress,
            "is_completed": is_completed
        })
    return result


@router.post("/api/missions/turn_in")
async def turn_in_mission(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    mission_id = data.get("mission_id")
    quantity = data.get("quantity", 1)
    
    if not mission_id or quantity <= 0:
        raise HTTPException(status_code=400, detail="Invalid mission_id or quantity")
        
    mission = db.get(DailyMission, mission_id)
    if not mission or mission.mission_type != "TURN_IN":
        raise HTTPException(status_code=404, detail="Mission not found or not a TURN_IN mission")
        
    # Check expiration
    from datetime import datetime, timezone
    if mission.expires_at:
        expiry = mission.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Mission has expired")
        
    am = db.execute(select(AgentMission).where(AgentMission.agent_id == current_agent.id, AgentMission.mission_id == mission.id)).scalar_one_or_none()
    if not am:
        am = AgentMission(agent_id=current_agent.id, mission_id=mission.id, progress=0)
        db.add(am)
        
    if am.is_completed:
        raise HTTPException(status_code=400, detail="Mission is already completed")
        
    # Check inventory
    inv_item = next((i for i in current_agent.inventory if i.item_type == mission.item_type), None)
    
    remaining_needed = mission.target_amount - am.progress
    turn_in_qty = min(quantity, remaining_needed)
    
    if not inv_item or inv_item.quantity < turn_in_qty:
        raise HTTPException(status_code=400, detail=f"Insufficient {mission.item_type} in inventory")
        
    # Process turn in
    inv_item.quantity -= turn_in_qty
    if inv_item.quantity <= 0:
        db.delete(inv_item)
        
    am.progress += turn_in_qty
    
    result_message = f"Turned in {turn_in_qty} {mission.item_type}."
    
    if am.progress >= mission.target_amount:
        am.is_completed = True
        credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
        if credits:
            credits.quantity += mission.reward_credits
        else:
            db.add(InventoryItem(agent_id=current_agent.id, item_type="CREDITS", quantity=mission.reward_credits))
        
        result_message += f" Mission Complete! Rewarded {mission.reward_credits} CR."
        db.add(AuditLog(agent_id=current_agent.id, event_type="MISSION_COMPLETED", details={"mission_id": mission.id, "type": "TURN_IN", "reward": mission.reward_credits}))
    else:
        db.add(AuditLog(agent_id=current_agent.id, event_type="MISSION_PROGRESS", details={"mission_id": mission.id, "type": "TURN_IN", "progress": am.progress, "target": mission.target_amount}))

    db.commit()
    return {"status": "success", "message": result_message, "progress": am.progress, "is_completed": am.is_completed}


@router.post("/api/field_trade")
async def field_trade_api(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not data.get("target_id"):
        raise HTTPException(status_code=400, detail="target_id required")
    next_tick = get_next_tick_index(db)
    db.add(Intent(agent_id=current_agent.id, tick_index=next_tick, action_type="FIELD_TRADE", data=data))
    db.commit()
    return {"status": "success", "tick": next_tick}


@router.post("/api/consume")
async def consume_api(data: dict, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    next_tick = get_next_tick_index(db)
    db.add(Intent(agent_id=current_agent.id, tick_index=next_tick, action_type="CONSUME", data=data))
    db.commit()
    return {"status": "success", "tick": next_tick}


@router.post("/api/salvage")
async def salvage_api(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    next_tick = get_next_tick_index(db)
    db.add(Intent(agent_id=current_agent.id, tick_index=next_tick, action_type="SALVAGE", data={}))
    db.commit()
    return {"status": "success", "tick": next_tick}


# ─────────────────────────────────────────────────────────────────────────────
# Debug Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/debug/teleport")
async def debug_teleport(data: dict, db: Session = Depends(get_db)):
    agent = db.get(Agent, data.get("agent_id"))
    if agent:
        agent.q = data.get("q"); agent.r = data.get("r")
        db.commit()
        return {"status": "success", "new_location": {"q": agent.q, "r": agent.r}}
    return {"status": "error", "message": "Agent not found"}


@router.post("/api/debug/set_structure")
async def debug_set_structure(data: dict, db: Session = Depends(get_db)):
    agent = db.get(Agent, data.get("agent_id"))
    if agent:
        if data.get("structure") is not None: agent.structure = data["structure"]
        if data.get("capacitor") is not None: agent.capacitor = data["capacitor"]
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Agent not found"}


@router.post("/api/debug/add_item")
async def add_item_debug(data: dict, db: Session = Depends(get_db)):
    """Debug: Inject item into agent inventory."""
    agent = db.get(Agent, data.get("agent_id"))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    item_type = data.get("item_type")
    quantity = data.get("quantity", 1)
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item:
        inv_item.quantity += quantity
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity))
    db.commit()
    return {"status": "success"}


@router.get("/api/debug/heartbeat")
async def debug_heartbeat(db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    state = db.execute(select(GlobalState)).scalars().first()
    return {
        "tick": state.tick_index if state else -1,
        "phase": state.phase if state else "UNKNOWN",
        "uptime_now": datetime.now(timezone.utc).isoformat(),
        "db_connected": True
    }


# ─────────────────────────────────────────────────────────────────────────────
# Squad Management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/squad/invite")
async def invite_squad(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Creates a squad if none exists, and adds target to the squad."""
    data = await request.json()
    target_id = data.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="Missing target_id")
        
    target_agent = db.get(Agent, target_id)
    if not target_agent:
        raise HTTPException(status_code=404, detail="Target agent not found")
        
    # In a fully fleshed out system, this would send an invite to be accepted.
    # For now (as per MVP specs), it directly adds them to the squad if they aren't in one.
    if target_agent.squad_id:
        raise HTTPException(status_code=400, detail="Target agent is already in a squad")
        
    squad_id = current_agent.squad_id
    if not squad_id:
        # Create a new squad ID based on the leader's ID
        squad_id = current_agent.id
        current_agent.squad_id = squad_id
        
    target_agent.squad_id = squad_id
    db.add(AuditLog(agent_id=target_agent.id, event_type="SQUAD_JOINED", details={"squad_id": squad_id, "leader": current_agent.name}))
    db.commit()
    return {"status": "success", "squad_id": squad_id, "message": f"{target_agent.name} joined the squad."}


@router.post("/api/squad/leave")
async def leave_squad(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.squad_id:
        raise HTTPException(status_code=400, detail="Not in a squad")
    
    old_squad = current_agent.squad_id
    current_agent.squad_id = None
    db.commit()
    return {"status": "success", "message": f"Left squad {old_squad}"}


@router.post("/api/squad/kick")
async def kick_squad(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    target_id = data.get("target_id")
    
    if not current_agent.squad_id:
        raise HTTPException(status_code=400, detail="Not in a squad")
        
    # Simplify leader check: Squad ID is the leader's agent ID
    if current_agent.squad_id != current_agent.id:
        raise HTTPException(status_code=403, detail="Only the squad leader can kick members")
        
    target_agent = db.get(Agent, target_id)
    if not target_agent or target_agent.squad_id != current_agent.squad_id:
        raise HTTPException(status_code=400, detail="Target is not in your squad")
        
    target_agent.squad_id = None
    db.add(AuditLog(agent_id=target_agent.id, event_type="SQUAD_KICKED", details={"kicked_by": current_agent.name}))
    db.commit()
    return {"status": "success", "message": f"{target_agent.name} was kicked from the squad."}

