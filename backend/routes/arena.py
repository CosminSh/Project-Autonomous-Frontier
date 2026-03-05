"""
arena.py — Routes for interacting with the Scrap Pit Arena.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from models import Agent, ChassisPart, AuditLog, InventoryItem
from database import get_db
from routes.common import verify_api_key

router = APIRouter(prefix="/api/arena", tags=["Arena"])

class EquipRequest(BaseModel):
    part_id: int


def get_or_create_pit_fighter(main_agent: Agent, db: Session) -> Agent:
    """Gets the user's pit fighter, creating it if it doesn't exist."""
    fighter_name = f"{main_agent.name}-PitFighter"
    fighter = db.execute(select(Agent).where(Agent.name == fighter_name, Agent.is_pit_fighter == True)).scalars().first()
    
    if not fighter:
        fighter = Agent(
            name=fighter_name,
            owner=main_agent.user_email,
            is_bot=True,
            is_pit_fighter=True,
            elo=1200,
            arena_wins=0,
            arena_losses=0,
            structure=0,
            max_structure=0,
            kinetic_force=0,
            logic_precision=0,
            storage_capacity=0
        )
        db.add(fighter)
        db.commit()
        db.refresh(fighter)
    
    return fighter


def update_fighter_stats(fighter: Agent, db: Session):
    """Recalculates Pit Fighter stats based entirely on equipped gear."""
    parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == fighter.id)).scalars().all()
    
    base_structure = 0
    base_kinetic = 0
    base_logic = 0
    
    for p in parts:
        stats = p.stats or {}
        base_structure += stats.get("structure", 0)
        base_kinetic += stats.get("kinetic_force", 0)
        base_logic += stats.get("logic_precision", 0)
        
    fighter.structure = base_structure
    fighter.max_structure = base_structure
    fighter.kinetic_force = base_kinetic
    fighter.logic_precision = base_logic
    db.commit()


@router.get("/status")
async def get_arena_status(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    fighter = get_or_create_pit_fighter(agent, db)
    parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == fighter.id)).scalars().all()
    
    return {
        "fighter_name": fighter.name,
        "elo": fighter.elo,
        "wins": fighter.arena_wins,
        "losses": fighter.arena_losses,
        "stats": {
            "kinetic_force": fighter.kinetic_force,
            "logic_precision": fighter.logic_precision,
            "structure": fighter.structure
        },
        "gear": [
            {
                "id": p.id,
                "type": p.part_type,
                "name": p.name,
                "rarity": p.rarity,
                "stats": p.stats,
                "durability": p.durability
            } for p in parts
        ]
    }


@router.post("/equip")
async def equip_pit_fighter(req: EquipRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    Permanently transfers an unequipped ChassisPart from the main agent to the Pit Fighter.
    """
    # Verify part belongs to main agent and is unequipped (slot_index is None implies it's in storage/inventory, 
    # but in our schema, unequipped parts just have agent_id = agent.id but aren't strictly 'equipped' until needed.
    # Actually, if it's in `chassis_parts` attached to agent, we'll allow moving it to the pit fighter.
    
    part = db.execute(select(ChassisPart).where(ChassisPart.id == req.part_id, ChassisPart.agent_id == agent.id)).scalars().first()
    
    if not part:
        raise HTTPException(status_code=404, detail="Part not found in your inventory.")
        
    # Prevent equipping the primary drill or core components if they are the ONLY ones.
    # We will assume if the player transfers it, they meant to. "Permanent donation".
    
    fighter = get_or_create_pit_fighter(agent, db)
    
    # Transfer ownership
    part.agent_id = fighter.id
    
    # Recalculate giving main agent base stats minus the part
    # Actually it's safer to just let the main agent's next action recalculate its stats or do it here.
    # We'll just update the fighter.
    db.commit()
    
    update_fighter_stats(fighter, db)
    
    return {"status": "ok", "message": f"Successfully donated {part.name} to {fighter.name}."}


@router.get("/logs")
async def get_arena_logs(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    fighter = get_or_create_pit_fighter(agent, db)
    
    logs = db.execute(
        select(AuditLog)
        .where(AuditLog.agent_id == fighter.id, AuditLog.event_type.in_(["ARENA_VICTORY", "ARENA_DEFEAT"]))
        .order_by(AuditLog.time.desc())
        .limit(10)
    ).scalars().all()
    
    return [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs]
