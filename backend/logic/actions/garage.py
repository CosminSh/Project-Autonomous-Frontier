import logging
from sqlalchemy import select
from models import AuditLog, InventoryItem, ChassisPart
from config import PART_DEFINITIONS
from game_helpers import recalculate_agent_stats

logger = logging.getLogger("heartbeat.actions.garage")

async def handle_equip(db, agent, intent, tick_count, manager):
    """Moves a part from inventory to the agent's chassis."""
    item_type = intent.data.get("item_type")
    if not item_type: return

    # Normalize item_type
    if not item_type.startswith("PART_") and item_type in PART_DEFINITIONS:
        item_type = f"PART_{item_type}"
    
    base_key = item_type.replace("PART_", "")
    part_def = PART_DEFINITIONS.get(base_key)
    if not part_def:
        db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={"reason": "INVALID_PART", "item": item_type}))
        return

    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    if not inv_item or inv_item.quantity < 1:
        db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={"reason": "NOT_IN_INVENTORY", "item": item_type}))
        return

    # Modular Slot Limits based on Frame
    from config import FRAME_SLOT_LIMITS
    
    # 1. Identify equipped frame
    equipped_frame = next((p for p in agent.parts if p.part_type == "Frame"), None)
    
    # 2. Get limits for that frame (or DEFAULT)
    frame_key = "DEFAULT"
    if equipped_frame:
        # Map frame name back to config key
        frame_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == equipped_frame.name), "DEFAULT")
    
    current_limits = FRAME_SLOT_LIMITS.get(frame_key, FRAME_SLOT_LIMITS["DEFAULT"])
    part_type = part_def["type"]
    limit = current_limits.get(part_type, 1)
    
    # Frame swap is special: if equipping a Frame, it REPLACES the old one (if any)
    if part_type == "Frame" and equipped_frame:
        # Move old frame to inventory (handled by handle_equip callers or we do it here)
        # For now, we allow the equip to proceed if they have 0 or exactly 1 frame.
        # But if they are swapping, we should unequip first or support replacement.
        # To avoid complexity, let's keep the standard "Must unequip first" logic if limit is 1.
        pass

    current_parts = [p for p in agent.parts if p.part_type == part_type]
    if len(current_parts) >= limit:
        db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={"reason": "SLOTS_FULL", "type": part_type}))
        return

    # Equip
    new_part = ChassisPart(
        agent_id=agent.id,
        part_type=part_type,
        name=part_def["name"],
        rarity=(inv_item.data or {}).get("rarity", "STANDARD"),
        stats=(inv_item.data or {}).get("stats", part_def.get("stats", {})),
        durability=(inv_item.data or {}).get("durability", 100.0)
    )
    db.add(new_part)
    
    # Remove from inventory
    inv_item.quantity -= 1
    if inv_item.quantity <= 0:
        db.delete(inv_item)
        
    db.flush()
    recalculate_agent_stats(db, agent)
    db.add(AuditLog(agent_id=agent.id, event_type="EQUIP", details={"part": new_part.name}))
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "EQUIP", "agent_id": agent.id, "part": new_part.name})

async def handle_unequip(db, agent, intent, tick_count, manager):
    """Moves a part from the chassis back to the inventory."""
    part_id = intent.data.get("part_id")
    part = next((p for p in agent.parts if p.id == part_id), None)
    
    if not part:
        db.add(AuditLog(agent_id=agent.id, event_type="UNEQUIP_FAILED", details={"reason": "PART_NOT_FOUND"}))
        return

    # Logic: Basic drills/panels cannot be unequipped if it would leave the agent empty?
    # For now, allow it all.
    
    # Check if part name maps back to a config key
    config_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == part.name), None)
    
    # Fallback to stat matching if name was changed in a patch
    if not config_key:
        matches = [k for k, v in PART_DEFINITIONS.items() if v["type"] == part.part_type and v.get("stats", {}) == (part.stats or {})]
        if matches: config_key = matches[0]
        
    # Hardcoded fallback for known old names
    if not config_key:
        old_mapping = {"Titanium Drill": "DRILL_UNIT", "Titanium Frame": "BASIC_FRAME"}
        config_key = old_mapping.get(part.name)

    item_type = f"PART_{config_key}" if config_key else "SCRAP_METAL"
    
    # Move to inventory
    inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
    item_data = {"rarity": part.rarity, "stats": part.stats, "durability": part.durability}
    
    if inv_item:
        # If stackable, we might lose data. But parts shouldn't be stackable unless identical.
        # For now, we create new record if data differs
        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
    else:
        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
        
    db.delete(part)
    db.flush()
    recalculate_agent_stats(db, agent)
    db.add(AuditLog(agent_id=agent.id, event_type="UNEQUIP", details={"part": part.name}))
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "UNEQUIP", "agent_id": agent.id, "part": part.name})
