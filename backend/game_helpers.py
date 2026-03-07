"""
game_helpers.py — Pure utility functions used across multiple modules.
Depends on: config.py, models.py, database.py
"""
import logging
from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import select

import json
import random
from models import Agent, WorldHex, ChassisPart, InventoryItem, AuditLog, Sector
from config import (
    ITEM_WEIGHTS, BASE_CAPACITY, RARITY_LEVELS, PART_DEFINITIONS,
    SOLAR_RADIUS_SAFE, SOLAR_RADIUS_TWILIGHT, ANARCHY_THRESHOLD,
    BASE_REGEN, CLUTTER_PENALTY,
    CRAFTING_RECIPES, SMELTING_RECIPES, CORE_RECIPES,
    WORLD_WIDTH, WORLD_HEIGHT, MAP_MIN_Q, MAP_MAX_Q, MAP_MIN_R, MAP_MAX_R
)

logger = logging.getLogger("heartbeat")

# ─────────────────────────────────────────────────────────────────────────────
# Module-level Recipe & Bounds Cache
# Built once at startup; reused on every /api/my_agent poll to avoid
# creating hundreds of temporary dicts/lists per request.
# ─────────────────────────────────────────────────────────────────────────────
_WORLD_BOUNDS = None

def get_world_bounds(db: Session):
    global _WORLD_BOUNDS
    if _WORLD_BOUNDS is None:
        from sqlalchemy import func
        res = db.execute(select(func.min(WorldHex.q), func.max(WorldHex.q), func.min(WorldHex.r), func.max(WorldHex.r))).first()
        if res and res[0] is not None:
            _WORLD_BOUNDS = {"min_q": res[0], "max_q": res[1], "min_r": res[2], "max_r": res[3]}
        else:
            _WORLD_BOUNDS = {"min_q": -40, "max_q": 59, "min_r": -40, "max_r": 59}
    return _WORLD_BOUNDS

def _build_recipe_cache() -> list:
    result = []
    for item_key, materials in CRAFTING_RECIPES.items():
        is_part = item_key in PART_DEFINITIONS
        part_data = PART_DEFINITIONS.get(item_key, {})
        inventory_type = f"PART_{item_key}" if is_part else item_key
        result.append({
            "id": item_key,
            "name": part_data.get("name", item_key.replace("_", " ").title()),
            "type": part_data.get("type", "Material"),
            "materials": materials,
            "stats": part_data.get("stats", {}),
            "weight": ITEM_WEIGHTS.get(inventory_type, 1.0),
            "is_core": item_key in CORE_RECIPES
        })
    return result

_CACHED_CRAFTING_RECIPES: list = _build_recipe_cache()



# ─────────────────────────────────────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────────────────────────────────────

def _axial_dist(q1, r1, q2, r2) -> int:
    """Core axial distance math."""
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def get_hex_distance(q1, r1, q2, r2) -> int:
    """Calculates shortest distance on a spherical/wrapped hex grid."""
    # To find shortest distance on a sphere/torus, we check the target and its "images"
    # across the seams and poles.
    
    # Image 1: Direct
    dists = [_axial_dist(q1, r1, q2, r2)]
    
    # Image 2 & 3: Longitude wrap
    dists.append(_axial_dist(q1, r1, q2 + WORLD_WIDTH, r2))
    dists.append(_axial_dist(q1, r1, q2 - WORLD_WIDTH, r2))
    
    # Image 4: North Pole Reflection (q+50, -r)
    pq_n = (q2 + (WORLD_WIDTH // 2))
    dists.append(_axial_dist(q1, r1, pq_n, -r2))
    dists.append(_axial_dist(q1, r1, pq_n - WORLD_WIDTH, -r2))
    dists.append(_axial_dist(q1, r1, pq_n + WORLD_WIDTH, -r2))
    
    # Image 5: South Pole Reflection (q+50, 200 - r)
    # Pole is at 100. Reflection of r2 over 100 is 100 + (100 - r2) = 200 - r2
    pq_s = (q2 + (WORLD_WIDTH // 2))
    dists.append(_axial_dist(q1, r1, pq_s, 200 - r2))
    dists.append(_axial_dist(q1, r1, pq_s - WORLD_WIDTH, 200 - r2))
    dists.append(_axial_dist(q1, r1, pq_s + WORLD_WIDTH, 200 - r2))
    
    return min(dists)


def is_in_anarchy_zone(q, r) -> bool:
    """Checks if coordinates are outside the colonial safe zone (city radius 5)."""
    return get_hex_distance(q, r, 0, 0) >= ANARCHY_THRESHOLD


def wrap_coords(q, r) -> tuple:
    """Wraps coordinates for a finite spherical world."""
    # Longitude (q) wrapping
    q = q % WORLD_WIDTH
    
    # Latitude (r) wrapping (over-the-pole reflection)
    if r < MAP_MIN_R:
        # Crossed North Pole
        r = abs(r)
        q = (q + (WORLD_WIDTH // 2)) % WORLD_WIDTH
    elif r > MAP_MAX_R:
        # Crossed South Pole
        r = MAP_MAX_R - (r - MAP_MAX_R)
        q = (q + (WORLD_WIDTH // 2)) % WORLD_WIDTH
        
    return q, r


def get_hex_terrain_data(q, r) -> dict:
    """
    Calculates the 'theoretical' terrain and resources for any coordinate.
    Hub is at (0,0) = North Pole. Distance from hub drives zone tier.
    Does NOT check the database. Used for seeding and dynamic hex generation.
    """
    q, r = wrap_coords(q, r)
    dist = get_hex_distance(q, r, 0, 0)

    # ── Static Stations (clustered at North Pole, within 3 steps) ──────────────
    STATIONS = {
        (0, 0): "MARKET",   # Hub / Market
        (2, 0): "SMELTER",
        (0, 2): "CRAFTER",
        (1, 2): "REPAIR",
        (2, 1): "REFINERY",
    }
    if (q, r) in STATIONS:
        return {
            "terrain_type": "STATION",
            "is_station": True,
            "station_type": STATIONS[(q, r)],
            "resource_type": None,
            "resource_density": 0.0,
            "resource_quantity": 0
        }

    # ── City Inner Ring (dist 0-5): safe void, no resources ───────────────────
    if dist <= 5:
        return {
            "terrain_type": "VOID",
            "is_station": False,
            "station_type": None,
            "resource_type": None,
            "resource_density": 0.0,
            "resource_quantity": 0
        }

    # ── Procedural Generation ──────────────────────────────────────────────────
    # Base terrain roll: 12% asteroid, 5% obstacle, rest void
    roll = random.random()
    terrain = "VOID"
    res_type = None
    res_density = 0.0
    res_qty = 0

    if roll < 0.12:
        terrain = "ASTEROID"
        tier_roll = random.random()
        elite_roll = random.random()  # 2% chance of +1 tier upgrade anywhere

        # ── Zone 1: Inner Ring / Iron Belt (dist 6–15) ─────────────────────────
        if dist <= 15:
            if tier_roll < 0.80:
                res_type = "IRON_ORE"
            elif tier_roll < 0.95:
                res_type = "COPPER_ORE"
            else:
                res_type = "GOLD_ORE"  # ultra-rare elite
            # Elite upgrade
            if elite_roll < 0.02 and res_type == "IRON_ORE":
                res_type = "COPPER_ORE"

        # ── Zone 2: Copper Belt (dist 16–30) ──────────────────────────────────
        elif dist <= 30:
            if tier_roll < 0.18:
                res_type = "IRON_ORE"
            elif tier_roll < 0.78:
                res_type = "COPPER_ORE"
            elif tier_roll < 0.96:
                res_type = "GOLD_ORE"
            else:
                res_type = "COBALT_ORE"  # ultra-rare elite
            if elite_roll < 0.02 and res_type in ("IRON_ORE", "COPPER_ORE"):
                # Bump up one tier
                res_type = "COPPER_ORE" if res_type == "IRON_ORE" else "GOLD_ORE"

        # ── Zone 3: Gold Fields (dist 31–50) ──────────────────────────────────
        elif dist <= 50:
            if tier_roll < 0.10:
                res_type = "IRON_ORE"
            elif tier_roll < 0.25:
                res_type = "COPPER_ORE"
            elif tier_roll < 0.70:
                res_type = "GOLD_ORE"
            else:
                res_type = "COBALT_ORE"
            if elite_roll < 0.02 and res_type == "COPPER_ORE":
                res_type = "GOLD_ORE"

        # ── Zone 4: Deep Dark / South Pole (dist > 50) ────────────────────────
        else:
            # Cobalt increasingly dominant as we approach south pole
            cobalt_chance = min(0.70, (dist - 50) / 70.0)
            if tier_roll < 0.05:
                res_type = "IRON_ORE"
            elif tier_roll < 0.12:
                res_type = "COPPER_ORE"
            elif tier_roll < (0.12 + (1.0 - cobalt_chance) * 0.58):
                res_type = "GOLD_ORE"
            else:
                res_type = "COBALT_ORE"

        # ── Helium Gas: 5% chance anywhere outside city, overrides ore ─────────
        if random.random() < 0.05:
            res_type = "HELIUM_GAS"

        res_density = random.uniform(0.8, 2.5)
        res_qty = random.randint(200, 1500)

    elif roll < 0.17:
        terrain = "OBSTACLE"

    return {
        "terrain_type": terrain,
        "is_station": False,
        "station_type": None,
        "resource_type": res_type,
        "resource_density": res_density,
        "resource_quantity": res_qty
    }


def seed_hex_if_missing(db: Session, q, r) -> WorldHex:
    """Checks DB for a hex; if missing, generates and saves it."""
    # We use a simple select to check existence. 
    # Performance tip: querying single hexes is fast with the index on (q,r).
    existing = db.execute(select(WorldHex).where(WorldHex.q == q, WorldHex.r == r)).scalar_one_or_none()
    if existing:
        return existing
        
    data = get_hex_terrain_data(q, r)
    
    # We need a sector_id. In a dynamic world, we might just use a 'Dynamic' sector
    # or calculate sector coordinates. SECTOR_SIZE is 20 in seed_world.py.
    sq, sr = q // 20, r // 20
    sector = db.execute(select(Sector).where(Sector.q == sq, Sector.r == sr)).scalar_one_or_none()
    if not sector:
        sector = Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}")
        db.add(sector)
        db.flush() # Get ID
        
    new_hex = WorldHex(
        sector_id=sector.id,
        q=q,
        r=r,
        terrain_type=data["terrain_type"],
        is_station=data["is_station"],
        station_type=data["station_type"],
        resource_type=data["resource_type"],
        resource_density=data["resource_density"],
        resource_quantity=data["resource_quantity"]
    )
    db.add(new_hex)
    db.flush()
    return new_hex


def get_solar_intensity(q, r, tick_count=0) -> float:
    """Solar intensity based on distance from the North Pole hub (0,0).
    City (dist 0-5): always 1.0
    Twilight zone (dist 6-30): day/night cycle
    Deep dark (dist > 30): always 0.0
    """
    dist = get_hex_distance(q, r, 0, 0)
    if dist <= SOLAR_RADIUS_SAFE:
        return 1.0
    if dist <= SOLAR_RADIUS_TWILIGHT:
        # Each day/night cycle = 60 ticks (30 day, 30 night)
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
    bounds = get_world_bounds(db)
    
    while queue:
        q, r, path = queue.popleft()
        if q == gq and r == gr:
            return path
        if len(path) >= max_steps:
            continue
        for dq, dr in NEIGHBORS:
            nq, nr = wrap_coords(q + dq, r + dr)
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
    # Base Stats
    agent.max_health = 100
    agent.damage = 10
    agent.accuracy = 10
    agent.speed = 10
    agent.overclock = 10
    agent.armor = 5
    agent.max_mass = BASE_CAPACITY
    agent.mining_yield = 10
    
    # Custom attributes (may not be in models yet, but we handle them)
    radar_radius = 5

    for part in agent.parts:
        base_stats = part.stats or {}
        rarity = part.rarity or "STANDARD"
        rarity_data = RARITY_LEVELS.get(rarity, RARITY_LEVELS["STANDARD"])
        multiplier = rarity_data["multiplier"]

        # Summation with Multiplier (Positive and Negative)
        agent.max_health += int(base_stats.get("max_health", 0) * multiplier)
        agent.damage += int(base_stats.get("damage", 0) * multiplier)
        agent.accuracy += int(base_stats.get("accuracy", 0) * multiplier)
        agent.speed += int(base_stats.get("speed", 0) * multiplier)
        agent.overclock += int(base_stats.get("overclock", 0) * multiplier)
        agent.armor += int(base_stats.get("armor", 0) * multiplier)
        agent.mining_yield += int(base_stats.get("mining_yield", 0) * multiplier)
        
        # Capacity is special (Float)
        agent.max_mass += (base_stats.get("capacity", 0) * multiplier)
        
        # Temporary Radar Radius (stored in local var for now, or could be in meta)
        radar_radius += int(base_stats.get("radar_radius", 0) * multiplier)

        # Upgrade Level Boost (10% per level)
        upgrade_lvl = part.stats.get("upgrade_level", 0) if part.stats else 0
        if upgrade_lvl > 0:
            boost = 1.0 + (upgrade_lvl * 0.1)
            agent.max_health = int(agent.max_health * boost)
            agent.damage = int(agent.damage * boost)
            agent.accuracy = int(agent.accuracy * boost)
            agent.speed = int(agent.speed * boost)
            agent.overclock = int(agent.overclock * boost)
            agent.armor = int(agent.armor * boost)
            agent.mining_yield = int(agent.mining_yield * boost)

        # Random Affixes
        affixes = part.affixes or {}
        for affix_name, stat_bonuses in affixes.items():
            if isinstance(stat_bonuses, dict):
                for stat_name, bonus in stat_bonuses.items():
                    if hasattr(agent, stat_name):
                        current_val = getattr(agent, stat_name) or 0
                        setattr(agent, stat_name, current_val + bonus)
                    elif stat_name == "capacity":
                        agent.max_mass += bonus
                    elif stat_name == "radar_radius":
                        radar_radius += bonus

    # Caps & Floor (Ensure no negative critical stats)
    agent.max_health = max(10, agent.max_health)
    agent.speed = max(1, agent.speed)
    agent.accuracy = max(1, agent.accuracy)
    agent.damage = max(1, agent.damage)
    agent.mining_yield = max(1, agent.mining_yield)
    agent.max_mass = max(50.0, agent.max_mass)

    # Wear & Tear penalty (Applied after all bonuses)
    wear = agent.wear_and_tear or 0.0
    if wear > 50.0:
        penalty_factor = max(0.2, 1.0 - ((wear - 50.0) / 100.0))
        agent.damage = int(agent.damage * penalty_factor)
        agent.accuracy = int(agent.accuracy * penalty_factor)
        agent.speed = int(agent.speed * penalty_factor)
        agent.mining_yield = int(agent.mining_yield * penalty_factor)
        logger.info(f"Agent {agent.id} Wear & Tear penalty: {penalty_factor:.2f}x")

    if agent.health > agent.max_health:
        agent.health = agent.max_health

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
        # Starter Care Package
        db.add(InventoryItem(agent_id=agent.id, item_type="FIELD_REPAIR_KIT", quantity=2, data={"is_tradable": False}))
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
            if "striker" in name_str:
                signature["chassis"] = "STRIKER"
            elif "industrial" in name_str or "hull" in name_str:
                signature["chassis"] = "INDUSTRIAL"
            elif "heavy" in name_str or "titan" in name_str or "bastion" in name_str:
                signature["chassis"] = "HEAVY"
            elif "aegis" in name_str or "shield" in name_str:
                signature["chassis"] = "SHIELDED"
                
        if part.part_type == "Actuator":
            if "drill" in name_str:
                signature["actuator"] = "DRILL"
            elif "blaster" in name_str or "laser" in name_str or "railgun" in name_str or "rifle" in name_str or "cannon" in name_str or "repeater" in name_str:
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
    best = min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s["q"], s["r"]))
    
    # Compatibility wrapper for attribute access (q, r)
    class _S:
        def __init__(self, d):
            self.q = d["q"]
            self.r = d["r"]
    return _S(best)


def get_discovery_packet(station_cache: list, agent: Agent) -> dict:
    """Returns nearest locations of public service stations from cache."""
    discovery = {}
    for st in ["MARKET", "SMELTER", "CRAFTER", "REPAIR", "REFINERY"]:
        relevant = [s for s in station_cache if s["station_type"] == st]
        if relevant:
            nearest = min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s["q"], s["r"]))
            dist = get_hex_distance(agent.q, agent.r, nearest["q"], nearest["r"])
            discovery[st] = {"q": nearest["q"], "r": nearest["r"], "distance": dist}

    # Use pre-built cached recipes — no per-request allocation
    discovery["crafting_recipes"] = _CACHED_CRAFTING_RECIPES
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
            agent.health = agent.max_health
            db.add(AuditLog(agent_id=agent.id, event_type="LEVEL_UP", details={"new_level": agent.level}))
            logger.info(f"Agent {agent.id} leveled up to {agent.level}!")
        else:
            break


