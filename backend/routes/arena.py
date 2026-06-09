"""
arena.py — Routes for interacting with the Scrap Pit Arena.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from models import Agent, ChassisPart, AuditLog, InventoryItem, ArenaProfile
from database import get_db
from routes.common import verify_api_key

router = APIRouter(prefix="/api/arena", tags=["Arena"])

class EquipRequest(BaseModel):
    part_id: int


def get_or_create_pit_fighter(main_agent: Agent, db: Session) -> Agent:
    """Gets the user's pit fighter, creating it if it doesn't exist."""
    fighter_name = f"{main_agent.name}-PitFighter"
    fighter = db.execute(select(Agent).where(Agent.name == fighter_name)).scalars().first()
    
    if not fighter:
        fighter = Agent(
            name=fighter_name,
            owner=main_agent.user_email,
            is_bot=True,
            is_pitfighter=True,
            health=0,
            max_health=0,
            damage=0,
            accuracy=0,
            speed=0,
            armor=0,
            storage_capacity=0,
            q=0,
            r=0
        )
        db.add(fighter)
        db.flush() # Get ID
        
        profile = ArenaProfile(agent_id=fighter.id, elo=1200, wins=0, losses=0)
        db.add(profile)
        
        db.commit()
        db.refresh(fighter)
    elif not fighter.arena_profile:
        profile = ArenaProfile(agent_id=fighter.id, elo=1200, wins=0, losses=0)
        db.add(profile)
        db.commit()
        db.refresh(fighter)
    
    return fighter


def update_fighter_stats(fighter: Agent, db: Session):
    """Recalculates Pit Fighter stats based entirely on equipped gear."""
    parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == fighter.id)).scalars().all()
    
    base_health = 0
    base_damage = 0
    base_accuracy = 0
    base_speed = 0
    base_armor = 0
    
    for p in parts:
        stats = p.stats or {}
        base_health += stats.get("max_health", 0)
        base_damage += stats.get("damage", 0)
        base_accuracy += stats.get("accuracy", 0)
        base_speed += stats.get("speed", 0)
        base_armor += stats.get("armor", 0)
        
    fighter.health = base_health
    fighter.max_health = base_health
    fighter.damage = base_damage
    fighter.accuracy = base_accuracy
    fighter.speed = base_speed
    fighter.armor = base_armor
    db.commit()


def _serialize_arena_gear(parts):
    return [
        {
            "id": p.id,
            "type": p.part_type,
            "name": p.name,
            "rarity": p.rarity,
            "stats": p.stats,
            "durability": p.durability,
            "level": (p.stats or {}).get("upgrade_level", 0),
        } for p in parts
    ]


def _get_recent_arena_logs(fighter: Agent, db: Session, limit: int = 10):
    logs = db.execute(
        select(AuditLog)
        .where(AuditLog.agent_id == fighter.id, AuditLog.event_type.in_(["ARENA_VICTORY", "ARENA_DEFEAT", "ARENA_SEASON_RESET_AGENT"]))
        .order_by(AuditLog.time.desc())
        .limit(limit)
    ).scalars().all()
    opponent_ids = {
        (l.details or {}).get("opponent_id")
        for l in logs
        if (l.details or {}).get("opponent_id")
    }
    opponent_names = {}
    if opponent_ids:
        opponents = db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(opponent_ids))).all()
        opponent_names = {row.id: row.name for row in opponents}

    serialized = []
    for log in logs:
        details = log.details or {}
        opponent_id = details.get("opponent_id")
        serialized.append({
            "time": log.time.isoformat(),
            "timestamp": log.time.isoformat(),
            "event": log.event_type,
            "result": "WIN" if log.event_type == "ARENA_VICTORY" else "LOSS" if log.event_type == "ARENA_DEFEAT" else "RESET",
            "details": details,
            "message": details.get("message", ""),
            "opponent_id": opponent_id,
            "opponent_name": opponent_names.get(opponent_id),
            "opponent_elo": details.get("opponent_elo"),
            "elo_change": details.get("elo_delta", 0),
            "winner_id": fighter.id if log.event_type == "ARENA_VICTORY" else None,
        })
    return serialized


@router.get("/status")
def get_arena_status(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    fighter = get_or_create_pit_fighter(agent, db)
    parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == fighter.id)).scalars().all()
    profile = fighter.arena_profile
    gear = _serialize_arena_gear(parts)
    logs = _get_recent_arena_logs(fighter, db)
    
    # A fighter is ready if they have a Frame and at least one Actuator (Weapon/Drill)
    has_frame = any(p.part_type == "Frame" for p in parts)
    has_weapon = any(p.part_type == "Actuator" for p in parts)
    
    return {
        "fighter_name": fighter.name,
        "warning": "CRITICAL: Gear donated to the Scrap Pit is PERMANENT. It cannot be retrieved. All pit gear is DESTROYED at the end of each weekly season.",
        "season_info": "Seasons reset every Sunday at 00:00 UTC. All equipped gear will be lost.",
        "elo": profile.elo if profile else 1200,
        "wins": profile.wins if profile else 0,
        "losses": profile.losses if profile else 0,
        "stats": {
            "damage": fighter.damage,
            "accuracy": fighter.accuracy,
            "health": fighter.health,
            "speed": fighter.speed,
            "armor": fighter.armor
        },
        "is_ready": has_frame and has_weapon,
        "requirements": {
            "has_frame": has_frame,
            "has_weapon": has_weapon,
            "details": "Requires 1x Chassis Frame (HP) and 1x Actuator (Damage)."
        },
        "gear": gear,
        "arena_gear": gear,
        "logs": logs,
        "arena_logs": logs,
    }


@router.post("/equip")
def equip_pit_fighter(req: EquipRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    PERMANENTLY transfers an unequipped ChassisPart from the main agent to the Pit Fighter.
    WARNING: This action is non-reversible. Donated gear is lost forever at the end of the season.
    """
    # Verify part belongs to main agent and is unequipped
    part = db.execute(select(ChassisPart).where(ChassisPart.id == req.part_id, ChassisPart.agent_id == agent.id)).scalars().first()
    
    if not part:
        raise HTTPException(status_code=404, detail="Part not found in your inventory.")
        
    fighter = get_or_create_pit_fighter(agent, db)
    
    # Transfer ownership
    part.agent_id = fighter.id
    db.commit()
    
    update_fighter_stats(fighter, db)
    
    return {
        "status": "ok", 
        "message": f"Successfully donated {part.name} to {fighter.name}.",
        "warning": "Reminder: This part is now permanently bound to the Scrap Pit and will be destroyed at season's end."
    }


@router.get("/logs")
def get_arena_logs(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    fighter = get_or_create_pit_fighter(agent, db)
    return _get_recent_arena_logs(fighter, db)
