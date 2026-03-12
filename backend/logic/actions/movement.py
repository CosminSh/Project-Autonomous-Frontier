import logging
from sqlalchemy import select
from models import Intent, AuditLog, WorldHex
from config import MOVE_ENERGY_COST, BASE_CAPACITY
from game_helpers import get_hex_distance, find_hex_path, get_agent_mass, wrap_coords

logger = logging.getLogger("heartbeat.actions.movement")

def handle_stop(db, agent, intent, tick_count):
    """Cancels all present and future queued intents for this agent."""
    future_intents = db.execute(select(Intent).where(
        Intent.agent_id == agent.id,
        Intent.tick_index >= tick_count
    )).scalars().all()
    to_cancel = [fi for fi in future_intents if fi.id != intent.id]
    cancelled_count = len(to_cancel)
    for fi in to_cancel:
        db.delete(fi)
    
    logger.info(f"Agent {agent.id} STOP: cancelled {cancelled_count} queued intents")
    db.add(AuditLog(agent_id=agent.id, event_type="STOP", details={
        "cancelled": cancelled_count,
        "note": "All queued actions cleared."
    }))

async def handle_move(db, agent, intent, tick_count, manager):
    """Handles agent movement, including long-distance pathfinding."""
    target_q, target_r = wrap_coords(intent.data.get("target_q"), intent.data.get("target_r"))

    # Already at destination — no-op
    if target_q == agent.q and target_r == agent.r:
        return

    # Map bound check - ensure the hex is seeded
    target_hex = db.execute(select(WorldHex).where(WorldHex.q == target_q, WorldHex.r == target_r)).scalar_one_or_none()
    if not target_hex:
        # In a finite wrap world, missing hexes should not happen if pre-seeded.
        # However, we allow "ghost" targets if we want, but better to check obstacle.
        db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={"reason": "OUT_OF_BOUNDS", "help": "Target coordinates are not initialized."}))
        return

    dist = get_hex_distance(agent.q, agent.r, target_q, target_r)
    max_dist = 3 if (agent.overclock_ticks or 0) > 0 else 1

    if dist > max_dist:
        # --- Long-distance: BFS pathfinding → queue per-tick MOVE chain ---
        path = find_hex_path(db, agent.q, agent.r, target_q, target_r)
        if path is None:
            db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
                "reason": "NO_PATH",
                "target": {"q": target_q, "r": target_r},
                "help": "No navigable route found."
            }))
            return
            
        # Overwrite any previously queued nav MOVE intents
        old_nav = db.execute(select(Intent).where(
            Intent.agent_id == agent.id,
            Intent.tick_index > tick_count,
            Intent.action_type == "MOVE"
        )).scalars().all()
        for old in old_nav:
            db.delete(old)
            
        # Queue each step in consecutive future ticks
        for i, (sq, sr) in enumerate(path):
            db.add(Intent(
                agent_id=agent.id,
                action_type="MOVE",
                data={"target_q": sq, "target_r": sr, "_nav": True},
                tick_index=tick_count + i + 1
            ))
            
        db.add(AuditLog(agent_id=agent.id, event_type="NAVIGATE_QUEUED", details={
            "steps": len(path),
            "destination": {"q": target_q, "r": target_r}
        }))
        logger.info(f"Agent {agent.id} NAVIGATE: {len(path)}-step path queued")
        return

    # --- Single-step move ---
    current_mass = get_agent_mass(agent)
    max_mass = agent.max_mass or BASE_CAPACITY
    
    # Base cost + sum of specialized part drain (Turbo Engines, etc.)
    drain = sum(p.stats.get("energy_cost", 0) for p in agent.parts if p.stats)
    energy_cost = MOVE_ENERGY_COST + drain

    if current_mass > max_mass:
        energy_cost *= (current_mass / max_mass)

    if agent.energy < energy_cost:
        db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
            "reason": "INSUFFICIENT_ENERGY",
            "help": "Move costs 5 energy. Latitude r < 66 is sunny — idle in the sun to recharge."
        }))
        return

    if not target_hex or target_hex.terrain_type == "OBSTACLE":
        db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={"reason": "OBSTACLE" if target_hex else "OUT_OF_BOUNDS"}))
        return

    agent.q, agent.r = target_q, target_r
    agent.energy -= energy_cost
    db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT", details={"q": target_q, "r": target_r}))
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "MOVE", "agent_id": agent.id, "q": target_q, "r": target_r})
