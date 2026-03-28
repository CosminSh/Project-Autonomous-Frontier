import logging
from sqlalchemy import select
from models import AuctionOrder, InventoryItem, AuditLog, Agent, DailyMission, AgentMission, MarketPickup, StorageItem, CorpStorageItem, Corporation
from sqlalchemy.sql import func
from datetime import datetime, timezone
from game_helpers import update_performance_stat

logger = logging.getLogger("heartbeat.actions.economy")

def _apply_corp_tax(db, agent, amount):
    """
    Applies corporate tax to a credit award.
    Returns (net_amount_to_agent, tax_amount_to_corp).
    """
    if not agent.corporation_id or amount <= 0:
        return amount, 0
        
    corp = db.get(Corporation, agent.corporation_id)
    if not corp:
        return amount, 0
    
    base_tax_rate = corp.tax_rate
    if base_tax_rate <= 0:
        return amount, 0
        
    # Apply "Market Influence" upgrade reduction
    final_tax_rate = base_tax_rate
    if corp.upgrades:
        market_lvl = corp.upgrades.get("MARKET", 0)
        if market_lvl > 0:
            from config import CORPORATE_UPGRADES
            upgrade_data = CORPORATE_UPGRADES["MARKET"]
            lvl_idx = min(market_lvl - 1, len(upgrade_data["levels"]) - 1)
            reduction = upgrade_data["levels"][lvl_idx].get("bonus", 0)
            final_tax_rate = max(0.0, base_tax_rate - reduction)
            
    tax_amount = int(amount * final_tax_rate)
    net_amount = amount - tax_amount
    
    if tax_amount > 0:
        corp.credit_vault += tax_amount
        db.add(AuditLog(agent_id=agent.id, event_type="CORP_TAX_COLLECTED", details={"corp_id": corp.id, "tax": tax_amount, "pre_tax": amount, "applied_rate": final_tax_rate}))
        
    return net_amount, tax_amount

async def handle_list(db, agent, intent, tick_count, manager):
    """Lists an item for sale, matching against existing BUY orders first."""
    item_type = intent.data.get("item_type")
    price = intent.data.get("price")
    quantity = intent.data.get("quantity", 1)
    
    if quantity == "MAX":
        quantity = sum(i.quantity for i in agent.inventory if i.item_type == item_type)
    
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item and not item_type.startswith("PART_"):
        alt_type = f"PART_{item_type}"
        if any(i.item_type == alt_type for i in agent.inventory):
            item_type = alt_type
            inv_item = next(i for i in agent.inventory if i.item_type == item_type)

    if not inv_item or inv_item.quantity < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "item": item_type}))
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
        item_data = inv_item.data # Preserve metadata
        if inv_item.quantity <= 0: db.delete(inv_item)
        
        net_cr, tax_cr = _apply_corp_tax(db, agent, int(trade_price * trade_qty))
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        if credits: credits.quantity += net_cr
        else: db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=net_cr))
        
        update_performance_stat(db, agent, "credits_earned", net_cr)
        
        if matching_buy.owner.startswith("agent:"):
            buyer_id = int(matching_buy.owner.split(":")[1])
            buyer = db.get(Agent, buyer_id)
            if buyer:
                pickup = next((p for p in buyer.market_pickups if p.item_type == item_type and p.data == item_data), None)
                if pickup: pickup.quantity += trade_qty
                else: db.add(MarketPickup(agent_id=buyer_id, item_type=item_type, quantity=trade_qty, data=item_data))
                await _update_buy_mission(db, buyer_id)
        
        if matching_buy.quantity > trade_qty: matching_buy.quantity -= trade_qty
        else: db.delete(matching_buy)
        
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_MATCH", details={"item": item_type, "qty": trade_qty}))
        if manager:
            await manager.broadcast({
                "type": "EVENT", "event": "MARKET", "subtype": "MATCH",
                "item": item_type, "qty": trade_qty, "price": trade_price,
                "seller": agent.name, "buyer": matching_buy.owner
            })
            await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
        
        quantity -= trade_qty

    if quantity > 0:
        item_data = inv_item.data # Preserve metadata
        inv_item.quantity -= quantity
        if inv_item.quantity <= 0: db.delete(inv_item)
        db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, quantity=quantity, price=price, order_type="SELL", data=item_data))
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_LIST", details={"item": item_type, "qty": quantity, "price": price}))
        if manager: await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})

async def handle_buy(db, agent, intent, tick_count, manager):
    """
    Buys items in bulk, matching against existing SELL orders or posting a persistent BUY order.
    Matches from cheapest to most expensive until quantity is met or credits/sellers are exhausted.
    """
    item_type = intent.data.get("item_type")
    max_price = intent.data.get("max_price", 999999)
    requested_qty = intent.data.get("quantity", 1)
    
    if requested_qty == "MAX":
        # Strategy for MAX: Use all available credits
        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
        if not credits or credits.quantity <= 0:
            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "NO_CREDITS"}))
            return
        # We don't know the exact price until we match, so we'll stop when credits run out in the loop below.
        requested_qty = 999999 

    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={"reason": "INSUFFICIENT_CREDITS"}))
        return

    # Find cheapest SELL orders matching the criteria
    query = select(AuctionOrder).where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "SELL", AuctionOrder.price <= max_price)
    orders = db.execute(query).scalars().all()
    
    if not orders and not item_type.startswith("PART_"):
        alt_type = f"PART_{item_type}"
        alt_query = select(AuctionOrder).where(AuctionOrder.item_type == alt_type, AuctionOrder.order_type == "SELL", AuctionOrder.price <= max_price)
        alt_orders = db.execute(alt_query).scalars().all()
        if alt_orders:
            orders = alt_orders
            item_type = alt_type # Use the one found

    orders = sorted(orders, key=lambda o: (o.price, o.created_at))
    
    total_bought = 0
    remaining_qty = requested_qty
    
    for order in orders:
        if remaining_qty <= 0: break
        
        trade_qty = min(remaining_qty, order.quantity)
        total_cost = int(trade_qty * order.price)
        
        if credits.quantity >= total_cost:
            # Execute Trade
            credits.quantity -= total_cost
            
            # Add to buyer's pickups (Preserving data if available)
            target = next((p for p in agent.market_pickups if p.item_type == item_type and p.data == order.data), None)
            if target: target.quantity += trade_qty
            else: db.add(MarketPickup(agent_id=agent.id, item_type=item_type, quantity=trade_qty, data=order.data))
            
            # Credit the seller
            if order.owner.startswith("agent:"):
                seller_id = int(order.owner.split(":")[1])
                seller = db.get(Agent, seller_id)
                if seller:
                    net_cr, tax_cr = _apply_corp_tax(db, seller, total_cost)
                    s_cr = next((i for i in seller.inventory if i.item_type == "CREDITS"), None)
                    if s_cr: s_cr.quantity += net_cr
                    else: db.add(InventoryItem(agent_id=seller.id, item_type="CREDITS", quantity=net_cr))
                    
                    update_performance_stat(db, seller, "credits_earned", net_cr)
            
            # Update order or delete if fully filled
            if order.quantity > trade_qty:
                order.quantity -= trade_qty
            else:
                db.delete(order)
            
            total_bought += trade_qty
            remaining_qty -= trade_qty
        else:
            # Partial fill based on remaining credits for this order's price
            can_afford = int(credits.quantity / order.price)
            if can_afford > 0:
                trade_qty = min(can_afford, order.quantity)
                cost = int(trade_qty * order.price)
                
                credits.quantity -= cost
                target = next((p for p in agent.market_pickups if p.item_type == item_type and p.data == order.data), None)
                if target: target.quantity += trade_qty
                else: db.add(MarketPickup(agent_id=agent.id, item_type=item_type, quantity=trade_qty, data=order.data))
                
                if order.owner.startswith("agent:"):
                    seller_id = int(order.owner.split(":")[1])
                    seller = db.get(Agent, seller_id)
                    if seller:
                        net_cr, tax_cr = _apply_corp_tax(db, seller, cost)
                        s_cr = next((i for i in seller.inventory if i.item_type == "CREDITS"), None)
                        if s_cr: s_cr.quantity += net_cr
                        else: db.add(InventoryItem(agent_id=seller.id, item_type="CREDITS", quantity=net_cr))
                        
                        update_performance_stat(db, seller, "credits_earned", net_cr)
                
                order.quantity -= trade_qty
                total_bought += trade_qty
                remaining_qty -= trade_qty
            
            break # No more credits to buy from any more orders

    if total_bought > 0:
        await _update_buy_mission(db, agent.id)
        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY_BULK", details={"item": item_type, "qty": total_bought}))
        if manager:
            await manager.broadcast({
                "type": "EVENT", "event": "MARKET", "subtype": "BULK_BUY",
                "item": item_type, "qty": total_bought, "buyer": agent.name
            })
            await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})

    # If we still want more and have credits, post a persistent BUY order
    if remaining_qty > 0 and remaining_qty < 9999: # Don't post infinite buy orders from 'MAX'
        # Only post if we can afford at least 1 at max_price
        if credits.quantity >= max_price:
            post_qty = remaining_qty
            db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, order_type="BUY", quantity=post_qty, price=max_price))
            # Note: Persistent BUY orders lock credits at the max_price
            credits.quantity -= int(post_qty * max_price)
            db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY_ORDER", details={"item": item_type, "qty": post_qty, "price": max_price}))
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
        inv_item = next((i for i in agent.inventory if i.item_type == order.item_type and i.data == order.data), None)
        if inv_item:
            inv_item.quantity += order.quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=order.item_type, quantity=order.quantity, data=order.data))
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
                net_reward, tax_reward = _apply_corp_tax(db, agent, m.reward_credits)
                cr = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                if cr: cr.quantity += net_reward
                else: db.add(InventoryItem(agent_id=agent_id, item_type="CREDITS", quantity=net_reward))
                
                agent = db.get(Agent, agent_id)
                update_performance_stat(db, agent, "credits_earned", net_reward)

async def handle_storage_deposit(db, agent, intent, tick_count, manager):
    """Moves items from agent inventory to personal or corporation vault. Requires Hub (0,0) or Station proximity."""
    item_type = intent.data.get("item_type")
    quantity = intent.data.get("quantity", 0)
    target = intent.data.get("target", "PERSONAL") # "PERSONAL" or "CORPORATION"
    
    # Proximity check (same for both)
    if agent.q != 0 or agent.r != 0:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NOT_AT_HUB"}))
        return

    if quantity == "MAX":
        quantity = sum(i.quantity for i in agent.inventory if i.item_type == item_type)
        from game_helpers import ITEM_WEIGHTS
        item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
        
        if target == "CORPORATION":
            if not agent.corporation_id:
                db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NO_CORPORATION"}))
                return
            corp = db.get(Corporation, agent.corporation_id)
            current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in corp.storage)
            max_possible = int((corp.vault_capacity - current_stored_mass) / item_weight)
            quantity = max(0, min(quantity, max_possible))
        else:
            current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in agent.storage)
            max_possible = int((agent.storage_capacity - current_stored_mass) / item_weight)
            quantity = max(0, min(quantity, max_possible))

    if quantity <= 0: return

    # Aggregate check
    total_inv = sum(i.quantity for i in agent.inventory if i.item_type == item_type)
    if total_inv < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "has": total_inv, "needs": quantity}))
        return

    from game_helpers import ITEM_WEIGHTS
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)

    if target == "CORPORATION":
        if not agent.corporation_id:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NO_CORPORATION"}))
            return
        corp = db.get(Corporation, agent.corporation_id)
        current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in corp.storage)
        if current_stored_mass + (quantity * item_weight) > corp.vault_capacity:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "CORP_CAPACITY_FULL"}))
            return
            
        # Subtract from inventory
        remaining = quantity
        inv_items = [i for i in agent.inventory if i.item_type == item_type]
        if not inv_items and not item_type.startswith("PART_"):
            alt_type = f"PART_{item_type}"
            inv_items = [i for i in agent.inventory if i.item_type == alt_type]
            if inv_items: item_type = alt_type

        # Sort by specific item metadata to ensure we take what the user likely intended
        # (For now, we just pick the first ones, but we MUST preserve the data)
        data_to_store = inv_items[0].data if inv_items else None

        for i in inv_items:
            if remaining <= 0: break
            take = min(i.quantity, remaining)
            i.quantity -= take
            remaining -= take
            if i.quantity <= 0: db.delete(i)
            
        # Add to corp storage
        vault_item = next((v for v in corp.storage if v.item_type == item_type and v.data == data_to_store), None)
        if vault_item:
            vault_item.quantity += quantity
        else:
            db.add(CorpStorageItem(corporation_id=agent.corporation_id, item_type=item_type, quantity=quantity, data=data_to_store))
        
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_DEPOSIT_CORP", details={"item": item_type, "qty": quantity, "corp_id": agent.corporation_id}))

    else:
        # Personal vault
        current_stored_mass = sum(v.quantity * ITEM_WEIGHTS.get(v.item_type, 1.0) for v in agent.storage)
        if current_stored_mass + (quantity * item_weight) > agent.storage_capacity:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "CAPACITY_FULL"}))
            return

        # Subtract from inventory
        remaining = quantity
        inv_items = [i for i in agent.inventory if i.item_type == item_type]
        if not inv_items and not item_type.startswith("PART_"):
            alt_type = f"PART_{item_type}"
            inv_items = [i for i in agent.inventory if i.item_type == alt_type]
            if inv_items: item_type = alt_type

        data_to_store = inv_items[0].data if inv_items else None

        for i in inv_items:
            if remaining <= 0: break
            take = min(i.quantity, remaining)
            i.quantity -= take
            remaining -= take
            if i.quantity <= 0: db.delete(i)

        # Add to storage
        vault_item = next((v for v in agent.storage if v.item_type == item_type and v.data == data_to_store), None)
        if vault_item:
            vault_item.quantity += quantity
        else:
            db.add(StorageItem(agent_id=agent.id, item_type=item_type, quantity=quantity, data=data_to_store))

        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_DEPOSIT", details={"item": item_type, "qty": quantity}))

async def handle_storage_withdraw(db, agent, intent, tick_count, manager):
    """Moves items from personal or corporation vault to agent inventory. Requires Hub (0,0) or Station proximity."""
    item_type = intent.data.get("item_type")
    quantity = intent.data.get("quantity", 0)
    target = intent.data.get("target", "PERSONAL") # "PERSONAL" or "CORPORATION"
    
    # Proximity check
    if agent.q != 0 or agent.r != 0:
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NOT_AT_HUB"}))
        return

    if target == "CORPORATION":
        if not agent.corporation_id:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "NO_CORPORATION"}))
            return
        corp = db.get(Corporation, agent.corporation_id)
        
        if quantity == "MAX":
            quantity = sum(s.quantity for s in corp.storage if s.item_type == item_type)
            from game_helpers import get_agent_mass, ITEM_WEIGHTS
            current_mass = get_agent_mass(agent)
            item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
            max_possible = int((agent.max_mass - current_mass) / item_weight)
            quantity = max(0, min(quantity, max_possible))
            
        if quantity <= 0: return
        
        # Aggregate check
        total_vault = sum(s.quantity for s in corp.storage if s.item_type == item_type)
        if total_vault < quantity:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "INSUFFICIENT_CORP_STORAGE", "has": total_vault}))
            return
            
        # Mass check
        from game_helpers import get_agent_mass, ITEM_WEIGHTS
        current_mass = get_agent_mass(agent)
        item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
        if current_mass + (quantity * item_weight) > agent.max_mass:
            db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_FAILED", details={"reason": "CARGO_FULL"}))
            return
            
        # Subtract from corp storage
        remaining = quantity
        vault_items = [s for s in corp.storage if s.item_type == item_type]
        if not vault_items and not item_type.startswith("PART_"):
            alt_type = f"PART_{item_type}"
            vault_items = [s for s in corp.storage if s.item_type == alt_type]
            if vault_items: item_type = alt_type

        data_to_withdraw = vault_items[0].data if vault_items else None

        for s in vault_items:
            if remaining <= 0: break
            take = min(s.quantity, remaining)
            s.quantity -= take
            remaining -= take
            if s.quantity <= 0: db.delete(s)
            
        # Add to inventory
        inv_item = next((i for i in agent.inventory if i.item_type == item_type and i.data == data_to_withdraw), None)
        if inv_item:
            inv_item.quantity += quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity, data=data_to_withdraw))
            
        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_WITHDRAW_CORP", details={"item": item_type, "qty": quantity, "corp_id": agent.corporation_id}))

    else:
        # Personal vault
        if quantity == "MAX":
            quantity = sum(s.quantity for s in agent.storage if s.item_type == item_type)
            from game_helpers import get_agent_mass, ITEM_WEIGHTS
            current_mass = get_agent_mass(agent)
            item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
            max_possible = int((agent.max_mass - current_mass) / item_weight)
            quantity = max(0, min(quantity, max_possible))

        if quantity <= 0: return

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
        if not vault_items and not item_type.startswith("PART_"):
            alt_type = f"PART_{item_type}"
            vault_items = [s for s in agent.storage if s.item_type == alt_type]
            if vault_items: item_type = alt_type

        data_to_withdraw = vault_items[0].data if vault_items else None

        for s in vault_items:
            if remaining <= 0: break
            take = min(s.quantity, remaining)
            s.quantity -= take
            remaining -= take
            if s.quantity <= 0: db.delete(s)

        # Add to inventory
        inv_item = next((i for i in agent.inventory if i.item_type == item_type and i.data == data_to_withdraw), None)
        if inv_item:
            inv_item.quantity += quantity
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=quantity, data=data_to_withdraw))

        db.add(AuditLog(agent_id=agent.id, event_type="STORAGE_WITHDRAW", details={"item": item_type, "qty": quantity}))

async def handle_transfer(db, agent, intent, tick_count, manager):
    """Directly transfers items to another agent in the same hex."""
    target_id = intent.data.get("target_id")
    item_type = intent.data.get("item_type")
    quantity = intent.data.get("quantity", 0)

    if not target_id or not item_type or quantity <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_FAILED", details={"reason": "INVALID_PARAMETERS"}))
        return

    target = db.get(Agent, target_id)
    if not target:
        db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_FAILED", details={"reason": "TARGET_NOT_FOUND"}))
        return

    # Proximity check
    if agent.q != target.q or agent.r != target.r:
        db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_FAILED", details={"reason": "TARGET_TOO_FAR"}))
        return

    if quantity == "MAX":
        quantity = sum(i.quantity for i in agent.inventory if i.item_type == item_type)

    if quantity <= 0: return

    # Check inventory
    inv_items = [i for i in agent.inventory if i.item_type == item_type]
    if not inv_items and not item_type.startswith("PART_"):
        alt_type = f"PART_{item_type}"
        inv_items = [i for i in agent.inventory if i.item_type == alt_type]
        if inv_items: item_type = alt_type

    total_has = sum(i.quantity for i in inv_items)
    if total_has < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_FAILED", details={"reason": "INSUFFICIENT_INVENTORY", "item": item_type}))
        return

    # Mass check for target
    from game_helpers import get_agent_mass, ITEM_WEIGHTS
    item_weight = ITEM_WEIGHTS.get(item_type, 1.0)
    target_mass = get_agent_mass(target)
    if target_mass + (quantity * item_weight) > target.max_mass:
        db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_FAILED", details={"reason": "TARGET_CARGO_FULL"}))
        return

    # Transfer logic
    remaining = quantity
    data_to_transfer = inv_items[0].data if inv_items else None
    
    for i in inv_items:
        if remaining <= 0: break
        take = min(i.quantity, remaining)
        i.quantity -= take
        remaining -= take
        if i.quantity <= 0: db.delete(i)

    target_inv = next((i for i in target.inventory if i.item_type == item_type and i.data == data_to_transfer), None)
    if target_inv:
        target_inv.quantity += quantity
    else:
        db.add(InventoryItem(agent_id=target.id, item_type=item_type, quantity=quantity, data=data_to_transfer))

    db.add(AuditLog(agent_id=agent.id, event_type="TRANSFER_SENT", details={"target": target.name, "item": item_type, "qty": quantity}))
    db.add(AuditLog(agent_id=target.id, event_type="TRANSFER_RECEIVED", details={"from": agent.name, "item": item_type, "qty": quantity}))

    if manager:
        await manager.broadcast({
            "type": "EVENT", "event": "TRANSFER", 
            "sender_id": agent.id, "target_id": target.id, 
            "item": item_type, "qty": quantity
        })
