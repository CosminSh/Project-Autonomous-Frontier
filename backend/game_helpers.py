"""
game_helpers.py — Pure utility functions used across multiple modules.
Depends on: config.py, models.py, database.py
"""
import logging
from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import select

import json
from models import Agent, WorldHex, ChassisPart, InventoryItem, AuditLog
from config import (
    ITEM_WEIGHTS, BASE_CAPACITY, RARITY_LEVELS, PART_DEFINITIONS,
    SOLAR_RADIUS_SAFE, SOLAR_RADIUS_TWILIGHT, ANARCHY_THRESHOLD,
    BASE_REGEN, CLUTTER_PENALTY
)

logger = logging.getLogger("heartbeat")


# ─────────────────────────────────────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────────────────────────────────────

def get_hex_distance(q1, r1, q2, r2) -> int:
    """Calculates distance on a cube/axial hex grid."""
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2


def is_in_anarchy_zone(q, r) -> bool:
    """Checks if coordinates are outside the colonial safe zone."""
    return get_hex_distance(q, r, 0, 0) >= ANARCHY_THRESHOLD


def get_solar_intensity(q, r, tick_count=0) -> float:
    """Calculates solar power intensity (0.0 to 1.0) based on latitude (r)."""
    dist_r = abs(r)
    if dist_r <= SOLAR_RADIUS_SAFE:
        return 1.0
    if dist_r <= SOLAR_RADIUS_TWILIGHT:
        day_night_cycle = (tick_count // 30) % 2 == 0
        return 1.0 if day_night_cycle else 0.0
    return 0.0


def find_hex_path(db: Session, sq: int, sr: int, gq: int, gr: int, max_steps: int = 50):
    """BFS pathfinding on the axial hex grid. Returns list of (q,r) steps or None."""
    if sq == gq and sr == gr:
        return []
    NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
    obstacles = set(
        (h.q, h.r) for h in db.execute(
            select(WorldHex).where(WorldHex.terrain_type == "OBSTACLE")
        ).scalars().all()
    )
    queue = deque([(sq, sr, [])])
    visited = {(sq, sr)}
    while queue:
        q, r, path = queue.popleft()
        if q == gq and r == gr:
            return path
        if len(path) >= max_steps:
            continue
        for dq, dr in NEIGHBORS:
            nq, nr = q + dq, r + dr
            if (nq, nr) not in visited and (nq, nr) not in obstacles:
                visited.add((nq, nr))
                queue.append((nq, nr, path + [(nq, nr)]))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Agent Stats & Gear
# ─────────────────────────────────────────────────────────────────────────────

def get_agent_mass(agent: Agent) -> float:
    """Calculates total mass of agent's inventory."""
    return sum(
        ITEM_WEIGHTS.get(item.item_type, 1.0) * item.quantity
        for item in agent.inventory
    )


def recalculate_agent_stats(db: Session, agent: Agent):
    """Resets and recalculates agent stats based on equipped parts."""
    agent.max_structure = 100
    agent.kinetic_force = 10
    agent.logic_precision = 10
    agent.overclock = 10
    agent.integrity = 5
    agent.max_mass = BASE_CAPACITY

    for part in agent.parts:
        base_stats = part.stats or {}
        rarity = part.rarity or "STANDARD"
        rarity_data = RARITY_LEVELS.get(rarity, RARITY_LEVELS["STANDARD"])
        multiplier = rarity_data["multiplier"]

        agent.max_structure += int(base_stats.get("max_structure", 0) * multiplier)
        agent.kinetic_force += int(base_stats.get("kinetic_force", 0) * multiplier)
        agent.logic_precision += int(base_stats.get("logic_precision", 0) * multiplier)
        agent.overclock += int(base_stats.get("overclock", 0) * multiplier)
        agent.integrity += int(base_stats.get("integrity", 0) * multiplier)
        agent.max_mass += int(base_stats.get("capacity", 0) * multiplier)

        upgrade_lvl = part.stats.get("upgrade_level", 0) if part.stats else 0
        if upgrade_lvl > 0:
            boost = 1.0 + (upgrade_lvl * 0.1)
            agent.max_structure = int(agent.max_structure * boost)
            agent.kinetic_force = int(agent.kinetic_force * boost)
            agent.logic_precision = int(agent.logic_precision * boost)
            agent.overclock = int(agent.overclock * boost)
            agent.integrity = int(agent.integrity * boost)

        affixes = part.affixes or {}
        for affix_name, stat_bonuses in affixes.items():
            if isinstance(stat_bonuses, dict):
                for stat_name, bonus in stat_bonuses.items():
                    if hasattr(agent, stat_name):
                        current_val = getattr(agent, stat_name) or 0
                        setattr(agent, stat_name, current_val + bonus)
                    elif stat_name == "capacity":
                        agent.max_mass = (agent.max_mass or BASE_CAPACITY) + bonus

    wear = agent.wear_and_tear or 0.0
    if wear > 50.0:
        penalty_factor = max(0.2, 1.0 - ((wear - 50.0) / 100.0))
        agent.kinetic_force = int(agent.kinetic_force * penalty_factor)
        agent.logic_precision = int(agent.logic_precision * penalty_factor)
        logger.info(f"Agent {agent.id} Wear & Tear penalty: {penalty_factor:.2f}x")

    if agent.structure > agent.max_structure:
        agent.structure = agent.max_structure

    db.flush()


def ensure_agent_has_starter_gear(db: Session, agent: Agent):
    """Bootstrap: Ensures agents have essential gear (Drill and Solar Panel)."""
    has_drill = any(p.part_type == "Actuator" for p in agent.parts)
    has_power = any(p.part_type == "Power" for p in agent.parts)

    dirty = False
    if not has_drill:
        logger.info(f"Bootstrap: Equipping starter drill for Agent {agent.id}")
        drill_def = PART_DEFINITIONS["DRILL_IRON_BASIC"]
        db.add(ChassisPart(agent_id=agent.id, part_type=drill_def["type"], name=drill_def["name"], stats=drill_def["stats"]))
        dirty = True

    if not has_power:
        logger.info(f"Bootstrap: Equipping starter solar panel for Agent {agent.id}")
        panel_def = PART_DEFINITIONS["SCRAP_SOLAR_PANEL"]
        db.add(ChassisPart(agent_id=agent.id, part_type=panel_def["type"], name=panel_def["name"], stats=panel_def["stats"]))
        dirty = True

    if dirty:
        db.commit()
        db.refresh(agent)
        recalculate_agent_stats(db, agent)
        db.commit()


def get_agent_visual_signature(agent: Agent) -> dict:
    """Computes a visual signature based on equipped gear for frontend rendering."""
    signature = {"chassis": "BASIC", "actuator": None, "rarity": "STANDARD"}
    highest_rarity_score = 0
    rarity_map = {"SCRAP": 1, "STANDARD": 2, "REFINED": 3, "PRIME": 4, "RELIC": 5}

    for part in agent.parts:
        name_str = (part.name or "").lower()
        if part.part_type == "Frame":
            if "aegis" in name_str or "shield" in name_str:
                signature["chassis"] = "SHIELDED"
            elif "heavy" in name_str or "titan" in name_str:
                signature["chassis"] = "HEAVY"
        if part.part_type == "Actuator":
            if "drill" in name_str:
                signature["actuator"] = "DRILL"
            elif "blaster" in name_str or "laser" in name_str:
                signature["actuator"] = "WEAPON"
        p_rarity = part.rarity or "STANDARD"
        score = rarity_map.get(p_rarity, 2)
        if score > highest_rarity_score:
            highest_rarity_score = score
            signature["rarity"] = p_rarity

    return signature


# ─────────────────────────────────────────────────────────────────────────────
# Station Discovery
# ─────────────────────────────────────────────────────────────────────────────

def get_nearest_station(station_cache: list, agent: Agent, station_type: str):
    """Returns the nearest station dict of a specific type from cache."""
    relevant = [s for s in station_cache if s["station_type"] == station_type]
    if not relevant:
        return None
    return min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s["q"], s["r"]))


def get_discovery_packet(station_cache: list, agent: Agent) -> dict:
    """Returns nearest locations of public service stations from cache."""
    discovery = {}
    for st in ["MARKET", "SMELTER", "CRAFTER", "REPAIR", "REFINERY"]:
        relevant = [s for s in station_cache if s["station_type"] == st]
        if relevant:
            nearest = min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s["q"], s["r"]))
            dist = get_hex_distance(agent.q, agent.r, nearest["q"], nearest["r"])
            discovery[st] = {"q": nearest["q"], "r": nearest["r"], "distance": dist}
            
    from config import CRAFTING_RECIPES, SMELTING_RECIPES, PART_DEFINITIONS, ITEM_WEIGHTS, CORE_RECIPES
    
    enriched_crafting = []
    for item_key, materials in CRAFTING_RECIPES.items():
        is_part = item_key in PART_DEFINITIONS
        part_data = PART_DEFINITIONS.get(item_key, {})
        
        # Calculate resulting item type for weight lookup
        inventory_type = f"PART_{item_key}" if is_part else item_key
        
        enriched_crafting.append({
            "id": item_key,
            "name": part_data.get("name", item_key.replace("_", " ").title()),
            "type": part_data.get("type", "Material"),
            "materials": materials,
            "stats": part_data.get("stats", {}),
            "weight": ITEM_WEIGHTS.get(inventory_type, 1.0),
            "is_core": item_key in CORE_RECIPES
        })
        
    discovery["crafting_recipes"] = enriched_crafting
    discovery["smelting_recipes"] = SMELTING_RECIPES
    return discovery


def merge_inventory(db: Session, agent: Agent):
    """Merges duplicate inventory items of the same type and meta (data)."""
    seen = {}  # (item_type, meta_key) -> item
    to_delete = []

    # Use a copy to avoid modification issues during iteration
    inv_copy = list(agent.inventory)

    for item in inv_copy:
        # Stabilize JSON to ensure keys are in same order for comparison
        meta_key = json.dumps(item.data, sort_keys=True) if item.data else ""
        key = (item.item_type, meta_key)

        if key in seen:
            existing = seen[key]
            existing.quantity += (item.quantity or 0)
            to_delete.append(item)
        else:
            seen[key] = item

    for item in to_delete:
        db.delete(item)
        if item in agent.inventory:
            agent.inventory.remove(item)

def add_experience(db: Session, agent: Agent, amount: int):
    """Adds experience to an agent and handles level ups."""
    if not hasattr(agent, "experience"):
        return
    agent.experience = (agent.experience or 0) + amount
    
    while True:
        level = agent.level or 1
        # Level 1 needs 100 XP, Level 2 needs 300 XP, Level 3 needs 600 XP (Cumulative)
        xp_required = int((level * (level + 1) / 2) * 100)
        
        if agent.experience >= xp_required:
            agent.level = level + 1
            agent.structure = agent.max_structure
            db.add(AuditLog(agent_id=agent.id, event_type="LEVEL_UP", details={"new_level": agent.level}))
            logger.info(f"Agent {agent.id} leveled up to {agent.level}!")
        else:
            break


