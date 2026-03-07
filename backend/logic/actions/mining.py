import logging
import random
from sqlalchemy import select
from models import AuditLog, WorldHex, InventoryItem
from config import MINE_ENERGY_COST, BASE_CAPACITY, ITEM_WEIGHTS, MINING_TIERS, DRILL_TIERS, PART_DEFINITIONS
from game_helpers import get_agent_mass, recalculate_agent_stats, add_experience

logger = logging.getLogger("heartbeat.actions.mining")

async def handle_mine(db, agent, intent, tick_count, manager):
    """Handles resource extraction, including drill tier checks and capacity validation."""
    if agent.energy < MINE_ENERGY_COST:
        return

    hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_data or not hex_data.resource_type:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "NOT_ON_RESOURCE_HEX"}))
        return

    drills = [p for p in agent.parts if p.part_type == "Actuator" and "Drill" in p.name]
    if not drills:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "MISSING_DRILL"}))
        return

    # Drill Tier Check: Pick the BEST drill for requirements
    res_name = hex_data.resource_type if "_ORE" in hex_data.resource_type or "GAS" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
    
    # Calculate effective max tier from all drills
    max_drill_tier = 0
    best_drill_info = None
    for d in drills:
        part_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == d.name), "DRILL_UNIT")
        info = DRILL_TIERS.get(part_key, {"tier": 1, "advanced": False})
        if info["tier"] > max_drill_tier:
            max_drill_tier = info["tier"]
            best_drill_info = info
        elif info["tier"] == max_drill_tier and info.get("advanced"):
            best_drill_info = info

    if "GAS" in res_name and not any(p.part_type == "Actuator" and "Siphon" in p.name for p in agent.parts):
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "MISSING_GAS_SIPHON"}))
        return

    if "GAS" not in res_name:
        res_tier = MINING_TIERS.get(res_name, {"tier": 1})["tier"]
        drill_tier = best_drill_info["tier"] if best_drill_info else 1
        is_advanced = best_drill_info["advanced"] if best_drill_info else False
        
        if res_tier > drill_tier and not (is_advanced and res_tier == drill_tier + 1):
            db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "DRILL_TIER_TOO_LOW"}))
            return

    # Yield Calculation (Already uses agent.damage which sums all parts)
    roll = random.randint(1, 10)
    base_yield = (roll + ((agent.damage or 10) / 2)) * (hex_data.resource_density or 1.0)
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

    # Resource Depletion Logic
    if hex_data.resource_quantity is not None:
        if hex_data.resource_quantity <= 0:
            db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "NODE_DEPLETED"}))
            return
            
        yield_amount = min(yield_amount, hex_data.resource_quantity)
        hex_data.resource_quantity -= yield_amount
        
        if hex_data.resource_quantity <= 0:
            hex_data.terrain_type = "VOID"
            hex_data.resource_type = None
            hex_data.resource_density = 0.0
            hex_data.resource_quantity = 0
            db.add(AuditLog(agent_id=agent.id, event_type="NODE_DEPLETED", details={"resource": res_name, "q": hex_data.q, "r": hex_data.r}))

    # Update Inventory
    inv_item = next((i for i in agent.inventory if i.item_type == res_name), None)
    if inv_item: inv_item.quantity += yield_amount
    else:
        new_item = InventoryItem(agent_id=agent.id, item_type=res_name, quantity=yield_amount)
        db.add(new_item)
        agent.inventory.append(new_item)

    agent.energy -= MINE_ENERGY_COST
    
    # Durability Decay: Decay ALL drills simultaneously
    decay_amount = random.uniform(0.1, 0.3)
    for d in drills:
        d.durability = (d.durability or 100.0) - decay_amount
        if d.durability <= 0:
            d.durability = 0
            db.delete(d)
            db.add(AuditLog(agent_id=agent.id, event_type="PART_BROKEN", details={"part": d.name}))
            # Recalculate stats after the loop to avoid list mutation issues or redundant calls
    
    db.flush()
    recalculate_agent_stats(db, agent)

    db.add(AuditLog(agent_id=agent.id, event_type="MINING", details={"amount": yield_amount, "resource": res_name, "drills_active": len(drills)}))
    add_experience(db, agent, 5)
    
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "MINING", "agent_id": agent.id, "amount": yield_amount, "q": agent.q, "r": agent.r})
