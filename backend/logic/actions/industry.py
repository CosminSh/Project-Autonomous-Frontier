import logging
import random
from sqlalchemy import select
from models import AuditLog, WorldHex, InventoryItem
from config import (
    SMELTING_RECIPES, SMELTING_RATIO, CRAFTING_RECIPES, CORE_RECIPES, 
    PART_DEFINITIONS, REPAIR_COST_PER_HP, REPAIR_COST_IRON_INGOT_PER_HP,
    MAINTENANCE_BASE_COST, MAINTENANCE_COEFFICIENT,
    UPGRADE_MAX_LEVEL, UPGRADE_BASE_INGOT_COST
)
import math
from game_helpers import add_experience, recalculate_agent_stats

logger = logging.getLogger("heartbeat.actions.industry")

async def handle_smelt(db, agent, intent, tick_count, manager):
    """Converts raw ore into refined ingots at a SMELTER station."""
    ore_type = intent.data.get("ore_type")
    quantity = intent.data.get("quantity", 10)
    
    if ore_type not in SMELTING_RECIPES:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INVALID_ORE"}))
        return

    inv_ore = next((i for i in agent.inventory if i.item_type == ore_type), None)
    if not inv_ore or inv_ore.quantity < quantity:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_ORE"}))
        return

    ingot_type = SMELTING_RECIPES[ore_type]
    amount_produced = quantity // SMELTING_RATIO
    if amount_produced <= 0: return

    inv_ore.quantity -= (amount_produced * SMELTING_RATIO)
    if inv_ore.quantity <= 0: db.delete(inv_ore)
    
    inv_ingot = next((i for i in agent.inventory if i.item_type == ingot_type), None)
    if inv_ingot: inv_ingot.quantity += amount_produced
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=ingot_type, quantity=amount_produced))
    
    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_SMELT", details={"ore": ore_type, "amount": amount_produced}))
    add_experience(db, agent, amount_produced * 10)
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "SMELT", "agent_id": agent.id, "ingot": ingot_type})

async def handle_refine_gas(db, agent, intent, tick_count, manager):
    """Fills Helium canisters at a REFINERY station."""
    gas_qty = intent.data.get("quantity", 10)
    inv_gas = next((i for i in agent.inventory if i.item_type == "HELIUM_GAS"), None)
    canister = next((i for i in agent.inventory if i.item_type in ["EMPTY_CANISTER", "HE3_CANISTER"]), None)
    
    if not inv_gas or inv_gas.quantity < gas_qty or not canister:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "MISSING_RESOURCES"}))
        return

    if canister.item_type == "EMPTY_CANISTER":
        canister.item_type = "HE3_CANISTER"
        canister.data = {"fill_level": 0}
    
    current_fill = (canister.data or {}).get("fill_level", 0)
    new_fill = min(100, current_fill + gas_qty)
    consumed_gas = new_fill - current_fill
    
    if consumed_gas > 0:
        inv_gas.quantity -= consumed_gas
        if inv_gas.quantity <= 0: db.delete(inv_gas)
        canister.data = {"fill_level": new_fill}
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_REFINE", details={"gas": consumed_gas, "fill": new_fill}))
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "REFINE_GAS", "agent_id": agent.id, "fill": new_fill})

async def handle_craft(db, agent, intent, tick_count, manager):
    """Crafts items and gear parts if materials are available and recipe is unlocked."""
    result_item = intent.data.get("item_type")
    recipe = CRAFTING_RECIPES.get(result_item)
    if not recipe: return

    unlocked = agent.unlocked_recipes or []
    if result_item not in CORE_RECIPES and result_item not in unlocked:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "RECIPE_LOCKED"}))
        return

    for mat, qty in recipe.items():
        inv_m = next((i for i in agent.inventory if i.item_type == mat), None)
        if not inv_m or inv_m.quantity < qty:
            db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_MATERIALS"}))
            return

    for mat, qty in recipe.items():
        inv_m = next((i for i in agent.inventory if i.item_type == mat), None)
        inv_m.quantity -= qty
        if inv_m.quantity <= 0: db.delete(inv_m)

    rarity = "COMMON"
    r_roll = random.random()
    if r_roll > 0.99: rarity = "LEGENDARY"
    elif r_roll > 0.95: rarity = "EPIC"
    elif r_roll > 0.85: rarity = "RARE"
    elif r_roll > 0.65: rarity = "UNCOMMON"

    item_type = f"PART_{result_item}" if result_item in PART_DEFINITIONS else result_item
    item_data = {"rarity": rarity, "stats": PART_DEFINITIONS.get(result_item, {}).get("stats", {})}
    db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
    
    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_CRAFT", details={"item": result_item, "rarity": rarity}))
    add_experience(db, agent, 20)
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "CRAFT", "agent_id": agent.id, "item": result_item})

async def handle_repair(db, agent, intent, tick_count, manager):
    """Restores agent health using credits and iron ingots at any station."""
    amt = intent.data.get("amount", 0)
    if amt <= 0: amt = agent.max_health - agent.health
    
    actual = min(amt, agent.max_health - agent.health)
    if actual <= 0: return

    cost_credits = actual * REPAIR_COST_PER_HP
    cost_ingots = int(actual * REPAIR_COST_IRON_INGOT_PER_HP)
    
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
    
    if credits and credits.quantity >= cost_credits and (cost_ingots == 0 or (ingots and ingots.quantity >= cost_ingots)):
        credits.quantity -= int(cost_credits)
        if cost_ingots > 0:
            ingots.quantity -= cost_ingots
            if ingots.quantity <= 0: db.delete(ingots)
        agent.health += actual
        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR", details={"hp": actual}))
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "REPAIR", "agent_id": agent.id, "hp": actual})
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "INSUFFICIENT_RESOURCES"}))
        
    # Reset wear at same time? Not by default here.
    agent.wear_and_tear = 0.0 # Optional reset for balance
    db.commit()

async def handle_salvage(db, agent, intent, tick_count, manager):
    """Collects loot drops at the agent's current coordinates."""
    from models import LootDrop
    drops = db.execute(select(LootDrop).where(LootDrop.q == agent.q, LootDrop.r == agent.r)).scalars().all()
    if not drops: return

    for d in drops:
        inv_i = next((i for i in agent.inventory if i.item_type == d.item_type), None)
        if inv_i: inv_i.quantity += d.quantity
        else: db.add(InventoryItem(agent_id=agent.id, item_type=d.item_type, quantity=d.quantity))
        db.delete(d)
    
    db.add(AuditLog(agent_id=agent.id, event_type="SALVAGE", details={"count": len(drops)}))
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "SALVAGE", "agent_id": agent.id})

def calculate_maintenance_cost(agent):
    """Calculates dynamic Wear & Tear cost based on chassis base + 20% of equipped gear cost."""
    costs = MAINTENANCE_BASE_COST.copy()
    
    # Add fractional costs for each equipped part
    for part in getattr(agent, "parts", []):
        config_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == part.name), None)
        if config_key and config_key in CRAFTING_RECIPES:
            recipe = CRAFTING_RECIPES[config_key]
            for resource, amount in recipe.items():
                fractional_cost = math.ceil(amount * MAINTENANCE_COEFFICIENT)
                if fractional_cost > 0:
                    costs[resource] = costs.get(resource, 0) + fractional_cost
                    
    return costs

async def handle_core_service(db, agent, intent, tick_count, manager):
    """Resets Wear & Tear dynamically scaling costs based on equipped loadout at qualified stations."""
    required_costs = calculate_maintenance_cost(agent)
    
    # Check if agent has all required resources
    has_all_resources = True
    for resource, required_qty in required_costs.items():
        inv_item = next((i for i in getattr(agent, "inventory", []) if i.item_type == resource), None)
        if not inv_item or inv_item.quantity < required_qty:
            has_all_resources = False
            break
            
    if has_all_resources:
        # Consume the resources
        for resource, required_qty in required_costs.items():
            inv_item = next((i for i in agent.inventory if i.item_type == resource), None)
            inv_item.quantity -= required_qty
            if inv_item.quantity <= 0:
                db.delete(inv_item)
                
        agent.wear_and_tear = 0.0
        db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE", details={"success": True}))
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={
            "reason": "INSUFFICIENT_RESOURCES",
            "required": required_costs
        }))
