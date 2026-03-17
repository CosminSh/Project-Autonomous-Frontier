from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import Agent, GlobalState, InventoryItem, ChassisPart
from database import get_db
from game_helpers import recalculate_agent_stats

router = APIRouter(prefix="/api/debug", tags=["Debug"])

@router.get("/heartbeat")
async def debug_heartbeat(db: Session = Depends(get_db)):
    state = db.execute(select(GlobalState)).scalars().first()
    return {
        "tick": state.tick_index if state else 0,
        "phase": state.phase if state else "PERCEPTION"
    }

@router.post("/teleport")
async def debug_teleport(data: dict, db: Session = Depends(get_db)):
    agent_id = data.get("agent_id")
    q = data.get("q", 0)
    r = data.get("r", 0)
    agent = db.get(Agent, agent_id)
    if agent:
        agent.q = q
        agent.r = r
        db.commit()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Agent not found")

@router.post("/add_item")
async def debug_add_item(data: dict, db: Session = Depends(get_db)):
    agent_id = data.get("agent_id")
    item_type = data.get("item_type")
    qty = data.get("quantity", 1)
    
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    inv_i = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_i:
        inv_i.quantity += qty
    else:
        db.add(InventoryItem(agent_id=agent_id, item_type=item_type, quantity=qty))
    
    db.commit()
    return {"status": "ok"}

@router.post("/set_structure")
async def debug_set_structure(data: dict, db: Session = Depends(get_db)):
    # Legacy name support for tests
    agent_id = data.get("agent_id")
    hp = data.get("structure") or data.get("health")
    energy = data.get("capacitor") or data.get("energy")
    
    agent = db.get(Agent, agent_id)
    if agent:
        if hp is not None: agent.health = hp
        if energy is not None: agent.energy = energy
        db.commit()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Agent not found")

@router.post("/equip")
async def debug_equip(data: dict, db: Session = Depends(get_db)):
    agent_id = data.get("agent_id")
    part_name = data.get("part_name")
    
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    from models import ChassisPart
    from config import PART_DEFINITIONS
    
    defn = PART_DEFINITIONS.get(part_name)
    if not defn:
        raise HTTPException(status_code=400, detail=f"Invalid part name: {part_name}")
        
    p = ChassisPart(
        agent_id=agent.id,
        part_type=defn["type"],
        name=part_name,
        stats=defn["stats"],
        rarity="STANDARD"
    )
    db.add(p)
    db.commit()
    recalculate_agent_stats(agent)
    db.commit()
    return {"status": "ok"}
