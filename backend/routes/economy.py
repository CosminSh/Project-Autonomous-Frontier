from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, AuctionOrder, InventoryItem, AuditLog, StorageItem
from routes.common import verify_api_key

router = APIRouter(prefix="/api", tags=["Economy"])

@router.get("/market")
async def get_market_orders(item_type: str = Query(None), db: Session = Depends(get_db)):
    """Returns active sell and buy orders on the galactic market."""
    query = select(AuctionOrder)
    if item_type: query = query.where(AuctionOrder.item_type == item_type)
    orders = db.execute(query).scalars().all()
    return [{"id": o.id, "item": o.item_type, "qty": o.quantity, "price": o.price, "type": o.order_type} for o in orders]

@router.get("/market/my_orders")
async def get_my_orders(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns only the authenticated agent's active market orders."""
    orders = db.execute(select(AuctionOrder).where(AuctionOrder.owner == agent.name)).scalars().all()
    return [{"id": o.id, "item": o.item_type, "qty": o.quantity, "price": o.price, "type": o.order_type} for o in orders]

@router.get("/market/prices")
async def get_market_prices(db: Session = Depends(get_db)):
    """Returns a summary of average prices for all traded items."""
    # Simplified price summary
    orders = db.execute(select(AuctionOrder)).scalars().all()
    prices = {}
    for o in orders:
        if o.item_type not in prices: prices[o.item_type] = []
        prices[o.item_type].append(o.price)
    
    return {k: sum(v)/len(v) for k, v in prices.items() if v}

@router.get("/storage")
async def get_vault_contents(agent: Agent = Depends(verify_api_key)):
    """Returns the agent's Personal Storage (Vault) inventory."""
    return [{"type": v.item_type, "quantity": v.quantity, "data": v.data} for v in agent.storage]

@router.post("/storage/deposit")
async def deposit_to_vault(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db), item_type: str = Body(...), quantity: int = Body(...)):
    """Moves items from agent inventory to personal vault."""
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < quantity: return {"error": "Insufficient inventory"}
    
    inv_item.quantity -= quantity
    if inv_item.quantity <= 0: db.delete(inv_item)
    
    vault_item = next((v for v in agent.storage if v.item_type == item_type), None)
    if vault_item: vault_item.quantity += quantity
    else: db.add(StorageItem(agent_id=agent.id, item_type=item_type, quantity=quantity))
    
    db.commit()
    return {"status": "deposited", "item": item_type, "qty": quantity}

@router.post("/storage/withdraw")
async def withdraw_from_vault(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db), item_type: str = Body(...), quantity: int = Body(...)):
    """Moves items from personal vault to agent inventory."""
    vault_item = next((v for v in agent.storage if v.item_type == item_type), None)
    if not vault_item or vault_item.quantity < quantity: return {"error": "Insufficient vault storage"}
    
    vault_item.quantity -= quantity
    if vault_item.quantity <= 0: db.delete(vault_item)
    
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item: inv_item.quantity += quantity
    else: db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity))
    
    db.commit()
    return {"status": "withdrawn", "item": item_type, "qty": quantity}
