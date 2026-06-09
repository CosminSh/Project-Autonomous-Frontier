"""
admin.py — Protected admin endpoints.
All routes require the ADMIN_KEY header to match the env var ADMIN_KEY.
"""
import os
import logging
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from database import SessionLocal, engine, refresh_station_cache
from models import Agent, AuditLog, InventoryItem
from logic.events import event_manager
from observability import build_metrics_snapshot

logger = logging.getLogger("heartbeat.admin")
router = APIRouter(prefix="/api/admin", tags=["Admin"])

INSECURE_ADMIN_KEYS = {"", "change-me-in-production", "change-me-before-deploy", "password"}


def _check_key(x_admin_key: str):
    admin_key = os.environ.get("ADMIN_KEY", "")
    if os.environ.get("ENVIRONMENT") == "production" and admin_key in INSECURE_ADMIN_KEYS:
        raise HTTPException(status_code=503, detail="Admin API is not configured.")
    if not admin_key:
        raise HTTPException(status_code=503, detail="Admin API is not configured.")
    if not hmac.compare_digest(x_admin_key, admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")


class BanRequest(BaseModel):
    is_banned: bool = True
    reason: str = Field(..., min_length=3, max_length=300)


class MuteRequest(BaseModel):
    minutes: int = Field(..., ge=0, le=43200)
    reason: str = Field(..., min_length=3, max_length=300)


class RescueRequest(BaseModel):
    q: int = 0
    r: int = 0
    heal: bool = True
    reason: str = Field(..., min_length=3, max_length=300)


class CreditAdjustmentRequest(BaseModel):
    delta: int = Field(..., ge=-100000000, le=100000000)
    reason: str = Field(..., min_length=3, max_length=300)


def _serialize_agent(agent: Agent):
    return {
        "id": agent.id,
        "name": agent.name,
        "user_email": agent.user_email,
        "owner": agent.owner,
        "q": agent.q,
        "r": agent.r,
        "level": agent.level,
        "corporation_id": agent.corporation_id,
        "is_bot": agent.is_bot,
        "is_pitfighter": agent.is_pitfighter,
        "is_banned": bool(agent.is_banned),
        "muted_until": agent.muted_until.isoformat() if agent.muted_until else None,
        "moderation_note": agent.moderation_note,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


def _get_agent_or_404(db, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


def _add_admin_audit(db, agent_id: int, event_type: str, details: dict):
    db.add(AuditLog(agent_id=agent_id, event_type=event_type, details=details))


@router.post("/reseed")
def admin_reseed(x_admin_key: str = Header(...)):
    """
    Full world re-seed: wipes all hexes, sectors, and bots.
    Teleports all real players back to the hub (0, 0).
    Regenerates the entire map with current zone rules.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    logger.info("ADMIN: Manual reseed triggered.")
    try:
        from seed_world import seed_world
        seed_world()
        refresh_station_cache()
        logger.info("ADMIN: Reseed complete.")
        return {"status": "ok", "message": "World reseed complete. Station cache refreshed."}
    except Exception as e:
        logger.error(f"ADMIN: Reseed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/teleport_all")
def admin_teleport_all(x_admin_key: str = Header(...)):
    """
    Teleports ALL real players to the hub (0, 0) without wiping the world.
    Useful for fixing stranded players after a coordinate system change.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    from sqlalchemy import select
    from models import Agent
    with SessionLocal() as db:
        players = db.execute(select(Agent).where(Agent.is_bot == False)).scalars().all()
        for p in players:
            p.q = 0
            p.r = 0
        db.commit()
        count = len(players)
    logger.info(f"ADMIN: Teleported {count} players to (0, 0).")
    return {"status": "ok", "message": f"Teleported {count} players to (0, 0)."}


@router.get("/agents")
def admin_find_agents(query: str = "", limit: int = 25, x_admin_key: str = Header(...)):
    """
    Looks up agents by id, name, owner, or email for support and moderation work.
    """
    _check_key(x_admin_key)
    limit = max(1, min(limit, 100))
    with SessionLocal() as db:
        stmt = select(Agent).where(Agent.is_pitfighter == False).order_by(Agent.id.desc()).limit(limit)
        if query.strip():
            term = f"%{query.strip()}%"
            numeric_id = int(query) if query.isdigit() else None
            conditions = [
                Agent.name.ilike(term),
                Agent.owner.ilike(term),
                Agent.user_email.ilike(term),
            ]
            if numeric_id is not None:
                conditions.append(Agent.id == numeric_id)
            stmt = select(Agent).where(Agent.is_pitfighter == False, or_(*conditions)).order_by(Agent.id.desc()).limit(limit)
        agents = db.execute(stmt).scalars().all()
        return {"status": "ok", "agents": [_serialize_agent(agent) for agent in agents]}


@router.get("/audit")
def admin_audit_logs(
    agent_id: int | None = None,
    event_type: str | None = None,
    limit: int = 100,
    x_admin_key: str = Header(...),
):
    """
    Returns recent audit logs, optionally filtered by agent id and event type.
    """
    _check_key(x_admin_key)
    limit = max(1, min(limit, 500))
    with SessionLocal() as db:
        stmt = select(AuditLog)
        if agent_id is not None:
            stmt = stmt.where(AuditLog.agent_id == agent_id)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        logs = db.execute(stmt.order_by(AuditLog.time.desc()).limit(limit)).scalars().all()
        return {
            "status": "ok",
            "logs": [
                {
                    "id": log.id,
                    "time": log.time.isoformat() if log.time else None,
                    "agent_id": log.agent_id,
                    "event_type": log.event_type,
                    "details": log.details,
                }
                for log in logs
            ],
        }


@router.get("/metrics")
def admin_metrics(x_admin_key: str = Header(...)):
    """
    Returns launch operations metrics for dashboards and on-call checks.
    """
    _check_key(x_admin_key)
    with SessionLocal() as db:
        return build_metrics_snapshot(db, engine=engine, event_manager=event_manager)


@router.post("/agents/{agent_id}/ban")
def admin_set_ban(agent_id: int, request: BanRequest, x_admin_key: str = Header(...)):
    _check_key(x_admin_key)
    with SessionLocal() as db:
        agent = _get_agent_or_404(db, agent_id)
        agent.is_banned = request.is_banned
        agent.moderation_note = request.reason
        event_type = "ADMIN_AGENT_BANNED" if request.is_banned else "ADMIN_AGENT_UNBANNED"
        _add_admin_audit(db, agent.id, event_type, {"reason": request.reason})
        db.commit()
        db.refresh(agent)
        return {"status": "ok", "agent": _serialize_agent(agent)}


@router.post("/agents/{agent_id}/mute")
def admin_set_mute(agent_id: int, request: MuteRequest, x_admin_key: str = Header(...)):
    _check_key(x_admin_key)
    with SessionLocal() as db:
        agent = _get_agent_or_404(db, agent_id)
        if request.minutes == 0:
            muted_until = None
            event_type = "ADMIN_AGENT_UNMUTED"
        else:
            muted_until = datetime.now(timezone.utc) + timedelta(minutes=request.minutes)
            event_type = "ADMIN_AGENT_MUTED"
        agent.muted_until = muted_until
        agent.moderation_note = request.reason
        _add_admin_audit(db, agent.id, event_type, {
            "reason": request.reason,
            "minutes": request.minutes,
            "muted_until": muted_until.isoformat() if muted_until else None,
        })
        db.commit()
        db.refresh(agent)
        return {"status": "ok", "agent": _serialize_agent(agent)}


@router.post("/agents/{agent_id}/rescue")
def admin_rescue_agent(agent_id: int, request: RescueRequest, x_admin_key: str = Header(...)):
    _check_key(x_admin_key)
    with SessionLocal() as db:
        agent = _get_agent_or_404(db, agent_id)
        old_position = {"q": agent.q, "r": agent.r}
        agent.q = request.q
        agent.r = request.r
        if request.heal:
            agent.health = agent.max_health
            agent.energy = 100
        _add_admin_audit(db, agent.id, "ADMIN_AGENT_RESCUE", {
            "reason": request.reason,
            "from": old_position,
            "to": {"q": request.q, "r": request.r},
            "heal": request.heal,
        })
        db.commit()
        db.refresh(agent)
        return {"status": "ok", "agent": _serialize_agent(agent)}


@router.post("/agents/{agent_id}/credits")
def admin_adjust_credits(agent_id: int, request: CreditAdjustmentRequest, x_admin_key: str = Header(...)):
    _check_key(x_admin_key)
    with SessionLocal() as db:
        agent = _get_agent_or_404(db, agent_id)
        credits = db.execute(
            select(InventoryItem).where(
                InventoryItem.agent_id == agent.id,
                InventoryItem.item_type == "CREDITS",
            )
        ).scalars().first()
        if not credits:
            credits = InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=0)
            db.add(credits)
            db.flush()
        new_balance = credits.quantity + request.delta
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="Credit adjustment would make balance negative.")
        old_balance = credits.quantity
        credits.quantity = new_balance
        _add_admin_audit(db, agent.id, "ADMIN_CREDIT_ADJUST", {
            "reason": request.reason,
            "delta": request.delta,
            "old_balance": old_balance,
            "new_balance": new_balance,
        })
        db.commit()
        return {"status": "ok", "agent_id": agent.id, "old_balance": old_balance, "new_balance": new_balance}


@router.post("/trigger_arena")
def admin_trigger_arena(x_admin_key: str = Header(...)):
    """
    Manually triggers a round of Scrap Pit battles.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    logger.info("ADMIN: Manual arena battle trigger.")
    try:
        from logic.arena_manager import trigger_arena_battles
        with SessionLocal() as db:
            trigger_arena_battles(db)
        return {"status": "ok", "message": "Arena battles resolved."}
    except Exception as e:
        logger.error(f"ADMIN: Arena trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/arena/reset_season")
def admin_reset_arena_season(
    force: bool = Body(False, embed=True),
    x_admin_key: str = Header(...),
):
    """
    Manually runs the weekly Scrap Pit season reset.

    By default, this is idempotent per UTC ISO week. Set force=true only to
    recover from a partial/manual operation after checking the audit log.
    """
    _check_key(x_admin_key)
    logger.info(f"ADMIN: Manual arena season reset triggered. force={force}")
    try:
        from logic.arena_manager import reset_arena_season
        with SessionLocal() as db:
            result = reset_arena_season(db, force=force, source="admin")
        return result
    except Exception as e:
        logger.error(f"ADMIN: Arena season reset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
def admin_logs(lines: int = 100, x_admin_key: str = Header(...)):
    """
    Returns the last N lines of the app.log file.
    
    Requires: X-Admin-Key header matching ADMIN_KEY env var.
    """
    _check_key(x_admin_key)
    log_path = "app.log"
    if not os.path.exists(log_path):
        return {"status": "error", "message": "Log file not found."}
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            # Efficiently read last N lines
            # For small files, readlines is fine. 
            # For 10MB (our rotation limit), it's also okay.
            all_lines = f.readlines()
            requested_lines = all_lines[-max(1, min(lines, 1000)):]
            return {
                "status": "ok", 
                "line_count": len(requested_lines),
                "logs": requested_lines
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}
