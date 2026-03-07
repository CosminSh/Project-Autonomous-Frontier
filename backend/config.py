"""
config.py — Game constants, recipes, item weights, and part definitions.
All other modules import from here. No database or app dependencies.
"""
import random
# ─────────────────────────────────────────────────────────────────────────────
# Game Constants (GDD Section 3.2 & 5.2)
# ─────────────────────────────────────────────────────────────────────────────
MOVE_ENERGY_COST = 5
MINE_ENERGY_COST = 10
ATTACK_ENERGY_COST = 15
BASE_REGEN = 2  # Energy recharged per tick (at 100% intensity)
MAX_CAPACITOR = 100

# Tick Phase Durations (GDD Section 5.2 - Scaled for Testing)
PHASE_PERCEPTION_DURATION = 5
PHASE_STRATEGY_DURATION = 10
PHASE_CRUNCH_DURATION = 5

RESPAWN_HP_PERCENT = 0.5
TOWN_COORDINATES = (0, 0)   # North Pole — the hub
ANARCHY_THRESHOLD = 6      # City is dist 0-5; anarchy starts at 6
SOLAR_RADIUS_SAFE = 5      # Always sunny within 5 steps (City)
SOLAR_RADIUS_TWILIGHT = 30 # Day/night zone: dist 6-30; pure dark beyond
CLUTTER_THRESHOLD = 3
CLUTTER_PENALTY = 0.2  # 20% reduction

# World Dimensions (Wrapping)
WORLD_WIDTH = 100
WORLD_HEIGHT = 101  # r from 0 to 100
MAP_MIN_Q = 0
MAP_MAX_Q = 99
MAP_MIN_R = 0
MAP_MAX_R = 100

# ─────────────────────────────────────────────────────────────────────────────
# Industrial Recipes & Costs
# ─────────────────────────────────────────────────────────────────────────────
SMELTING_RECIPES = {
    "IRON_ORE": "IRON_INGOT",
    "COPPER_ORE": "COPPER_INGOT",
    "GOLD_ORE": "GOLD_INGOT",
    "COBALT_ORE": "COBALT_INGOT"
}
SMELTING_RATIO = 5  # 5 Ore -> 1 Ingot

CRAFTING_RECIPES = {
    "SCRAP_FRAME": {"IRON_INGOT": 1},
    "SCRAP_ACTUATOR": {"IRON_INGOT": 1},
    "BASIC_FRAME": {"IRON_INGOT": 10},
    "HEAVY_FRAME": {"IRON_INGOT": 20, "COBALT_INGOT": 10},
    "DRILL_UNIT": {"IRON_INGOT": 5, "COPPER_INGOT": 5},
    "DRILL_IRON_BASIC": {"IRON_INGOT": 10},
    "DRILL_IRON_ADVANCED": {"IRON_INGOT": 10},
    "DRILL_COPPER_BASIC": {"COPPER_INGOT": 5},
    "DRILL_COPPER_ADVANCED": {"COPPER_INGOT": 15},
    "DRILL_GOLD_BASIC": {"GOLD_INGOT": 5},
    "DRILL_GOLD_ADVANCED": {"GOLD_INGOT": 15},
    "DRILL_COBALT_BASIC": {"COBALT_INGOT": 5, "GOLD_INGOT": 5},
    "DRILL_COBALT_ADVANCED": {"COBALT_INGOT": 15},
    "SCRAP_SOLAR_PANEL": {"COPPER_INGOT": 2, "IRON_INGOT": 2},
    "REFINED_SOLAR_PANEL": {"COPPER_INGOT": 8, "GOLD_INGOT": 2},
    "HE3_FUEL_CELL_UNIT": {"COBALT_INGOT": 5, "GOLD_INGOT": 2},
    "NEURAL_SCANNER": {"COPPER_INGOT": 20, "GOLD_INGOT": 5},
    "ADVANCED_SCANNER": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    "GAS_SIPHON": {"COPPER_INGOT": 10, "IRON_INGOT": 5},
    "EMPTY_CANISTER": {"IRON_INGOT": 5},
    "ENGINE_UNIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "ENGINE_CARGO": {"IRON_INGOT": 20, "GOLD_INGOT": 5},
    "ENGINE_TURBO": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    "SHIELD_GENERATOR": {"COPPER_INGOT": 30, "GOLD_INGOT": 10},
    "UPGRADE_MODULE": {"GOLD_INGOT": 5, "COBALT_INGOT": 2},
    "REPAIR_KIT": {"IRON_INGOT": 10, "COPPER_INGOT": 5},
    "FIELD_REPAIR_KIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "CORE_VOUCHER": {"GOLD_INGOT": 5, "COBALT_INGOT": 5},
    
    # New Weapons (Actuators)
    "IRON_AUTO_RIFLE": {"IRON_INGOT": 15},
    "COPPER_RAILGUN": {"IRON_INGOT": 10, "COPPER_INGOT": 10},
    "GOLD_LASER_CANNON": {"COPPER_INGOT": 15, "GOLD_INGOT": 5},
    
    # New Armors (Frames)
    "LIGHT_PLATING": {"IRON_INGOT": 15},
    "COPPER_ALLOY_ARMOR": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    
    # New Sensors
    "BASIC_SCANNER": {"IRON_INGOT": 10},
    "COPPER_ARRAY": {"COPPER_INGOT": 15},
    
    # New Engines
    "IRON_THRUSTER": {"IRON_INGOT": 20},
    "COPPER_OVERDRIVE": {"IRON_INGOT": 10, "COPPER_INGOT": 15},
    
    # Utilities (Power / Capacity)
    "BASIC_BATTERY": {"IRON_INGOT": 15},
    "COPPER_CAPACITOR": {"COPPER_INGOT": 20}
}

CORE_RECIPES = ["SCRAP_FRAME", "SCRAP_ACTUATOR", "BASIC_FRAME", "HEAVY_FRAME", "DRILL_UNIT", 
                "DRILL_IRON_BASIC", "DRILL_IRON_ADVANCED", 
                "DRILL_COPPER_BASIC", "DRILL_COPPER_ADVANCED",
                "DRILL_GOLD_BASIC", "DRILL_GOLD_ADVANCED",
                "DRILL_COBALT_BASIC", "DRILL_COBALT_ADVANCED",
                "EMPTY_CANISTER", "UPGRADE_MODULE", "ENGINE_UNIT", "SCRAP_SOLAR_PANEL", "REPAIR_KIT",
                "FIELD_REPAIR_KIT", "CORE_VOUCHER",
                "IRON_AUTO_RIFLE", "COPPER_RAILGUN", "GOLD_LASER_CANNON",
                "LIGHT_PLATING", "COPPER_ALLOY_ARMOR", "BASIC_SCANNER", "COPPER_ARRAY",
                "IRON_THRUSTER", "COPPER_OVERDRIVE", "BASIC_BATTERY", "COPPER_CAPACITOR"]
UPGRADE_MAX_LEVEL = 10
UPGRADE_BASE_INGOT_COST = 10

# ─────────────────────────────────────────────────────────────────────────────
# Rarity Hierarchy (GDD Overhaul)
# ─────────────────────────────────────────────────────────────────────────────
RARITY_LEVELS = {
    "SCRAP": {"color": "gray", "multiplier": 0.8, "weight": 40},
    "STANDARD": {"color": "white", "multiplier": 1.0, "weight": 35},
    "REFINED": {"color": "blue", "multiplier": 1.2, "weight": 15},
    "PRIME": {"color": "yellow", "multiplier": 1.5, "weight": 8},
    "RELIC": {"color": "orange", "multiplier": 2.0, "weight": 2}
}

# Affix Pool: Randomized prefixes/suffixes
AFFIX_POOL = {
    "Overclocked": {"overclock": 10},
    "Hardened": {"armor": 5},
    "Precise": {"accuracy": 8},
    "Dense": {"max_health": 25},
    "Reactive": {"accuracy": 4, "overclock": 4},
    "Bulk": {"capacity": 50},
    "Swift": {"speed": 5, "damage": 5}
}

REPAIR_COST_PER_HP = 1  # Credits per HP restored
REPAIR_COST_IRON_INGOT_PER_HP = 0.02  # 1 Ingot per 50 HP
MAINTENANCE_BASE_COST = {"CREDITS": 50, "IRON_INGOT": 2}
MAINTENANCE_COEFFICIENT = 0.2  # 20% of equipped gear crafting cost
CANISTER_MAX_FILL = 100  # 100%
GAS_REFINING_RATIO = 10  # 10 Helium -> 10% Canister Fill
FACTION_REALIGNMENT_COST = 500
FACTION_REALIGNMENT_COOLDOWN = 100

# ─────────────────────────────────────────────────────────────────────────────
# Part Stats Definitions
# ─────────────────────────────────────────────────────────────────────────────
PART_DEFINITIONS = {
    "SCRAP_FRAME": {"type": "Frame", "stats": {"max_health": 40, "armor": 1}, "name": "Basic Scrap Frame"},
    "SCRAP_ACTUATOR": {"type": "Actuator", "stats": {"damage": 5, "accuracy": -5}, "name": "Scrap Actuator Spike"},
    "BASIC_FRAME": {"type": "Frame", "stats": {"max_health": 50, "armor": 5, "capacity": 50}, "name": "Reinforced Chassis"},
    "HEAVY_FRAME": {"type": "Frame", "stats": {"max_health": 150, "armor": 15, "capacity": 30, "speed": -5}, "name": "Heavy Assault Chassis"},
    "DRILL_UNIT": {"type": "Actuator", "stats": {"damage": 8, "accuracy": 0}, "name": "Basic Iron Drill"},
    "DRILL_IRON_BASIC": {"type": "Actuator", "stats": {"damage": 5}, "name": "Iron Drill"},
    "DRILL_IRON_ADVANCED": {"type": "Actuator", "stats": {"damage": 10}, "name": "Advanced Iron Drill"},
    "DRILL_COPPER_BASIC": {"type": "Actuator", "stats": {"damage": 15}, "name": "Copper Drill"},
    "DRILL_COPPER_ADVANCED": {"type": "Actuator", "stats": {"damage": 22}, "name": "Advanced Copper Drill"},
    "DRILL_GOLD_BASIC": {"type": "Actuator", "stats": {"damage": 30}, "name": "Gold Drill"},
    "DRILL_GOLD_ADVANCED": {"type": "Actuator", "stats": {"damage": 40}, "name": "Advanced Gold Drill"},
    "DRILL_COBALT_BASIC": {"type": "Actuator", "stats": {"damage": 55}, "name": "Cobalt Drill"},
    "DRILL_COBALT_ADVANCED": {"type": "Actuator", "stats": {"damage": 75}, "name": "Advanced Cobalt Drill"},
    "SCRAP_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 0.5}, "name": "Scrap Solar Panel"},
    "REFINED_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 1.0}, "name": "Refined Solar Array"},
    "HE3_FUEL_CELL_UNIT": {"type": "Power", "stats": {"efficiency": 2.0}, "name": "Helium-3 Fuel Cell"},
    "NEURAL_SCANNER": {"type": "Sensor", "stats": {"radius": 2, "scan_depth": 1}, "name": "Neural-Link Cargo Scanner"},
    "ADVANCED_SCANNER": {"type": "Sensor", "stats": {"radius": 4, "scan_depth": 1}, "name": "Deep-Space Array Scanner"},
    "GAS_SIPHON": {"type": "Actuator", "stats": {"damage": 2}, "name": "Helium Gas Siphon"},
    "ENGINE_UNIT": {"type": "Engine", "stats": {"damage": 5, "capacity": 20, "speed": 10}, "name": "Standard Fusion Engine"},
    "ENGINE_CARGO": {"type": "Engine", "stats": {"damage": 2, "capacity": 60, "speed": 0}, "name": "Hauler-Class Cargo Engine"},
    "ENGINE_TURBO": {"type": "Engine", "stats": {"damage": 15, "capacity": 5, "speed": 25}, "name": "Interceptor Turbo Engine"},
    "SHIELD_GENERATOR": {"type": "Frame", "stats": {"armor": 15, "max_health": 50}, "name": "Aegis Shield Generator"},
    "IRON_AUTO_RIFLE": {"type": "Actuator", "stats": {"damage": 10, "speed": 10}, "name": "Standard Iron Auto-Rifle"},
    "COPPER_RAILGUN": {"type": "Actuator", "stats": {"damage": 25, "accuracy": -2, "speed": -5}, "name": "High-Impact Copper Railgun"},
    "GOLD_LASER_CANNON": {"type": "Actuator", "stats": {"damage": 35, "accuracy": 15}, "name": "Precision Gold Laser Cannon"},
    "LIGHT_PLATING": {"type": "Frame", "stats": {"max_health": 30, "armor": 2, "speed": 5}, "name": "Lightweight Iron Plating"},
    "COPPER_ALLOY_ARMOR": {"type": "Frame", "stats": {"max_health": 60, "armor": 10, "speed": -2}, "name": "Copper Alloy Armor"},
    "BASIC_SCANNER": {"type": "Sensor", "stats": {"radius": 1, "accuracy": 5}, "name": "Basic Proximity Scanner"},
    "COPPER_ARRAY": {"type": "Sensor", "stats": {"radius": 2, "accuracy": 10}, "name": "Copper Comm-Array"},
    "IRON_THRUSTER": {"type": "Engine", "stats": {"damage": 3, "capacity": 5, "speed": 15}, "name": "Iron Pursuit Thruster"},
    "COPPER_OVERDRIVE": {"type": "Engine", "stats": {"damage": 8, "capacity": -10, "speed": 30}, "name": "Copper Overdrive Manifold"},
    "BASIC_BATTERY": {"type": "Power", "stats": {"energy": 25}, "name": "Basic Iron Battery"},
    "COPPER_CAPACITOR": {"type": "Power", "stats": {"energy": 60}, "name": "Copper Flux Capacitor"}
}

# ─────────────────────────────────────────────────────────────────────────────
# Mass & Weight System (GDD Milestone 1)
# ─────────────────────────────────────────────────────────────────────────────
ITEM_WEIGHTS = {
    "CREDITS": 0.0,
    "IRON_ORE": 2.0,
    "COPPER_ORE": 2.0,
    "GOLD_ORE": 3.0,
    "COBALT_ORE": 4.0,
    "IRON_INGOT": 5.0,
    "COPPER_INGOT": 5.0,
    "GOLD_INGOT": 7.0,
    "COBALT_INGOT": 10.0,
    "PART_SCRAP_FRAME": 25.0,
    "PART_SCRAP_ACTUATOR": 10.0,
    "PART_BASIC_FRAME": 50.0,
    "PART_HEAVY_FRAME": 100.0,
    "PART_DRILL_UNIT": 15.0,
    "PART_DRILL_IRON_BASIC": 15.0,
    "PART_DRILL_IRON_ADVANCED": 20.0,
    "PART_DRILL_COPPER_BASIC": 20.0,
    "PART_DRILL_COPPER_ADVANCED": 25.0,
    "PART_DRILL_GOLD_BASIC": 25.0,
    "PART_DRILL_GOLD_ADVANCED": 30.0,
    "PART_DRILL_COBALT_BASIC": 30.0,
    "PART_DRILL_COBALT_ADVANCED": 40.0,
    "PART_SCRAP_SOLAR_PANEL": 5.0,
    "PART_REFINED_SOLAR_PANEL": 10.0,
    "PART_HE3_FUEL_CELL_UNIT": 12.0,
    "PART_NEURAL_SCANNER": 12.0,
    "PART_ADVANCED_SCANNER": 20.0,
    "PART_GAS_SIPHON": 15.0,
    "EMPTY_CANISTER": 5.0,
    "HE3_CANISTER": 8.0,
    "HELIUM_GAS": 1.0,
    "HE3_FUEL_CELL": 5.0,
    "PART_ENGINE_UNIT": 40.0,
    "PART_ENGINE_CARGO": 60.0,
    "PART_ENGINE_TURBO": 30.0,
    "PART_SHIELD_GENERATOR": 50.0,
    "PART_IRON_AUTO_RIFLE": 25.0,
    "PART_COPPER_RAILGUN": 35.0,
    "PART_GOLD_LASER_CANNON": 30.0,
    "PART_LIGHT_PLATING": 20.0,
    "PART_COPPER_ALLOY_ARMOR": 45.0,
    "PART_BASIC_SCANNER": 10.0,
    "PART_COPPER_ARRAY": 15.0,
    "PART_IRON_THRUSTER": 25.0,
    "PART_COPPER_OVERDRIVE": 35.0,
    "PART_BASIC_BATTERY": 20.0,
    "PART_COPPER_CAPACITOR": 30.0,
    "UPGRADE_MODULE": 2.0,
    "REPAIR_KIT": 5.0,
    "FIELD_REPAIR_KIT": 8.0,
    "CORE_VOUCHER": 0.5,
    "SCRAP_METAL": 1.0,
    "ELECTRONICS": 0.5
}
BASE_CAPACITY = 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Mining Tier Logic
# ─────────────────────────────────────────────────────────────────────────────
MINING_TIERS = {
    "IRON_ORE": {"tier": 1, "name": "Iron"},
    "COPPER_ORE": {"tier": 2, "name": "Copper"},
    "GOLD_ORE": {"tier": 3, "name": "Gold"},
    "COBALT_ORE": {"tier": 4, "name": "Cobalt"}
}

DRILL_TIERS = {
    "DRILL_IRON_BASIC": {"tier": 1, "advanced": False},
    "DRILL_IRON_ADVANCED": {"tier": 1, "advanced": True},
    "DRILL_COPPER_BASIC": {"tier": 2, "advanced": False},
    "DRILL_COPPER_ADVANCED": {"tier": 2, "advanced": True},
    "DRILL_GOLD_BASIC": {"tier": 3, "advanced": False},
    "DRILL_GOLD_ADVANCED": {"tier": 3, "advanced": True},
    "DRILL_COBALT_BASIC": {"tier": 4, "advanced": False},
    "DRILL_COBALT_ADVANCED": {"tier": 4, "advanced": True},
    "DRILL_UNIT": {"tier": 1, "advanced": False},
}


# ─────────────────────────────────────────────────────────────────────────────
# Rarity / Affix Helpers (pure logic, no DB)
# ─────────────────────────────────────────────────────────────────────────────
def roll_rarity() -> str:
    """Weighted roll for item rarity."""
    items = list(RARITY_LEVELS.keys())
    weights = [v["weight"] for v in RARITY_LEVELS.values()]
    return random.choices(items, weights=weights, k=1)[0]


def roll_affixes(rarity: str) -> dict:
    """Roll for affixes based on rarity. Higher rarity = more affixes."""
    rarity_slots = {"SCRAP": 0, "STANDARD": 0, "REFINED": 1, "PRIME": 2, "RELIC": 3}
    count = rarity_slots.get(rarity, 0)
    if count == 0:
        return {}
    selected_names = random.sample(list(AFFIX_POOL.keys()), min(count, len(AFFIX_POOL)))
    return {name: AFFIX_POOL[name] for name in selected_names}
