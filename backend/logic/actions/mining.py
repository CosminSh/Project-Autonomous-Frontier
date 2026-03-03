import logging
import random
from sqlalchemy import select
from models import AuditLog, WorldHex, InventoryItem
from config import MINE_ENERGY_COST, BASE_CAPACITY, ITEM_WEIGHTS, MINING_TIERS, DRILL_TIERS, PART_DEFINITIONS
from game_helpers import get_agent_mass, recalculate_agent_stats, add_experience

logger = logging.getLogger("heartbeat.actions.mining")

async def handle_mine(db, agent, intent, tick_count, manager):
    """Handles resource extraction, including drill tier checks and capacity validation."""
    if agent.capacitor < MINE_ENERGY_COST:
        return

    hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_data or not hex_data.resource_type:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "NOT_ON_RESOURCE_HEX"}))
        return

    active_drill = next((p for p in agent.parts if p.part_type == "Actuator" and "Drill" in p.name), None)
    if not active_drill:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "MISSING_DRILL"}))
        return

    # Drill Tier Check
    res_name = hex_data.resource_type if "_ORE" in hex_data.resource_type or "GAS" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
    part_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == active_drill.name), "DRILL_UNIT")
    
    if "GAS" in res_name and not any(p.part_type == "Actuator" and "Siphon" in p.name for p in agent.parts):
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "MISSING_GAS_SIPHON"}))
        return

    if "GAS" not in res_name:
        res_tier = MINING_TIERS.get(res_name, {"tier": 1})["tier"]
        drill_info = DRILL_TIERS.get(part_key, {"tier": 1, "advanced": False})
        drill_tier = drill_info["tier"]
        is_advanced = drill_info["advanced"]
        
        if res_tier > drill_tier and not (is_advanced and res_tier == drill_tier + 1):
            db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "DRILL_TIER_TOO_LOW"}))
            return

    # Yield Calculation
    roll = random.randint(1, 10)
    base_yield = (roll + ((agent.kinetic_force or 10) / 2)) * (hex_data.resource_density or 1.0)
    if (agent.overclock_ticks or 0) > 0: base_yield *= 2.0
    yield_amount = int(base_yield)

    # Capacity Check
    item_weight = ITEM_WEIGHTS.get(res_name, 1.0)
    current_mass = get_agent_mass(agent)
    max_mass = agent.max_mass or BASE_CAPACITY
    
    if current_mass >= max_mass:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "CARGO_FULL"}))
        return
        
    space_remaining = max_mass - current_mass
    max_yield = int(space_remaining / item_weight) if item_weight > 0 else yield_amount
    yield_amount = min(yield_amount, max_yield)

    if yield_amount <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "CARGO_FULL"}))
        return

    # Update Inventory
    inv_item = next((i for i in agent.inventory if i.item_type == res_name), None)
    if inv_item: inv_item.quantity += yield_amount
    else:
        new_item = InventoryItem(agent_id=agent.id, item_type=res_name, quantity=yield_amount)
        db.add(new_item)
        agent.inventory.append(new_item)

    agent.capacitor -= MINE_ENERGY_COST
    
    # Durability Decay
    active_drill.durability = (active_drill.durability or 100.0) - random.uniform(0.1, 0.3)
    if active_drill.durability <= 0:
        active_drill.durability = 0
        db.delete(active_drill)
        recalculate_agent_stats(db, agent)
        db.add(AuditLog(agent_id=agent.id, event_type="PART_BROKEN", details={"part": active_drill.name}))

    db.add(AuditLog(agent_id=agent.id, event_type="MINING", details={"amount": yield_amount, "resource": res_name}))
    add_experience(db, agent, 5)
    
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "MINING", "agent_id": agent.id, "amount": yield_amount, "q": agent.q, "r": agent.r})
