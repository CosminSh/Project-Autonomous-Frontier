from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, PlayerContract, InventoryItem, AuditLog, StorageItem
from routes.common import verify_api_key
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])

class ContractCreate(BaseModel):
    contract_type: str = "DELIVERY" # Currently only DELIVERY supported
    item_type: str
    quantity: int
    reward_credits: int
    target_station_q: int
    target_station_r: int
    expiry_hours: Optional[int] = 24

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

    # 1. Verify credits and Escrow
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < contract_data.reward_credits:
        raise HTTPException(status_code=400, detail="Insufficient credits for reward escrow.")
    
    credits.quantity -= contract_data.reward_credits
    
    # 2. Create Contract
    expires_at = datetime.utcnow() + timedelta(hours=contract_data.expiry_hours or 24)
    
    new_contract = PlayerContract(
        issuer_id=agent.id,
        issuer_name=agent.name,
        contract_type=contract_data.contract_type,
        requirements={"item": contract_data.item_type, "qty": contract_data.quantity},
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
    now = datetime.utcnow()
    contracts = db.execute(
        select(PlayerContract).where(PlayerContract.status == "OPEN")
    ).scalars().all()
    
    results = []
    for c in contracts:
        if c.expires_at and c.expires_at < now:
            # Mark as expired and refund (simplified cleanup)
            c.status = "EXPIRED"
            # Return credits to issuer storage or inventory
            # For now, just mark expired. System-wide cleanup should handle refunds properly.
            continue
            
        results.append({
            "id": c.id,
            "issuer": c.issuer_name,
            "type": c.contract_type,
            "requirements": c.requirements,
            "reward": c.reward_credits,
            "expires_at": c.expires_at,
            "target": {"q": c.target_station_q, "r": c.target_station_r}
        })
        
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

@router.get("/my_contracts")
def get_my_contracts(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns contracts issued or claimed by the agent."""
    issued = db.execute(
        select(PlayerContract).where(PlayerContract.issuer_id == agent.id)
    ).scalars().all()
    
    claimed = db.execute(
        select(PlayerContract).where(PlayerContract.claimed_by_id == agent.id)
    ).scalars().all()
    
    return {
        "issued": issued,
        "claimed": claimed
    }
