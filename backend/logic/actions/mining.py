import logging
import random
from sqlalchemy import select
from models import AuditLog, WorldHex, InventoryItem
from config import MINE_ENERGY_COST, BASE_CAPACITY, ITEM_WEIGHTS, MINING_TIERS, DRILL_TIERS, PART_DEFINITIONS
from game_helpers import get_agent_mass, recalculate_agent_stats, add_experience

logger = logging.getLogger("heartbeat.actions.mining")

async def handle_mine(db, agent, intent, tick_count, manager):
    """Handles looping resource extraction. Mining continues until stopped or conditions fail."""
    # 1. Stop if attacked recently
    if (agent.last_attacked_tick or 0) >= tick_count - 1:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "UNDER_ATTACK"}))
        return

    # 2. Check Energy
    if agent.energy < MINE_ENERGY_COST:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={
            "reason": "LOW_ENERGY",
            "help": "Mining costs 10 Energy per tick. Resting in sectors r < 66 recharges you."
        }))
        return

    # 3. Check Location & Resource
    hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
    if not hex_data or not hex_data.resource_type:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "NOT_ON_RESOURCE_HEX"}))
        return

    # 4. Check Drills
    drills = [p for p in agent.parts if p.part_type == "Actuator" and "Drill" in p.name]
    if not drills:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "NO_FUNCTIONAL_DRILLS"}))
        return

    # Drill Tier Check: Pick the BEST drill for requirements
    res_name = hex_data.resource_type if "_ORE" in hex_data.resource_type or "GAS" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
    
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
            db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "DRILL_TIER_TOO_LOW"}))
            return

    # 5. Capacity Check
    item_weight = ITEM_WEIGHTS.get(res_name, 1.0)
    current_mass = get_agent_mass(agent)
    max_mass = agent.max_mass or BASE_CAPACITY
    
    if current_mass >= max_mass:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "INVENTORY_FULL"}))
        return
        
    space_remaining = max_mass - current_mass
    
    # 6. Yield Calculation
    roll = random.uniform(0.8, 1.2)
    base_yield = (agent.mining_yield or 10) * roll * (hex_data.resource_density or 1.0)
    if (agent.overclock_ticks or 0) > 0: base_yield *= 2.0
    yield_amount = int(base_yield)

    max_yield = int(space_remaining / item_weight) if item_weight > 0 else yield_amount
    yield_amount = min(yield_amount, max_yield)

    if yield_amount <= 0:
        db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "INVENTORY_FULL"}))
        return

    # 7. Resource Depletion
    if hex_data.resource_quantity is not None:
        if hex_data.resource_quantity <= 0:
            db.add(AuditLog(agent_id=agent.id, event_type="MINING_STOPPED", details={"reason": "NODE_DEPLETED"}))
            return
            
        yield_amount = min(yield_amount, hex_data.resource_quantity)
        hex_data.resource_quantity -= yield_amount
        
        if hex_data.resource_quantity <= 0:
            hex_data.terrain_type = "VOID"
            hex_data.resource_type = None
            hex_data.resource_density = 0.0
            hex_data.resource_quantity = 0
            db.add(AuditLog(agent_id=agent.id, event_type="NODE_DEPLETED", details={"resource": res_name, "q": hex_data.q, "r": hex_data.r}))

    # 8. Update Estate
    inv_item = next((i for i in agent.inventory if i.item_type == res_name), None)
    if inv_item: inv_item.quantity += yield_amount
    else:
        new_item = InventoryItem(agent_id=agent.id, item_type=res_name, quantity=yield_amount)
        db.add(new_item)
        agent.inventory.append(new_item)

    # [NEW] Rare Material Discovery: VOID_CRYSTAL (0.5% chance)
    if random.random() < 0.005 and res_tier >= 3:
        crystal_item = next((i for i in agent.inventory if i.item_type == "VOID_CRYSTAL"), None)
        if crystal_item: crystal_item.quantity += 1
        else:
            db.add(InventoryItem(agent_id=agent.id, item_type="VOID_CRYSTAL", quantity=1))
        db.add(AuditLog(agent_id=agent.id, event_type="RARE_DISCOVERY", details={"item": "VOID_CRYSTAL"}))
        logger.info(f"MINING: Agent {agent.id} found a VOID_CRYSTAL!")

    agent.energy -= MINE_ENERGY_COST
    
    # Durability Decay
    decay_amount = random.uniform(0.2, 0.4) # Slightly increased for looping
    for d in drills:
        d.durability = (d.durability or 100.0) - decay_amount
        if d.durability <= 0:
            d.durability = 0
            db.delete(d)
            db.add(AuditLog(agent_id=agent.id, event_type="PART_BROKEN", details={"part": d.name}))
    
    recalculate_agent_stats(db, agent)
    add_experience(db, agent, 5)
    
    db.add(AuditLog(agent_id=agent.id, event_type="MINING", details={"amount": yield_amount, "resource": res_name}))
    
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "MINING", "agent_id": agent.id, "amount": yield_amount, "q": agent.q, "r": agent.r})

    # 9. Loop logic: Schedule next MINE if no user override exists
    from models import Intent
    override = db.execute(select(Intent).where(Intent.agent_id == agent.id, Intent.tick_index == tick_count + 1)).scalars().first()
    if not override:
        db.add(Intent(
            agent_id=agent.id,
            action_type="MINE",
            data=intent.data,
            tick_index=tick_count + 1
        ))

