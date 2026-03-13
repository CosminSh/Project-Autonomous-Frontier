import logging
import random
from sqlalchemy import select
from models import AuditLog, WorldHex, InventoryItem
from config import (
    SMELTING_RECIPES, SMELTING_RATIO, SMELTING_MAX_PER_TICK, SMELTING_ENERGY_COSTS,
    CRAFTING_RECIPES, CORE_RECIPES, 
    PART_DEFINITIONS, REPAIR_COST_PER_HP, REPAIR_COST_IRON_INGOT_PER_HP,
    MAINTENANCE_BASE_COST, MAINTENANCE_COEFFICIENT,
    UPGRADE_MAX_LEVEL, UPGRADE_BASE_INGOT_COST
)
import math
from game_helpers import add_experience, recalculate_agent_stats, ITEM_WEIGHTS, get_hex_distance

logger = logging.getLogger("heartbeat.actions.industry")

def get_total_resource(agent, item_type):
    """Returns total quantity of an item across inventory and vault."""
    inv_qty = sum(i.quantity for i in agent.inventory if i.item_type == item_type)
    vault_qty = sum(s.quantity for s in agent.storage if s.item_type == item_type)
    return inv_qty + vault_qty

def consume_resources(db, agent, item_type, total_needed):
    """Consumes specified quantity of an item, prioritizing inventory then vault."""
    remaining = total_needed
    
    # 1. Consume from Inventory first
    inv_items = [i for i in agent.inventory if i.item_type == item_type]
    for i in inv_items:
        if remaining <= 0: break
        take = min(i.quantity, remaining)
        i.quantity -= take
        remaining -= take
        if i.quantity <= 0: db.delete(i)
        
    # 2. Consume from Vault if still needed
    if remaining > 0:
        vault_items = [s for s in agent.storage if s.item_type == item_type]
        for s in vault_items:
            if remaining <= 0: break
            take = min(s.quantity, remaining)
            s.quantity -= take
            remaining -= take
            if s.quantity <= 0: db.delete(s)
            
    return remaining == 0

async def handle_smelt(db, agent, intent, tick_count, manager):
    """Converts raw ore into refined ingots at a SMELTER station."""
    ore_type = intent.data.get("ore_type")
    raw_qty = intent.data.get("quantity", 5)
    
    if raw_qty == "MAX":
        raw_qty = get_total_resource(agent, ore_type)
    
    if ore_type not in SMELTING_RECIPES:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INVALID_ORE", "ore": ore_type}))
        return

    # Proximity check for SMELTER
    from database import STATION_CACHE
    if not STATION_CACHE:
        logger.warning("SMELT: STATION_CACHE is empty! Refreshing...")
        from database import refresh_station_cache
        refresh_station_cache()

    stations = [s for s in STATION_CACHE if s["station_type"] == "SMELTER"]
    can_smelt = any(get_hex_distance(agent.q, agent.r, s["q"], s["r"]) == 0 for s in stations)
    if not can_smelt:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "NOT_AT_SMELTER", "q": agent.q, "r": agent.r, "available_smelters": stations}))
        logger.warning(f"SMELT: Agent {agent.id} not at SMELTER (Pos: {agent.q},{agent.r})")
        return

    # Production Logic (Bottlenecked to 1 Ingot per Tick)
    amount_requested = int(raw_qty) // SMELTING_RATIO
    amount_produced = min(amount_requested, SMELTING_MAX_PER_TICK)
    
    if amount_produced <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "QUANTITY_TOO_LOW", "has": raw_qty, "min": SMELTING_RATIO}))
        return

    energy_cost = amount_produced * SMELTING_ENERGY_COSTS.get(ore_type, 100)
    if agent.energy < energy_cost:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_ENERGY", "has": agent.energy, "needs": energy_cost}))
        return

    total_ore = get_total_resource(agent, ore_type)
    consumed_ore = amount_produced * SMELTING_RATIO
    if total_ore < consumed_ore:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_ORE", "has": total_ore, "needs": consumed_ore}))
        return

    # Execution
    consume_resources(db, agent, ore_type, consumed_ore)
    agent.energy -= energy_cost
    
    ingot_type = SMELTING_RECIPES[ore_type]
    inv_ingot = next((i for i in agent.inventory if i.item_type == ingot_type), None)
    if inv_ingot: inv_ingot.quantity += amount_produced
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=ingot_type, quantity=amount_produced))
    
    is_max = intent.data.get("quantity") == "MAX"
    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_SMELT", details={
        "ore": ore_type, 
        "amount": amount_produced, 
        "energy_cost": energy_cost,
        "remaining_request": "MAX" if is_max else (amount_requested - amount_produced)
    }))
    logger.info(f"SMELT: Agent {agent.id} produced {amount_produced} {ingot_type} from {consumed_ore} {ore_type}.")
    
    add_experience(db, agent, amount_produced * 10)
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "SMELT", "agent_id": agent.id, "ingot": ingot_type})
        
    # Auto-requeue if we still have more to smelt (like MINE does)
    remaining_to_smelt = amount_requested - amount_produced
    if remaining_to_smelt > 0 or (is_max and get_total_resource(agent, ore_type) >= SMELTING_RATIO):
        from models import Intent
        # Don't overwrite if user queued something else for next tick
        override = db.execute(select(Intent).where(Intent.agent_id == agent.id, Intent.tick_index == tick_count + 1)).scalars().first()
        if not override:
            db.add(Intent(
                agent_id=agent.id,
                action_type="SMELT",
                data=intent.data,
                tick_index=tick_count + 1
            ))

async def handle_refine_gas(db, agent, intent, tick_count, manager):
    """Fills Helium canisters at a REFINERY station."""
    gas_qty = intent.data.get("quantity", 10)
    inv_gas = next((i for i in agent.inventory if i.item_type == "HELIUM_GAS"), None)
    canister = next((i for i in agent.inventory if i.item_type in ["EMPTY_CANISTER", "HE3_CANISTER"]), None)

    if gas_qty == "MAX":
        if inv_gas and canister:
            current_fill = (canister.data or {}).get("fill_level", 0)
            gas_needed = 100 - current_fill
            gas_qty = min(inv_gas.quantity, gas_needed)
        else:
            gas_qty = 0 # Will fail the check below
    
    if not inv_gas or inv_gas.quantity < gas_qty or not canister:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "MISSING_RESOURCES"}))
        return

    if canister.item_type == "EMPTY_CANISTER":
        canister.item_type = "HE3_CANISTER"
        canister.data = {"fill_level": 0}
    
    # Proximity check for REFINERY
    from database import STATION_CACHE
    if not STATION_CACHE:
        from database import refresh_station_cache
        refresh_station_cache()
    
    stations = [s for s in STATION_CACHE if s["station_type"] == "REFINERY"]
    can_refine = any(get_hex_distance(agent.q, agent.r, s["q"], s["r"]) == 0 for s in stations)
    if not can_refine:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "NOT_AT_REFINERY", "q": agent.q, "r": agent.r, "available_refineries": stations}))
        return

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
    if not recipe:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INVALID_RECIPE", "item": result_item}))
        return

    unlocked = agent.unlocked_recipes or []
    if result_item not in CORE_RECIPES and result_item not in unlocked:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "RECIPE_LOCKED"}))
        return

    for mat, qty in recipe.items():
        if get_total_resource(agent, mat) < qty:
            db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "INSUFFICIENT_MATERIALS", "missing": mat}))
            return

    for mat, qty in recipe.items():
        consume_resources(db, agent, mat, qty)

    rarity = "COMMON"
    r_roll = random.random()
    if r_roll > 0.99: rarity = "LEGENDARY"
    elif r_roll > 0.95: rarity = "EPIC"
    elif r_roll > 0.85: rarity = "RARE"
    elif r_roll > 0.65: rarity = "UNCOMMON"

    item_type = f"PART_{result_item}" if result_item in PART_DEFINITIONS else result_item
    
    # Proximity check for CRAFTER
    from database import STATION_CACHE
    if not STATION_CACHE:
        from database import refresh_station_cache
        refresh_station_cache()

    stations = [s for s in STATION_CACHE if s["station_type"] == "CRAFTER"]
    can_craft = any(get_hex_distance(agent.q, agent.r, s["q"], s["r"]) == 0 for s in stations)
    if not can_craft:
        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "NOT_AT_CRAFTER", "q": agent.q, "r": agent.r, "available_crafters": stations}))
        return

    item_data = {"rarity": rarity, "stats": PART_DEFINITIONS.get(result_item, {}).get("stats", {})}
    db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
    
    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_CRAFT", details={"item": result_item, "rarity": rarity}))
    add_experience(db, agent, 20)
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "CRAFT", "agent_id": agent.id, "item": result_item})

async def handle_repair(db, agent, intent, tick_count, manager):
    """Restores agent health using credits and iron ingots at any station."""
    amt = intent.data.get("amount", 0)
    if amt == "MAX" or (isinstance(amt, (int, float)) and amt <= 0):
        # Calculate how much we can afford
        hp_needed = agent.max_health - agent.health
        if amt == "MAX":
            # Budget check
            credits = get_total_resource(agent, "CREDITS")
            ingots = get_total_resource(agent, "IRON_INGOT")
            
            # Max HP per credits
            can_afford_cr = int(credits / REPAIR_COST_PER_HP)
            can_afford_in = hp_needed
            if REPAIR_COST_IRON_INGOT_PER_HP > 0:
                can_afford_in = int(ingots / REPAIR_COST_IRON_INGOT_PER_HP)
                
            amt = min(hp_needed, can_afford_cr, can_afford_in)
        else:
            amt = hp_needed
    
    # Proximity check for REPAIR or any Station
    from database import STATION_CACHE
    if not STATION_CACHE:
        from database import refresh_station_cache
        refresh_station_cache()
    
    can_repair = any(get_hex_distance(agent.q, agent.r, s["q"], s["r"]) == 0 for s in STATION_CACHE)
    if not can_repair:
        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "NOT_AT_STATION", "q": agent.q, "r": agent.r}))
        return

    actual = min(amt, agent.max_health - agent.health)
    if actual <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "ALREADY_AT_MAX_HEALTH"}))
        return

    cost_credits = actual * REPAIR_COST_PER_HP
    cost_ingots = int(actual * REPAIR_COST_IRON_INGOT_PER_HP)
    
    if get_total_resource(agent, "CREDITS") >= cost_credits and (cost_ingots == 0 or get_total_resource(agent, "IRON_INGOT") >= cost_ingots):
        consume_resources(db, agent, "CREDITS", int(cost_credits))
        if cost_ingots > 0:
            consume_resources(db, agent, "IRON_INGOT", cost_ingots)
            
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
    # Proximity check for REPAIR station or Hub
    from database import STATION_CACHE
    if not STATION_CACHE:
        from database import refresh_station_cache
        refresh_station_cache()
        
    repair_stations = [s for s in STATION_CACHE if s["station_type"] in ["REPAIR", "STATION_HUB"]]
    at_repair = any(get_hex_distance(agent.q, agent.r, s["q"], s["r"]) == 0 for s in repair_stations)
    if not at_repair:
        db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={"reason": "NOT_AT_REPAIR_STATION", "q": agent.q, "r": agent.r, "available_stations": repair_stations}))
        return

    required_costs = calculate_maintenance_cost(agent)
    
    # Check if agent has all required resources
    has_all_resources = True
    for resource, required_qty in required_costs.items():
        if get_total_resource(agent, resource) < required_qty:
            has_all_resources = False
            break
            
    if has_all_resources:
        # Consume the resources (prioritize inventory, then vault)
        for resource, required_qty in required_costs.items():
            consume_resources(db, agent, resource, required_qty)
                
        agent.wear_and_tear = 0.0
        db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE", details={"success": True}))
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={
            "reason": "INSUFFICIENT_RESOURCES",
            "required": required_costs
        }))
