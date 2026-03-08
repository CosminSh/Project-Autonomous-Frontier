import logging
from sqlalchemy import select
from models import AuctionOrder, InventoryItem, AuditLog, Agent, DailyMission, AgentMission, MarketPickup, StorageItem
from sqlalchemy.sql import func
from datetime import datetime, timezone

logger = logging.getLogger("heartbeat.actions.economy")

async def handle_list(db, agent, intent, tick_count, manager):
    """Lists an item for sale, matching against existing BUY orders first."""
    item_type = intent.data.get("item_type")
    price = intent.data.get("price")
    quantity = intent.data.get("quantity", 1)
    
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_INVENTORY"}))
        return

    # Instant Matching
    matching_buy = db.execute(select(AuctionOrder)
        .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "BUY", AuctionOrder.price >= price)
        .order_by(AuctionOrder.price.desc())
    ).scalars().first()
    
    if matching_buy:
        trade_qty = min(quantity, matching_buy.quantity)
        trade_price = matching_buy.price
        
        inv_item.quantity -= trade_qty
        if inv_item.quantity <= 0: db.delete(inv_item)
        
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        if credits: credits.quantity += int(trade_price * trade_qty)
        else: db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(trade_price * trade_qty)))
        
        if matching_buy.owner.startswith("agent:"):
            buyer_id = int(matching_buy.owner.split(":")[1])
            buyer = db.get(Agent, buyer_id)
            if buyer:
                pickup = next((p for p in buyer.market_pickups if p.item_type == item_type), None)
                if pickup: pickup.quantity += trade_qty
                else: db.add(MarketPickup(agent_id=buyer_id, item_type=item_type, quantity=trade_qty))
                await _update_buy_mission(db, buyer_id)
        
        if matching_buy.quantity > trade_qty: matching_buy.quantity -= trade_qty
        else: db.delete(matching_buy)
        
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_MATCH", details={"item": item_type, "qty": trade_qty}))
        if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
        
        quantity -= trade_qty

    if quantity > 0:
        inv_item.quantity -= quantity
        if inv_item.quantity <= 0: db.delete(inv_item)
        db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, quantity=quantity, price=price, order_type="SELL"))
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_LIST", details={"item": item_type, "qty": quantity, "price": price}))
        if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})

async def handle_buy(db, agent, intent, tick_count, manager):
    """Buys an item, matching against existing SELL orders or posting a persistent BUY order."""
    item_type = intent.data.get("item_type")
    max_price = intent.data.get("max_price", 999999)
    
    order = db.execute(select(AuctionOrder)
        .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "SELL", AuctionOrder.price <= max_price)
        .order_by(AuctionOrder.price.asc())
    ).scalars().first()
    
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if order:
        if credits and credits.quantity >= order.price:
            credits.quantity -= int(order.price)
            target = next((p for p in agent.market_pickups if p.item_type == item_type), None)
            if target: target.quantity += 1
            else: db.add(MarketPickup(agent_id=agent.id, item_type=item_type, quantity=1))
            
            if order.owner.startswith("agent:"):
                seller = db.get(Agent, int(order.owner.split(":")[1]))
                if seller:
                    s_cr = next((i for i in seller.inventory if i.item_type == "CREDITS"), None)
                    if s_cr: s_cr.quantity += int(order.price)
                    else: db.add(InventoryItem(agent_id=seller.id, item_type="CREDITS", quantity=int(order.price)))
            
            if order.quantity > 1: order.quantity -= 1
            else: db.delete(order)
            
            await _update_buy_mission(db, agent.id)
            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY", details={"item": item_type, "price": order.price}))
            if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
        else:
            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_CREDITS"}))
    else:
        # Persistent BUY Order
        if credits and credits.quantity >= max_price:
            credits.quantity -= int(max_price)
            db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, order_type="BUY", quantity=1, price=max_price))
            await _update_buy_mission(db, agent.id)
            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY_ORDER", details={"item": item_type, "price": max_price}))
            if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})

async def handle_cancel(db, agent, intent, tick_count, manager):
    """Cancels an active market order (via logic tick)."""
    order_id = intent.data.get("order_id")
    if not order_id:
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "MISSING_ORDER_ID"}))
        return

    order = db.get(AuctionOrder, order_id)
    if not order or (order.owner != agent.name and order.owner != f"agent:{agent.id}"):
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "ORDER_NOT_FOUND_OR_UNAUTHORIZED"}))
        return

    if order.order_type == "SELL":
        inv_item = next((i for i in agent.inventory if i.item_type == order.item_type), None)
        if inv_item:
            inv_item.quantity += order.quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=order.item_type, quantity=order.quantity))
    elif order.order_type == "BUY":
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        refund_amount = order.price * order.quantity
        if credits:
            credits.quantity += int(refund_amount)
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(refund_amount)))

    db.delete(order)
    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_CANCEL", details={"order_id": order_id, "item": order.item_type}))
    if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": order.item_type})

async def _update_buy_mission(db, agent_id):
    """Helper to update Mission Progress for BUY_MARKET types."""
    active = db.execute(select(DailyMission).where(DailyMission.mission_type == "BUY_MARKET", DailyMission.expires_at > func.now())).scalars().all()
    for m in active:
        am = db.execute(select(AgentMission).where(AgentMission.agent_id == agent_id, AgentMission.mission_id == m.id)).scalar_one_or_none()
        if not am:
            am = AgentMission(agent_id=agent_id, mission_id=m.id, progress=0)
            db.add(am)
        if not am.is_completed:
            am.progress += 1
            if am.progress >= m.target_amount:
                am.is_completed = True
                agent = db.get(Agent, agent_id)
                cr = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                if cr: cr.quantity += m.reward_credits
                else: db.add(InventoryItem(agent_id=agent_id, item_type="CREDITS", quantity=m.reward_credits))

async def handle_storage_deposit(db, agent, intent, tick_count, manager):
    """Moves items from agent inventory to personal vault. Requires Hub (0,0) or Station proximity."""
    item_type = intent.data.get("item_type")
    quantity = intent.data.get("quantity", 0)
    
    if quantity <= 0: return

    # Proximity check
    if agent.q != 0 or agent.r != 0:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NOT_AT_HUB"}))
        return

    # Aggregate check
    total_inv = sum(i.quantity for i in agent.inventory if i.item_type == item_type)
    if total_inv < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "has": total_inv, "needs": quantity}))
        return

    # Capacity check
    from game_helpers import ITEM_WEIGHTS
    current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in agent.storage)
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
    if current_stored_mass + (quantity * item_weight) > agent.storage_capacity:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "CAPACITY_FULL"}))
        return

    # Subtract from inventory (handle multiple stacks)
    remaining = quantity
    inv_items = [i for i in agent.inventory if i.item_type == item_type]
    for i in inv_items:
        if remaining <= 0: break
        take = min(i.quantity, remaining)
        i.quantity -= take
        remaining -= take
        if i.quantity <= 0: db.delete(i)

    # Add to storage
    vault_item = next((v for v in agent.storage if v.item_type == item_type), None)
    if vault_item:
        vault_item.quantity += quantity
    else:
        db.add(StorageItem(agent_id=agent.id, item_type=item_type, quantity=quantity))

    db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_DEPOSIT", details={"item": item_type, "qty": quantity}))

async def handle_storage_withdraw(db, agent, intent, tick_count, manager):
    """Moves items from personal vault to agent inventory."""
    item_type = intent.data.get("item_type")
    quantity = intent.data.get("quantity", 0)
    
    if quantity <= 0: return

    if agent.q != 0 or agent.r != 0:
        return

    # Aggregate check
    total_vault = sum(s.quantity for s in agent.storage if s.item_type == item_type)
    if total_vault < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "INSUFFICIENT_STORAGE", "has": total_vault}))
        return

    # Mass check
    from game_helpers import get_agent_mass, ITEM_WEIGHTS
    current_mass = get_agent_mass(agent)
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
    if current_mass + (quantity * item_weight) > agent.max_mass:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "CARGO_FULL"}))
        return

    # Subtract from storage
    remaining = quantity
    vault_items = [s for s in agent.storage if s.item_type == item_type]
    for s in vault_items:
        if remaining <= 0: break
        take = min(s.quantity, remaining)
        s.quantity -= take
        remaining -= take
        if s.quantity <= 0: db.delete(s)

    # Add to inventory
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item:
        inv_item.quantity += quantity
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity))

    db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_WITHDRAW", details={"item": item_type, "qty": quantity}))
