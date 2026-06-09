from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import STATION_CACHE, get_db
from models import Agent, PlayerContract, InventoryItem, AuditLog, StorageItem
from routes.common import verify_api_key
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from config import ITEM_WEIGHTS

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

class ContractCreate(BaseModel):
    contract_type: str = "DELIVERY" # Currently only DELIVERY supported
    item_type: str
    quantity: int
    reward_credits: int
    target_station_q: int
    target_station_r: int
    expiry_hours: Optional[int] = 24

def _serialize_contract(contract: PlayerContract) -> dict:
    requirements = contract.requirements or {}
    item_type = requirements.get("item")
    quantity = requirements.get("qty", 0)
    target = {
        "q": contract.target_station_q,
        "r": contract.target_station_r,
    }

    return {
        "id": contract.id,
        "issuer_id": contract.issuer_id,
        "issuer": contract.issuer_name,
        "issuer_name": contract.issuer_name,
        "claimed_by_id": contract.claimed_by_id,
        "type": contract.contract_type,
        "contract_type": contract.contract_type,
        "item": item_type,
        "item_type": item_type,
        "quantity": quantity,
        "requirements": requirements,
        "reward": contract.reward_credits,
        "reward_credits": contract.reward_credits,
        "status": contract.status,
        "target": target,
        "target_station_q": contract.target_station_q,
        "target_station_r": contract.target_station_r,
        "created_at": contract.created_at,
        "expires_at": contract.expires_at,
    }

def _credit_agent(db: Session, agent_id: int, amount: int):
    credits = db.execute(
        select(InventoryItem).where(InventoryItem.agent_id == agent_id, InventoryItem.item_type == "CREDITS")
    ).scalars().first()
    if credits:
        credits.quantity += amount
    else:
        db.add(InventoryItem(agent_id=agent_id, item_type="CREDITS", quantity=amount))

def _refund_contract_escrow(db: Session, contract: PlayerContract, reason: str):
    if contract.status != "OPEN":
        return
    _credit_agent(db, contract.issuer_id, int(contract.reward_credits or 0))
    contract.status = reason
    db.add(AuditLog(agent_id=contract.issuer_id, event_type=f"CONTRACT_{reason}", details={
        "contract_id": contract.id,
        "refund": contract.reward_credits
    }))

@router.post("/post")
def post_contract(
    contract_data: ContractCreate,
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    if contract_data.reward_credits <= 0:
        raise HTTPException(status_code=400, detail="Reward must be positive.")
    if contract_data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")
    if contract_data.contract_type.upper() != "DELIVERY":
        raise HTTPException(status_code=400, detail="Only DELIVERY contracts are currently supported.")

    item_type = contract_data.item_type.strip().upper().replace(" ", "_").replace("-", "_")
    if item_type not in ITEM_WEIGHTS:
        raise HTTPException(status_code=400, detail="Unknown item type.")

    target_exists = any(
        s["q"] == contract_data.target_station_q and s["r"] == contract_data.target_station_r
        for s in STATION_CACHE
    )
    if not target_exists:
        raise HTTPException(status_code=400, detail="Target station coordinates are invalid.")

    # 1. Verify credits and Escrow
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < contract_data.reward_credits:
        raise HTTPException(status_code=400, detail="Insufficient credits for reward escrow.")
    
    credits.quantity -= contract_data.reward_credits
    
    # 2. Create Contract
    expires_at = _utcnow() + timedelta(hours=contract_data.expiry_hours or 24)
    
    new_contract = PlayerContract(
        issuer_id=agent.id,
        issuer_name=agent.name,
        contract_type="DELIVERY",
        requirements={"item": item_type, "qty": contract_data.quantity},
        reward_credits=contract_data.reward_credits,
        target_station_q=contract_data.target_station_q,
        target_station_r=contract_data.target_station_r,
        expires_at=expires_at,
        status="OPEN"
    )
    
    db.add(new_contract)
    db.add(AuditLog(agent_id=agent.id, event_type="CONTRACT_POST", details={
        "item": contract_data.item_type, 
        "qty": contract_data.quantity, 
        "reward": contract_data.reward_credits
    }))
    db.commit()
    db.refresh(new_contract)
    
    return {"status": "success", "contract_id": new_contract.id}

@router.get("/available")
def get_available_contracts(db: Session = Depends(get_db)):
    # Clean up expired ones on the fly for UI
    now = _utcnow()
    contracts = db.execute(
        select(PlayerContract).where(PlayerContract.status == "OPEN")
    ).scalars().all()
    
    results = []
    for c in contracts:
        if c.expires_at and _coerce_utc(c.expires_at) < now:
            _refund_contract_escrow(db, c, "EXPIRED")
            continue
            
        results.append(_serialize_contract(c))
        
    db.commit()
    return results

@router.post("/claim/{contract_id}")
def claim_contract(
    contract_id: int,
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    contract = db.get(PlayerContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    
    if contract.status != "OPEN":
        raise HTTPException(status_code=400, detail="Contract is no longer available.")
    
    if contract.issuer_id == agent.id:
        raise HTTPException(status_code=400, detail="You cannot claim your own contract.")
    
    # Check if agent already has 3 active claims to prevent hoarding
    existing_claims = db.execute(
        select(PlayerContract).where(PlayerContract.claimed_by_id == agent.id, PlayerContract.status == "CLAIMED")
    ).scalars().all()
    if len(existing_claims) >= 3:
        raise HTTPException(status_code=400, detail="You already have 3 active contract claims. Complete them first.")

    contract.status = "CLAIMED"
    contract.claimed_by_id = agent.id
    db.add(AuditLog(agent_id=agent.id, event_type="CONTRACT_CLAIM", details={"contract_id": contract_id}))
    db.commit()
    
    return {"status": "success", "message": "Contract claimed."}

@router.post("/fulfill/{contract_id}")
def fulfill_contract(
    contract_id: int,
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    contract = db.get(PlayerContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    
    if contract.status != "CLAIMED" or contract.claimed_by_id != agent.id:
        raise HTTPException(status_code=400, detail="Contract not active for this agent.")
    
    # Check location
    if agent.q != contract.target_station_q or agent.r != contract.target_station_r:
        raise HTTPException(status_code=400, detail=f"Target station is at ({contract.target_station_q}, {contract.target_station_r}). You are at ({agent.q}, {agent.r}).")
    
    # Check requirements
    req_item = contract.requirements.get("item")
    req_qty = contract.requirements.get("qty")
    
    inv_item = next((i for i in agent.inventory if i.item_type == req_item), None)
    if not inv_item or inv_item.quantity < req_qty:
        raise HTTPException(status_code=400, detail=f"Insufficient {req_item} in inventory. Need {req_qty}.")
    
    item_data = inv_item.data # Capture metadata
    
    # 1. Remove items from claimant
    inv_item.quantity -= req_qty
    if inv_item.quantity <= 0:
        db.delete(inv_item)
    
    # 2. Give reward to claimant
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if credits:
        credits.quantity += int(contract.reward_credits)
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(contract.reward_credits)))
    
    # 3. Give items to issuer STORAGE
    from models import StorageItem
    issuer_storage = db.execute(
        select(StorageItem).where(StorageItem.agent_id == contract.issuer_id, StorageItem.item_type == req_item, StorageItem.data == item_data)
    ).scalars().first()
    
    if issuer_storage:
        issuer_storage.quantity += req_qty
    else:
        db.add(StorageItem(agent_id=contract.issuer_id, item_type=req_item, quantity=req_qty, data=item_data))
    
    contract.status = "COMPLETED"
    db.add(AuditLog(agent_id=agent.id, event_type="CONTRACT_FULFILL", details={"contract_id": contract_id, "reward": contract.reward_credits}))
    db.commit()
    
    return {"status": "success", "message": "Contract fulfilled. Reward paid and items delivered to issuer storage."}

@router.post("/cancel/{contract_id}")
def cancel_contract(
    contract_id: int,
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    contract = db.get(PlayerContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    if contract.issuer_id != agent.id:
        raise HTTPException(status_code=403, detail="Only the issuer can cancel this contract.")
    if contract.status != "OPEN":
        raise HTTPException(status_code=400, detail="Only open contracts can be cancelled.")

    _refund_contract_escrow(db, contract, "CANCELLED")
    db.commit()
    return {"status": "success", "message": "Contract cancelled and escrow refunded."}

@router.get("/my_contracts")
def get_my_contracts(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns contracts issued or claimed by the agent."""
    issued = db.execute(
        select(PlayerContract).where(PlayerContract.issuer_id == agent.id)
    ).scalars().all()
    
    claimed = db.execute(
        select(PlayerContract).where(PlayerContract.claimed_by_id == agent.id)
    ).scalars().all()
    
    return [_serialize_contract(c) for c in issued + claimed]
