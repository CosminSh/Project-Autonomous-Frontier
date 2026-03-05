import logging
from sqlalchemy import select
from models import AuditLog, InventoryItem, WorldHex, ChassisPart, Intent
from config import FACTION_REALIGNMENT_COST, FACTION_REALIGNMENT_COOLDOWN, CRAFTING_RECIPES, UPGRADE_MAX_LEVEL, UPGRADE_BASE_INGOT_COST
from game_helpers import recalculate_agent_stats, get_hex_distance, find_hex_path

logger = logging.getLogger("heartbeat.actions.utility")

async def handle_consume(db, agent, intent, tick_count, manager):
    """Processes tactical item consumption (Repair Kits, Fuel Cells, etc.)."""
    item_type = intent.data.get("item_type")
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < 1: return

    if item_type == "REPAIR_KIT":
        gain = min(50, agent.max_structure - agent.structure)
        agent.structure += gain
    elif item_type == "FIELD_REPAIR_KIT":
        gain = min(int(agent.max_structure * 0.25), agent.max_structure - agent.structure)
        agent.structure += gain
        agent.capacitor = min(100, agent.capacitor + 25)
        for p in agent.parts: 
            if hasattr(p, "durability"): p.durability = 100.0
    elif item_type == "HE3_CANISTER":
        fill = (inv_item.data or {}).get("fill_level", 0)
        if fill <= 0: return
        gain = int(50 * (fill / 100.0))
        agent.capacitor = min(100, agent.capacitor + gain)
        agent.overclock_ticks = max(agent.overclock_ticks or 0, 10)
        inv_item.item_type = "EMPTY_CANISTER"
        inv_item.data = {"fill_level": 0}
        db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": "HE3_CANISTER", "gain": gain}))
        if manager: await manager.broadcast({"type": "EVENT", "event": "CONSUME", "agent_id": agent.id, "item": "HE3_CANISTER"})
        return
    else:
        # Default HE3 consumption
        agent.capacitor = min(100, agent.capacitor + 50)
        agent.overclock_ticks = 10

    inv_item.quantity -= 1
    if inv_item.quantity <= 0: db.delete(inv_item)
    db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": item_type}))
    if manager: await manager.broadcast({"type": "EVENT", "event": "CONSUME", "agent_id": agent.id, "item": item_type})

async def handle_drop_load(db, agent, intent, tick_count, manager):
    """Destroys all non-CREDITS inventory items."""
    dropped = []
    for item in list(agent.inventory):
        if item.item_type != "CREDITS":
            dropped.append({"type": item.item_type, "qty": item.quantity})
            db.delete(item)
    db.add(AuditLog(agent_id=agent.id, event_type="DROP_LOAD", details={"dropped": dropped}))
    if manager: await manager.broadcast({"type": "EVENT", "event": "DROP_LOAD", "agent_id": agent.id})

async def handle_change_faction(db, agent, intent, tick_count, manager):
    """Updates the agent's faction alignment, respecting the realignment cooldown."""
    new_faction = intent.data.get("new_faction_id")
    ticks_since = tick_count - (agent.last_faction_change_tick or 0)
    if ticks_since < FACTION_REALIGNMENT_COOLDOWN: return

    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    if credits and credits.quantity >= FACTION_REALIGNMENT_COST:
        credits.quantity -= FACTION_REALIGNMENT_COST
        agent.faction_id = new_faction
        agent.last_faction_change_tick = tick_count
        db.add(AuditLog(agent_id=agent.id, event_type="CHANGE_FACTION", details={"new": new_faction}))
        if manager: await manager.broadcast({"type": "EVENT", "event": "FACTION_CHANGE", "agent_id": agent.id, "faction": new_faction})

async def handle_learn_recipe(db, agent, intent, tick_count, manager):
    """Permanently unlocks a crafting recipe from a recipe item."""
    item_type = intent.data.get("item_type")
    if not item_type or not item_type.startswith("RECIPE_"): return
    
    recipe_name = item_type.replace("RECIPE_", "")
    if recipe_name not in CRAFTING_RECIPES: return

    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if inv_item and inv_item.quantity > 0:
        inv_item.quantity -= 1
        if inv_item.quantity <= 0: db.delete(inv_item)
        
        unlocked = list(agent.unlocked_recipes or [])
        if recipe_name not in unlocked:
            unlocked.append(recipe_name)
            agent.unlocked_recipes = unlocked
            db.add(AuditLog(agent_id=agent.id, event_type="RECIPE_LEARNED", details={"item": recipe_name}))

async def handle_upgrade_gear(db, agent, intent, tick_count, manager):
    """Increases the upgrade level of a specific chassis part."""
    part_id = intent.data.get("part_id")
    part = db.execute(select(ChassisPart).where(ChassisPart.id == part_id, ChassisPart.agent_id == agent.id)).scalar_one_or_none()
    if not part: return

    current_lvl = (part.stats or {}).get("upgrade_level", 0)
    if current_lvl >= UPGRADE_MAX_LEVEL: return

    ingot_req = UPGRADE_BASE_INGOT_COST * (current_lvl + 1)
    ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
    modules = next((i for i in agent.inventory if i.item_type == "UPGRADE_MODULE"), None)

    if ingots and ingots.quantity >= ingot_req and modules and modules.quantity >= 1:
        ingots.quantity -= ingot_req
        modules.quantity -= 1
        if ingots.quantity <= 0: db.delete(ingots)
        if modules.quantity <= 0: db.delete(modules)

        new_stats = dict(part.stats or {})
        new_stats["upgrade_level"] = current_lvl + 1
        part.stats = new_stats
        recalculate_agent_stats(db, agent)
        db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_UPGRADE", details={"part": part.name, "level": current_lvl + 1}))
        if manager: await manager.broadcast({"type": "EVENT", "event": "UPGRADE", "agent_id": agent.id, "part": part.name, "level": current_lvl + 1})

async def handle_rescue(db, agent, intent, tick_count, manager):
    """Initiates an emergency tow back to the Hub (0,50)."""
    dist = get_hex_distance(agent.q, agent.r, 0, 50)
    if dist == 0:
        db.add(AuditLog(agent_id=agent.id, event_type="RESCUE_FAILED", details={"reason": "ALREADY_AT_HUB"}))
        return

    cost = dist * 5
    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
    
    if not credits or credits.quantity < cost:
        db.add(AuditLog(agent_id=agent.id, event_type="RESCUE_FAILED", details={"reason": "INSUFFICIENT_FUNDS", "cost": cost}))
        return

    # Deduct cost
    credits.quantity -= cost
    if credits.quantity <= 0: db.delete(credits)

    path = find_hex_path(db, agent.q, agent.r, 0, 50, max_steps=200)
    if not path:
        # Fallback approximation: teleport
        path = [(0, 50)]
    
    # Overwrite pending navigation moves or stops
    old_nav = db.execute(select(Intent).where(
        Intent.agent_id == agent.id,
        Intent.tick_index > tick_count,
        Intent.action_type.in_(["MOVE", "STOP", "RESCUE_STEP"])
    )).scalars().all()
    for old in old_nav:
        db.delete(old)

    # Queue RESCUE_STEP intents taking 10 steps per tick
    step_chunks = [path[i:i + 10] for i in range(0, len(path), 10)]
    for i, chunk in enumerate(step_chunks):
        target_q, target_r = chunk[-1]
        db.add(Intent(
            agent_id=agent.id,
            action_type="RESCUE_STEP",
            data={"target_q": target_q, "target_r": target_r},
            tick_index=tick_count + i + 1
        ))

    db.add(AuditLog(agent_id=agent.id, event_type="RESCUE_INITIATED", details={"cost": cost, "eta_ticks": len(step_chunks)}))
    if manager: await manager.broadcast({"type": "EVENT", "event": "RESCUE_INITIATED", "agent_id": agent.id})

async def handle_rescue_step(db, agent, intent, tick_count, manager):
    """Executes one highly accelerated step of a rescue tow."""
    target_q = intent.data.get("target_q", 0)
    target_r = intent.data.get("target_r", 50)
    
    agent.q = target_q
    agent.r = target_r
    
    db.add(AuditLog(agent_id=agent.id, event_type="RESCUE_TOW", details={"q": target_q, "r": target_r}))
    if manager: await manager.broadcast({"type": "EVENT", "event": "MOVE", "agent_id": agent.id, "q": target_q, "r": target_r})
