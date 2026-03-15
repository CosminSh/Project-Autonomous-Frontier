from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, AuctionOrder, InventoryItem, AuditLog, StorageItem, MarketPickup, WorldHex
from routes.common import verify_api_key
from game_helpers import get_agent_mass, ITEM_WEIGHTS

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
    orders = db.execute(select(AuctionOrder)).scalars().all()
    prices = {}
    for o in orders:
        if o.item_type not in prices: prices[o.item_type] = []
        prices[o.item_type].append(o.price)
    
    return {k: sum(v)/len(v) for k, v in prices.items() if v}
    
@router.get("/market/depth")
async def get_market_depth(item_type: str = Query(None), db: Session = Depends(get_db)):
    """Returns aggregated volume at each price point for a specific item (Order Book view)."""
    if not item_type:
        raise HTTPException(status_code=400, detail="item_type is required for market depth.")
        
    orders = db.execute(select(AuctionOrder).where(AuctionOrder.item_type == item_type)).scalars().all()
    
    depth = {"BUY": {}, "SELL": {}}
    for o in orders:
        price_str = f"{o.price:.2f}"
        depth[o.order_type][price_str] = depth[o.order_type].get(price_str, 0) + o.quantity
        
    return {
        "item": item_type,
        "buy_orders": sorted([{"price": float(p), "qty": q} for p, q in depth["BUY"].items()], key=lambda x: x["price"], reverse=True),
        "sell_orders": sorted([{"price": float(p), "qty": q} for p, q in depth["SELL"].items()], key=lambda x: x["price"])
    }

@router.delete("/market/orders/{order_id}")
async def cancel_market_order(order_id: int, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Cancels an active market order and refunds the items/credits."""
    order = db.get(AuctionOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    
    if order.owner != agent.name and order.owner != f"agent:{agent.id}":
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order.")
    
    # Refund logic
    if order.order_type == "SELL":
        # Refund items
        inv_item = next((i for i in agent.inventory if i.item_type == order.item_type), None)
        if inv_item:
            inv_item.quantity += order.quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=order.item_type, quantity=order.quantity))
    elif order.order_type == "BUY":
        # Refund credits
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        refund_amount = order.price * order.quantity
        if credits:
            credits.quantity += int(refund_amount)
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(refund_amount)))
            
    db.delete(order)
    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_CANCEL", details={"order_id": order_id, "item": order.item_type}))
    db.commit()
    
    return {"message": "Order cancelled and resources refunded."}

@router.patch("/market/orders/{order_id}")
async def adjust_market_order(order_id: int, price: float = Body(..., embed=True), agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Adjusts the price of an active market order."""
    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive.")
        
    order = db.get(AuctionOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    if order.owner != agent.name and order.owner != f"agent:{agent.id}":
        raise HTTPException(status_code=403, detail="Not authorized to modify this order.")
        
    if order.order_type == "BUY":
        # Handle credit difference for BUY orders
        cost_diff = (price - order.price) * order.quantity
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        if cost_diff > 0:
            if not credits or credits.quantity < cost_diff:
                raise HTTPException(status_code=400, detail="Insufficient credits to increase BUY order price.")
            credits.quantity -= int(cost_diff)
        elif cost_diff < 0:
            if credits:
                credits.quantity += int(-cost_diff)
            else:
                db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(-cost_diff)))
                
    order.price = price
    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_ADJUST", details={"order_id": order_id, "new_price": price}))
    db.commit()
    
    return {"message": "Order price adjusted."}

@router.get("/market/pickups")
async def get_market_pickups(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Returns all items waiting for the agent to pick up from the market."""
    pickups = db.execute(select(MarketPickup).where(MarketPickup.agent_id == agent.id)).scalars().all()
    return [{"id": p.id, "item": p.item_type, "qty": p.quantity} for p in pickups]

@router.post("/market/pickup")
async def claim_market_pickups(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Claims all pending market pickups. Must be at a MARKET station."""
    hex_loc = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalars().first()
    if not (hex_loc and hex_loc.is_station and (hex_loc.station_type == "MARKET" or hex_loc.station_type == "STATION_HUB")):
        raise HTTPException(status_code=400, detail="Must be at a MARKET station to claim pickups.")

    pickups = db.execute(select(MarketPickup).where(MarketPickup.agent_id == agent.id)).scalars().all()
    if not pickups:
        raise HTTPException(status_code=400, detail="No pending pickups.")

    # Tally up what is being claimed
    claimed = {}
    for p in pickups:
        inv_item = next((i for i in agent.inventory if i.item_type == p.item_type), None)
        if inv_item:
            inv_item.quantity += p.quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=p.item_type, quantity=p.quantity))
            
        claimed[p.item_type] = claimed.get(p.item_type, 0) + p.quantity
        db.delete(p)

    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_CLAIM", details={"claimed": claimed}))
    db.commit()

    return {"message": "Pickups claimed successfully.", "claimed": claimed}

# ── VAULT / STORAGE ────────────────────────────────────────────────────────────

@router.get("/storage")
async def get_vault_contents(agent: Agent = Depends(verify_api_key)):
    """Returns the agent's Personal Storage (Vault) inventory."""
    return [{"type": v.item_type, "quantity": v.quantity, "data": v.data} for v in agent.storage]

@router.get("/storage/info")
async def get_vault_info(agent: Agent = Depends(verify_api_key)):
    """Returns vault contents plus capacity stats and next upgrade requirement."""
    used_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in agent.storage)
    
    from config import get_vault_upgrade_requirements
    next_reqs = get_vault_upgrade_requirements(agent.storage_capacity)
    
    return {
        "items": [{"type": v.item_type, "quantity": v.quantity} for v in agent.storage],
        "capacity": agent.storage_capacity,
        "used": used_mass,
        "next_upgrade_requirements": next_reqs
    }

@router.post("/storage/deposit")
async def deposit_to_vault(
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db),
    item_type: str = Body(...),
    quantity: int = Body(...),
):
    """Moves items from agent inventory to personal vault. Requires MARKET station proximity."""
    item_type = item_type.upper().replace("-", "_")

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient inventory — you have {inv_item.quantity if inv_item else 0}x {item_type}."
        )

    # Capacity check (mass-based)
    current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in agent.storage)
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
    if current_stored_mass + (quantity * item_weight) > agent.storage_capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Vault capacity exceeded — {current_stored_mass:.1f}/{agent.storage_capacity:.0f} kg used."
        )

    inv_item.quantity -= quantity
    if inv_item.quantity <= 0:
        db.delete(inv_item)

    vault_item = next((v for v in agent.storage if v.item_type == item_type), None)
    if vault_item:
        vault_item.quantity += quantity
    else:
        db.add(StorageItem(agent_id=agent.id, item_type=item_type, quantity=quantity))

    db.commit()
    return {"message": f"Deposited {quantity}x {item_type} into vault."}

@router.post("/storage/withdraw")
async def withdraw_from_vault(
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db),
    item_type: str = Body(...),
    quantity: int = Body(...),
):
    """Moves items from personal vault to agent inventory."""
    item_type = item_type.upper().replace("-", "_")

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    vault_item = next((v for v in agent.storage if v.item_type == item_type), None)
    if not vault_item or vault_item.quantity < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient vault storage — you have {vault_item.quantity if vault_item else 0}x {item_type} stored."
        )

    # Mass check
    current_mass = get_agent_mass(agent)
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
    if current_mass + (quantity * item_weight) > agent.max_mass:
        raise HTTPException(
            status_code=400,
            detail=f"Cargo hold full — {current_mass:.1f}/{agent.max_mass:.0f} kg used."
        )

    vault_item.quantity -= quantity
    if vault_item.quantity <= 0:
        db.delete(vault_item)

    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item:
        inv_item.quantity += quantity
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity))

    db.commit()
    return {"message": f"Withdrew {quantity}x {item_type} from vault."}

@router.post("/storage/upgrade")
async def upgrade_vault(
    agent: Agent = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Increases vault capacity. Costs credits and increasingly rare materials."""
    from config import get_vault_upgrade_requirements, VAULT_UPGRADE_SIZE
    
    reqs = get_vault_upgrade_requirements(agent.storage_capacity)
    
    # ── Verify All Requirements ──
    for res_type, qty in reqs.items():
        inv_item = next((i for i in agent.inventory if i.item_type == res_type), None)
        has_qty = inv_item.quantity if inv_item else 0
        if has_qty < qty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient {res_type} — need {qty}, you have {has_qty}."
            )

    # ── Consume Resources ──
    for res_type, qty in reqs.items():
        inv_item = next((i for i in agent.inventory if i.item_type == res_type), None)
        inv_item.quantity -= qty
        if inv_item.quantity <= 0:
            db.delete(inv_item)

    # ── Apply Upgrade ──
    agent.storage_capacity += VAULT_UPGRADE_SIZE
    db.add(AuditLog(agent_id=agent.id, event_type="VAULT_UPGRADE", details={"new_capacity": agent.storage_capacity, "cost": reqs}))
    db.commit()
    
    return {"message": f"Vault upgraded! New capacity: {agent.storage_capacity:.0f} kg.", "new_capacity": agent.storage_capacity}
