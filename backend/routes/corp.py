import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from models import Agent, Corporation, InventoryItem, AuditLog
from database import get_db
from .common import verify_api_key

logger = logging.getLogger("heartbeat")
router = APIRouter()

@router.post("/api/corp/create")
async def create_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    name = data.get("name")
    ticker = data.get("ticker")
    tax_rate = data.get("tax_rate", 0.0)
    
    if not name or not ticker:
        raise HTTPException(status_code=400, detail="Name and ticker are required.")
    
    if current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are already in a corporation.")
        
    # Check 10,000 Credits fee
    credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < 10000:
        raise HTTPException(status_code=400, detail="Creating a corporation requires 10,000 Credits.")
        
    existing = db.execute(select(Corporation).where((Corporation.name == name) | (Corporation.ticker == ticker))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Corporation name or ticker already taken.")
        
    credits.quantity -= 10000
    
    corp = Corporation(
        name=name,
        ticker=ticker,
        owner_id=current_agent.id,
        faction_id=current_agent.faction_id,
        tax_rate=float(tax_rate)
    )
    db.add(corp)
    db.flush()
    
    current_agent.corporation_id = corp.id
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_CREATED", details={"corp_id": corp.id, "name": corp.name}))
    db.commit()
    return {"status": "success", "corp_id": corp.id, "message": f"Corporation {corp.name} [{corp.ticker}] established."}

@router.post("/api/corp/join")
async def join_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    ticker = data.get("ticker")
    
    if current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Already in a corporation. Leave your current corp first.")
        
    corp = db.execute(select(Corporation).where(Corporation.ticker == ticker)).scalar_one_or_none()
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    current_agent.corporation_id = corp.id
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_JOINED", details={"corp_id": corp.id}))
    db.commit()
    return {"status": "success", "message": f"Joined Corporation {corp.name}."}

@router.post("/api/corp/leave")
async def leave_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if corp and corp.owner_id == current_agent.id:
        raise HTTPException(status_code=400, detail="CEO cannot leave. Transfer ownership or disband corp first.")
        
    current_agent.corporation_id = None
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_LEFT", details={"corp_id": corp.id if corp else None}))
    db.commit()
    return {"status": "success", "message": "Left corporation."}

@router.post("/api/corp/deposit")
async def corp_deposit(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    amount = data.get("amount", 0)
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0.")
        
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < amount:
        raise HTTPException(status_code=400, detail="Insufficient credits.")
        
    credits.quantity -= amount
    corp.credit_vault += amount
    
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_DEPOSIT", details={"corp_id": corp.id, "amount": amount}))
    db.commit()
    return {"status": "success", "message": f"Deposited {amount} CR into vault."}
