import logging
from sqlalchemy import select
from models import AuctionOrder, InventoryItem, AuditLog, Agent, DailyMission, AgentMission
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
                b_inv = next((i for i in buyer.inventory if i.item_type == item_type), None)
                if b_inv: b_inv.quantity += trade_qty
                else: db.add(InventoryItem(agent_id=buyer_id, item_type=item_type, quantity=trade_qty))
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
            target = next((i for i in agent.inventory if i.item_type == item_type), None)
            if target: target.quantity += 1
            else: db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1))
            
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
