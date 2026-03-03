"""
routes_storage.py — Modularized API routes for Personal Storage (Vault) management.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from models import Agent, InventoryItem, StorageItem, WorldHex
from database import get_db
from config import ITEM_WEIGHTS

logger = logging.getLogger("heartbeat")
router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Auth Dependency Cleanup
# ─────────────────────────────────────────────────────────────────────────────

async def verify_api_key(request: Request, db: Session = Depends(get_db)):
    api_key = request.headers.get("X-API-KEY")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    agent = db.execute(select(Agent).where(Agent.api_key == api_key)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return agent

# ─────────────────────────────────────────────────────────────────────────────
# Storage Schemas
# ─────────────────────────────────────────────────────────────────────────────

class StorageOpRequest(BaseModel):
    item_type: str
    quantity: int

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_total_storage_mass(db: Session, agent_id: int) -> float:
    items = db.execute(select(StorageItem).where(StorageItem.agent_id == agent_id)).scalars().all()
    total_mass = 0.0
    for item in items:
        weight = ITEM_WEIGHTS.get(item.item_type, 1.0)
        total_mass += weight * item.quantity
    return total_mass

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/storage/deposit")
async def deposit_item(req: StorageOpRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # 1. Verify location (at a MARKET station)
    hex_info = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_info or hex_info.station_type != "MARKET":
        raise HTTPException(status_code=400, detail="Personal Storage is only accessible at a MARKET station.")

    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    # 2. Verify inventory
    inv_item = next((i for i in agent.inventory if i.item_type == req.item_type), None)
    if not inv_item or inv_item.quantity < req.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient {req.item_type} in inventory.")

    # 3. Check storage capacity
    item_weight = ITEM_WEIGHTS.get(req.item_type, 1.0)
    total_stored_mass = get_total_storage_mass(db, agent.id)
    new_total_mass = total_stored_mass + (item_weight * req.quantity)
    
    if new_total_mass > (agent.storage_capacity or 500.0):
        raise HTTPException(status_code=400, detail=f"Insufficient storage capacity. {new_total_mass:.1f}/{agent.storage_capacity:.1f}kg limit.")

    # 4. Perform Transfer
    inv_item.quantity -= req.quantity
    if inv_item.quantity <= 0:
        db.delete(inv_item)

    storage_item = db.execute(select(StorageItem).where(StorageItem.agent_id == agent.id, StorageItem.item_type == req.item_type)).scalar_one_or_none()
    if storage_item:
        storage_item.quantity += req.quantity
    else:
        db.add(StorageItem(agent_id=agent.id, item_type=req.item_type, quantity=req.quantity))

    db.commit()
    return {"status": "success", "message": f"Deposited {req.quantity} {req.item_type}"}

@router.post("/api/storage/withdraw")
async def withdraw_item(req: StorageOpRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # 1. Verify location
    hex_info = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_info or hex_info.station_type != "MARKET":
        raise HTTPException(status_code=400, detail="Personal Storage is only accessible at a MARKET station.")

    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    # 2. Verify storage
    storage_item = db.execute(select(StorageItem).where(StorageItem.agent_id == agent.id, StorageItem.item_type == req.item_type)).scalar_one_or_none()
    if not storage_item or storage_item.quantity < req.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient {req.item_type} in storage.")

    # 3. Perform Transfer
    storage_item.quantity -= req.quantity
    if storage_item.quantity <= 0:
        db.delete(storage_item)

    inv_item = next((i for i in agent.inventory if i.item_type == req.item_type), None)
    if inv_item:
        inv_item.quantity += req.quantity
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=req.item_type, quantity=req.quantity))

    db.commit()
    return {"status": "success", "message": f"Withdrew {req.quantity} {req.item_type}"}

@router.get("/api/storage/info")
async def get_storage_info(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    items = db.execute(select(StorageItem).where(StorageItem.agent_id == agent.id)).scalars().all()
    storage_list = [{"item_type": i.item_type, "quantity": i.quantity} for i in items]
    total_mass = get_total_storage_mass(db, agent.id)
    return {
        "capacity": agent.storage_capacity or 500.0,
        "used": total_mass,
        "items": storage_list
    }
@router.post("/api/storage/upgrade")
async def upgrade_storage(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    # 1. Verify location
    hex_info = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_info or hex_info.station_type != "MARKET":
        raise HTTPException(status_code=400, detail="Storage upgrades are only available at a MARKET station.")

    # 2. Define costs based on current capacity
    current_cap = agent.storage_capacity or 500.0
    tier = int((current_cap - 500.0) / 250.0) # 0, 1, 2...
    
    credit_cost = 500 * (tier + 1)
    material_type = "IRON_INGOT"
    material_qty = 10 * (tier + 1)
    
    if tier >= 2: material_type = "COPPER_INGOT"
    if tier >= 4: material_type = "GOLD_INGOT"
    if tier >= 6: material_type = "COBALT_INGOT"

    # 3. Check resources
    credits_item = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    mat_item = next((i for i in agent.inventory if i.item_type == material_type), None)
    
    if not credits_item or credits_item.quantity < credit_cost:
        raise HTTPException(status_code=400, detail=f"Insufficient credits for upgrade. Need {credit_cost} CR.")
    if not mat_item or mat_item.quantity < material_qty:
        raise HTTPException(status_code=400, detail=f"Insufficient materials for upgrade. Need {material_qty} {material_type}.")

    # 4. Perform Upgrade
    credits_item.quantity -= credit_cost
    mat_item.quantity -= material_qty
    if mat_item.quantity <= 0: db.delete(mat_item)
    
    agent.storage_capacity = current_cap + 250.0
    db.commit()
    
    return {
        "status": "success", 
        "message": f"Storage upgraded to {agent.storage_capacity}kg.",
        "new_capacity": agent.storage_capacity
    }
