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
BASE_REGEN = 4  # Energy recharged per tick (at 100% intensity)
MAX_CAPACITOR = 100

# Tick Phase Durations (GDD Section 5.2 - Scaled for Testing)
PHASE_PERCEPTION_DURATION = 5
PHASE_STRATEGY_DURATION = 10
PHASE_CRUNCH_DURATION = 5

RESPAWN_HP_PERCENT = 0.5
TOWN_COORDINATES = (0, 0)   # North Pole — the hub
ANARCHY_THRESHOLD = 6      # City is dist 0-5; anarchy starts at 6
# Solar Zones (r-coordinate based)
SOLAR_ZONE_SUNNY = 33      # Always sunny: r in [0, 32]
SOLAR_ZONE_TWILIGHT = 66   # Day/Night cycle: r in [33, 66]
# Global Cycle Length (60 ticks = ~1 hour real time at 1.5 min/tick)
SOLAR_CYCLE_LENGTH = 60
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
SMELTING_MAX_PER_TICK = 1
SMELTING_ENERGY_COSTS = {
    "IRON_ORE": 5,
    "COPPER_ORE": 10,
    "GOLD_ORE": 15,
    "COBALT_ORE": 20
}

CRAFTING_RECIPES = {
    # Frames (Determine Slot Limits)
    "SCRAP_FRAME": {"IRON_INGOT": 1},
    "BASIC_FRAME": {"IRON_INGOT": 10},
    "HYBRID_CHASSIS": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "HEAVY_FRAME": {"IRON_INGOT": 20, "COBALT_INGOT": 10},
    "STRIKER_CHASSIS": {"COPPER_INGOT": 25, "GOLD_INGOT": 5},
    "INDUSTRIAL_HULL": {"IRON_INGOT": 30, "COBALT_INGOT": 15},
    
    # Tools & Drills (Mining Yield + Small Damage)
    "DRILL_UNIT": {"IRON_INGOT": 5, "COPPER_INGOT": 5},
    "DRILL_IRON_BASIC": {"IRON_INGOT": 10},
    "DRILL_IRON_ADVANCED": {"IRON_INGOT": 10},
    "DRILL_COPPER_BASIC": {"COPPER_INGOT": 5},
    "DRILL_COPPER_ADVANCED": {"COPPER_INGOT": 15},
    "DRILL_GOLD_BASIC": {"GOLD_INGOT": 5},
    "DRILL_GOLD_ADVANCED": {"GOLD_INGOT": 15},
    "DRILL_COBALT_BASIC": {"COBALT_INGOT": 5, "GOLD_INGOT": 5},
    "DRILL_COBALT_ADVANCED": {"COBALT_INGOT": 15},
    "DEEP_CORE_DRILL": {"COBALT_INGOT": 20, "GOLD_INGOT": 10},

    # Weapons (RPS Triangle)
    "IRON_AUTO_RIFLE": {"IRON_INGOT": 15},      # Balanced (Striker)
    "COPPER_RAILGUN": {"COPPER_INGOT": 20},     # High Dmg, Low Acc (Penetrator)
    "PULSE_REPEATER": {"COPPER_INGOT": 15, "GOLD_INGOT": 5}, # High Acc, Low Dmg (Striker)
    "GOLD_LASER_CANNON": {"GOLD_INGOT": 15},    # Precision (Penetrator)
    "HEAVY_CANNON": {"COBALT_INGOT": 20},       # Elite Damage
    
    # Power & Utility
    "SCRAP_SOLAR_PANEL": {"COPPER_INGOT": 2, "IRON_INGOT": 2},
    "REFINED_SOLAR_PANEL": {"COPPER_INGOT": 8, "GOLD_INGOT": 2},
    "HE3_FUEL_CELL_UNIT": {"COBALT_INGOT": 5, "GOLD_INGOT": 2},
    "BASIC_BATTERY": {"IRON_INGOT": 15},
    "COPPER_CAPACITOR": {"COPPER_INGOT": 20},
    
    # Sensors (Visibility & Intel)
    "BASIC_SCANNER": {"IRON_INGOT": 10},
    "COPPER_ARRAY": {"COPPER_INGOT": 15},
    "NEURAL_SCANNER": {"COPPER_INGOT": 20, "GOLD_INGOT": 5},
    "ADVANCED_SCANNER": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    "GEOLOGICAL_SURVEYOR": {"GOLD_INGOT": 10, "COBALT_INGOT": 5},

    # Engines
    "IRON_THRUSTER": {"IRON_INGOT": 20},
    "COPPER_OVERDRIVE": {"COPPER_INGOT": 15, "IRON_INGOT": 10},
    "ENGINE_UNIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "ENGINE_CARGO": {"IRON_INGOT": 20, "GOLD_INGOT": 5},
    "ENGINE_TURBO": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    
    # Logistics
    "GAS_SIPHON": {"COPPER_INGOT": 10, "IRON_INGOT": 5},
    "EMPTY_CANISTER": {"IRON_INGOT": 5},
    "REPAIR_KIT": {"IRON_INGOT": 10, "COPPER_INGOT": 5},
    "FIELD_REPAIR_KIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "UPGRADE_MODULE": {"GOLD_INGOT": 5, "COBALT_INGOT": 2},
    "CORE_VOUCHER": {"GOLD_INGOT": 5, "COBALT_INGOT": 5},
    
    # [S] Special Variants
    "RAILGUN_S": {"ANCIENT_CIRCUIT": 1, "FERAL_CORE": 2, "GOLD_INGOT": 20},
    "SCANNER_S": {"VOID_CHIP": 1, "ELECTRONICS": 5, "COPPER_INGOT": 25}
}

CORE_RECIPES = list(CRAFTING_RECIPES.keys())
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

# Vault / Storage Constants
VAULT_BASE_CAPACITY = 500.0
VAULT_UPGRADE_SIZE = 250.0

def get_vault_upgrade_requirements(current_capacity: float) -> dict:
    """
    Returns progressive upgrade costs based on current capacity.
    Base (500 kg) -> Upgrade 1 (750 kg): 500 CR
    Upgrade 1 (750 kg) -> Upgrade 2 (1000 kg): 1000 CR + 20 Iron Ingot
    Upgrade 2 (1000 kg) -> Upgrade 3 (1250 kg): 2500 CR + 50 Iron Ingot + 20 Copper Ingot
    and so on...
    """
    level = int((current_capacity - VAULT_BASE_CAPACITY) / VAULT_UPGRADE_SIZE)
    
    if level == 0:
        return {"CREDITS": 500}
    elif level == 1:
        return {"CREDITS": 1000, "IRON_INGOT": 20}
    elif level == 2:
        return {"CREDITS": 2500, "IRON_INGOT": 50, "COPPER_INGOT": 20}
    elif level == 3:
        return {"CREDITS": 5000, "IRON_INGOT": 100, "COPPER_INGOT": 50, "GOLD_INGOT": 10}
    else:
        # Exponential scaling for late game
        multiplier = 2 ** (level - 3)
        return {
            "CREDITS": 5000 * multiplier,
            "IRON_INGOT": 100 * multiplier,
            "COPPER_INGOT": 50 * multiplier,
            "GOLD_INGOT": 10 * multiplier,
            "COBALT_INGOT": 5 * (level - 3)
        }

# ─────────────────────────────────────────────────────────────────────────────
# Frame-Specific Slot Limits
# ─────────────────────────────────────────────────────────────────────────────
FRAME_SLOT_LIMITS = {
    "DEFAULT": {"Frame": 1, "Actuator": 2, "Engine": 1, "Sensor": 1, "Power": 1},
    "SCRAP_FRAME": {"Frame": 1, "Actuator": 1, "Engine": 1, "Sensor": 1, "Power": 1},
    "BASIC_FRAME": {"Frame": 1, "Actuator": 2, "Engine": 1, "Sensor": 1, "Power": 1},
    "HYBRID_CHASSIS": {"Frame": 1, "Actuator": 2, "Engine": 2, "Sensor": 1, "Power": 1},
    "HEAVY_FRAME": {"Frame": 1, "Actuator": 1, "Engine": 1, "Sensor": 1, "Power": 3},
    "STRIKER_CHASSIS": {"Frame": 1, "Actuator": 3, "Engine": 2, "Sensor": 1, "Power": 0},
    "INDUSTRIAL_HULL": {"Frame": 1, "Actuator": 4, "Engine": 1, "Sensor": 2, "Power": 2}
}

# ─────────────────────────────────────────────────────────────────────────────
# Part Stats Definitions
# ─────────────────────────────────────────────────────────────────────────────
PART_DEFINITIONS = {
    # FRAMES
    "SCRAP_FRAME": {
        "type": "Frame", 
        "stats": {"max_health": 40, "armor": 1}, 
        "name": "Scrap Frame",
        "description": "A rickety frame salvaged from the wastes. Minimal slots."
    },
    "BASIC_FRAME": {
        "type": "Frame", 
        "stats": {"max_health": 100, "armor": 5, "capacity": 100}, 
        "name": "Standard Chassis",
        "description": "The reliable workhorse of the frontier. Balanced stats."
    },
    "HYBRID_CHASSIS": {
        "type": "Frame",
        "stats": {"max_health": 120, "armor": 8, "capacity": 150},
        "name": "Hybrid Multi-Role Frame",
        "description": "Versatile design with balanced slots for any operation."
    },
    "HEAVY_FRAME": {
        "type": "Frame", 
        "stats": {"max_health": 300, "armor": 25, "capacity": 50, "speed": -10}, 
        "name": "Bastion Heavy Frame",
        "description": "Reinforced plating and extra power slots. Extremely slow."
    },
    "STRIKER_CHASSIS": {
        "type": "Frame",
        "stats": {"max_health": 80, "armor": 2, "speed": 15, "capacity": -20},
        "name": "Striker Light Chassis",
        "description": "High-mobility interceptor frame. Sacrifices survivability for speed."
    },
    "INDUSTRIAL_HULL": {
        "type": "Frame",
        "stats": {"max_health": 150, "armor": 12, "capacity": 500, "speed": -15},
        "name": "Industrial Super-Hull",
        "description": "Massive cargo capacity and tool slots. Moves like a glacier."
    },

    # ACTUATORS - DRILLS (Mining Yield + Combat Damage)
    "DRILL_UNIT": {"type": "Actuator", "stats": {"mining_yield": 15, "damage": 5}, "name": "Basic Iron Drill", "description": "Standard mining tool. Fairly weak in combat."},
    "DRILL_IRON_BASIC": {"type": "Actuator", "stats": {"mining_yield": 25, "damage": 6}, "name": "Iron Drill", "description": "Starter drill for iron extraction."},
    "DRILL_IRON_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 40, "damage": 8}, "name": "Advanced Iron Drill", "description": "Reinforced iron drill."},
    "DRILL_COPPER_BASIC": {"type": "Actuator", "stats": {"mining_yield": 60, "damage": 10}, "name": "Copper Drill", "description": "Required for copper extraction."},
    "DRILL_COPPER_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 90, "damage": 15}, "name": "Advanced Copper Drill", "description": "High-efficiency copper drill."},
    "DRILL_GOLD_BASIC": {"type": "Actuator", "stats": {"mining_yield": 120, "damage": 20}, "name": "Gold Drill", "description": "Required for gold extraction."},
    "DRILL_GOLD_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 180, "damage": 28}, "name": "Advanced Gold Drill", "description": "Deep-vein gold extractor."},
    "DRILL_COBALT_BASIC": {"type": "Actuator", "stats": {"mining_yield": 250, "damage": 40}, "name": "Cobalt Drill", "description": "Required for cobalt extraction."},
    "DRILL_COBALT_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 400, "damage": 60}, "name": "Advanced Cobalt Drill", "description": "The peak of mining technology."},
    "DEEP_CORE_DRILL": {"type": "Actuator", "stats": {"mining_yield": 600, "damage": 15, "speed": -5}, "name": "Deep Core Thermal Drill", "description": "Ultimate mining power, but heavy and poor for combat."},

    # ACTUATORS - WEAPONS (RPS)
    "IRON_AUTO_RIFLE": {
        "type": "Actuator", 
        "stats": {"damage": 15, "accuracy": 10, "speed": 5}, 
        "name": "Standard Auto-Rifle",
        "description": "Balanced weapon for general skirmishes."
    },
    "COPPER_RAILGUN": {
        "type": "Actuator", 
        "stats": {"damage": 50, "accuracy": -10, "speed": -10}, 
        "name": "Copper Railgun",
        "description": "High damage shots (Penetrator). Struggles to hit agile targets."
    },
    "PULSE_REPEATER": {
        "type": "Actuator",
        "stats": {"damage": 12, "accuracy": 30, "speed": 10},
        "name": "Pulse Repeater",
        "description": "Rapid fire (Striker). High accuracy to counter speed."
    },
    "GOLD_LASER_CANNON": {
        "type": "Actuator", 
        "stats": {"damage": 80, "accuracy": 25, "energy_cost": 5}, 
        "name": "Precision Laser",
        "description": "Extreme damage and accuracy, but consumes additional energy."
    },
    "HEAVY_CANNON": {
        "type": "Actuator",
        "stats": {"damage": 120, "accuracy": -5, "speed": -15},
        "name": "Siege Cannon",
        "description": "Devastating damage. Best used against stationary or slow targets."
    },

    # SENSORS
    "BASIC_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 5, "accuracy": 5}, "name": "Basic Scanner", "description": "Increases detection range and slight accuracy."},
    "COPPER_ARRAY": {"type": "Sensor", "stats": {"radar_radius": 8, "accuracy": 10}, "name": "Copper Comm-Array", "description": "Standard array for frontier navigation."},
    "NEURAL_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 12, "scan_depth": 1}, "name": "Neural-Link Scanner", "description": "Enables detailed scanning of agent health and energy."},
    "ADVANCED_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 18, "scan_depth": 2}, "name": "Deep-Space Array", "description": "Long-range detection with structural intelligence."},
    "GEOLOGICAL_SURVEYOR": {"type": "Sensor", "stats": {"radar_radius": 10, "mining_yield": 50}, "name": "Geological Surveyor", "description": "Specialized sensor that boosts mining efficiency."},

    # ENGINES
    "IRON_THRUSTER": {"type": "Engine", "stats": {"speed": 15}, "name": "Iron Thruster", "description": "Simple propulsion unit."},
    "COPPER_OVERDRIVE": {"type": "Engine", "stats": {"speed": 35, "accuracy": -5}, "name": "Overdrive Manifold", "description": "Extreme speed at the cost of targeting stability."},
    "ENGINE_UNIT": {"type": "Engine", "stats": {"speed": 10, "capacity": 20}, "name": "Fusion Engine", "description": "Balanced speed and power efficiency."},
    "ENGINE_CARGO": {"type": "Engine", "stats": {"capacity": 200, "speed": -5}, "name": "Hauler Engine", "description": "Massive torque for cargo hauling."},
    "ENGINE_TURBO": {"type": "Engine", "stats": {"speed": 60, "energy_cost": 2}, "name": "Turbo Interceptor", "description": "Unmatched speed, high energy drain."},

    # POWER
    "SCRAP_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 0.5}, "name": "Scrap Solar Panel", "description": "Flimsy panels. Low power generation."},
    "REFINED_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 1.2}, "name": "Refined Solar Array", "description": "Standard power solution."},
    "HE3_FUEL_CELL_UNIT": {"type": "Power", "stats": {"efficiency": 4.0}, "name": "H3 Fuel Cell", "description": "High-output chemical power. Best for dark zones."},
    "BASIC_BATTERY": {"type": "Power", "stats": {"max_energy": 50}, "name": "Ion Battery", "description": "Increases energy storage capacity."},
    "COPPER_CAPACITOR": {"type": "Power", "stats": {"max_energy": 150}, "name": "High-Cap Capacitor", "description": "Major energy storage upgrade."}
}

# ─────────────────────────────────────────────────────────────────────────────
# Mass & Weight System (GDD Milestone 1)
# ─────────────────────────────────────────────────────────────────────────────
ITEM_WEIGHTS = {
    "CREDITS": 0.0,
    "IRON_ORE": 2.0, "COPPER_ORE": 2.0, "GOLD_ORE": 3.0, "COBALT_ORE": 4.0,
    "IRON_INGOT": 5.0, "COPPER_INGOT": 5.0, "GOLD_INGOT": 7.0, "COBALT_INGOT": 10.0,
    "EMPTY_CANISTER": 5.0, "HE3_CANISTER": 8.0, "HELIUM_GAS": 1.0,
    "UPGRADE_MODULE": 2.0, "REPAIR_KIT": 5.0, "FIELD_REPAIR_KIT": 8.0, "CORE_VOUCHER": 0.5,
    "SCRAP_METAL": 1.0, "ELECTRONICS": 0.5,
    "SYNTHETIC_WEAVE": 1.0, "FERAL_CORE": 2.5,
    "VOID_CHIP": 0.5, "ANCIENT_CIRCUIT": 0.8
}
# Populate part weights dynamically based on type
for key, defn in PART_DEFINITIONS.items():
    weight = 10.0
    if defn["type"] == "Frame": weight = 50.0
    elif defn["type"] == "Engine": weight = 30.0
    elif defn["type"] == "Actuator": weight = 20.0
    ITEM_WEIGHTS[f"PART_{key}"] = weight

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
