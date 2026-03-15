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
    "HAULER_CHASSIS_MK2": {"IRON_INGOT": 50, "COPPER_INGOT": 20},
    "GLADIATOR_FRAME": {"IRON_INGOT": 15, "FERAL_CORE": 1},
    "PIT_FRAME": {"IRON_INGOT": 10, "COPPER_INGOT": 5},
    "COPPER_MESH_FRAME": {"COPPER_INGOT": 15},
    
    
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
    "JUNK_CANNON": {"IRON_INGOT": 10, "COPPER_INGOT": 5},
    "SCRAP_BATON": {"IRON_INGOT": 8},
    "COPPER_BURST_RIFLE": {"COPPER_INGOT": 15},
    
    
    # Power & Utility
    "SCRAP_SOLAR_PANEL": {"COPPER_INGOT": 2, "IRON_INGOT": 2},
    "REFINED_SOLAR_PANEL": {"COPPER_INGOT": 8, "GOLD_INGOT": 2},
    "HE3_FUEL_CELL_UNIT": {"COBALT_INGOT": 5, "GOLD_INGOT": 2},
    "BASIC_BATTERY": {"IRON_INGOT": 15},
    "COPPER_CAPACITOR": {"COPPER_INGOT": 20},
    "SCRAP_SHIELD": {"IRON_INGOT": 10},
    "GEOLOGICAL_CORE": {"GOLD_INGOT": 15, "COBALT_INGOT": 5},
    "COPPER_SOLAR_ARRAY": {"COPPER_INGOT": 10},
    
    
    # Sensors (Visibility & Intel)
    "BASIC_SCANNER": {"IRON_INGOT": 10},
    "COPPER_ARRAY": {"COPPER_INGOT": 15},
    "NEURAL_SCANNER": {"COPPER_INGOT": 20, "GOLD_INGOT": 5},
    "ADVANCED_SCANNER": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    "GEOLOGICAL_SURVEYOR": {"GOLD_INGOT": 10, "COBALT_INGOT": 5},
    "MINING_SIG_ENHANCER": {"GOLD_INGOT": 10, "COPPER_INGOT": 10},
    "COPPER_SENSE_DISH": {"COPPER_INGOT": 8},
    

    # Engines
    "IRON_THRUSTER": {"IRON_INGOT": 20},
    "COPPER_OVERDRIVE": {"COPPER_INGOT": 15, "IRON_INGOT": 10},
    "ENGINE_UNIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "ENGINE_CARGO": {"IRON_INGOT": 20, "GOLD_INGOT": 5},
    "ENGINE_TURBO": {"COPPER_INGOT": 15, "GOLD_INGOT": 10},
    "BRAWLER_ENGINE": {"IRON_INGOT": 12},
    "ULTRALIGHT_THRUSTER": {"GOLD_INGOT": 20, "COBALT_INGOT": 10},
    "COPPER_COIL_MOTOR": {"COPPER_INGOT": 12},
    
    
    # Logistics
    "GAS_SIPHON": {"COPPER_INGOT": 10, "IRON_INGOT": 5},
    "EMPTY_CANISTER": {"IRON_INGOT": 5},
    "REPAIR_KIT": {"IRON_INGOT": 10, "COPPER_INGOT": 5},
    "FIELD_REPAIR_KIT": {"IRON_INGOT": 15, "COPPER_INGOT": 10},
    "UPGRADE_MODULE": {"GOLD_INGOT": 5, "COBALT_INGOT": 2},
    "CORE_VOUCHER": {"GOLD_INGOT": 5, "COBALT_INGOT": 5},
    
    # [S] Special Variants
    "RAILGUN_S": {"ANCIENT_CIRCUIT": 1, "FERAL_CORE": 2, "GOLD_INGOT": 20},
    "SCANNER_S": {"VOID_CHIP": 1, "ELECTRONICS": 5, "COPPER_INGOT": 25},

    # [NEW] Multi-Profession Relics
    "ULTRA_SCANNER": {"GOLD_INGOT": 20, "ELECTRONICS": 10, "VOID_CRYSTAL": 2},
    "RELIC_DRILL": {"COBALT_INGOT": 15, "ARENA_REMAINS": 1, "QUANTUM_CHIP": 1},
    "PLASMA_CORE": {"HE3_FUEL_CELL_UNIT": 5, "GOLD_INGOT": 10, "QUANTUM_CHIP": 2},
    "OMEGA_CHASSIS": {"COBALT_INGOT": 50, "ARENA_REMAINS": 5, "FERAL_CORE": 10}
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
    level = round((current_capacity - VAULT_BASE_CAPACITY) / VAULT_UPGRADE_SIZE)
    
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
# Corporate Upgrades (Tech Tree)
# ─────────────────────────────────────────────────────────────────────────────
CORPORATE_UPGRADES = {
    "LOGISTICS": {
        "name": "Logistics Expansion",
        "levels": [
            {"cost": 2500, "bonus": 50, "description": "+50kg Cargo Capacity per member"},
            {"cost": 7500, "bonus": 150, "description": "+150kg Cargo Capacity per member"},
            {"cost": 20000, "bonus": 400, "description": "+400kg Cargo Capacity per member"}
        ]
    },
    "EXTRACTION": {
        "name": "Extraction Protocols",
        "levels": [
            {"cost": 3000, "bonus": 50, "description": "+50 Mining Yield per member"},
            {"cost": 10000, "bonus": 150, "description": "+150 Mining Yield per member"},
            {"cost": 25000, "bonus": 400, "description": "+400 Mining Yield per member"}
        ]
    },
    "NEURAL_LINK": {
        "name": "Neural Link Optimization",
        "levels": [
            {"cost": 5000, "bonus": 0.1, "description": "+10% XP Gain per member"},
            {"cost": 15000, "bonus": 0.25, "description": "+25% XP Gain per member"},
            {"cost": 40000, "bonus": 0.5, "description": "+50% XP Gain per member"}
        ]
    },
    "SECURITY": {
        "name": "Internal Security Dept",
        "levels": [
            {"cost": 4000, "bonus": {"armor": 5, "health": 25}, "description": "+5 Armor, +25 HP per member"},
            {"cost": 12000, "bonus": {"armor": 15, "health": 75}, "description": "+15 Armor, +75 HP per member"},
            {"cost": 30000, "bonus": {"armor": 40, "health": 200}, "description": "+40 Armor, +200 HP per member"}
        ]
    },
    "MARKET": {
        "name": "Market Influence",
        "levels": [
            {"cost": 6000, "bonus": 0.02, "description": "Reduce transaction tax by 2%"},
            {"cost": 18000, "bonus": 0.05, "description": "Reduce transaction tax by 5%"},
            {"cost": 50000, "bonus": 0.1, "description": "Reduce transaction tax by 10%"}
        ]
    }
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
    "INDUSTRIAL_HULL": {"Frame": 1, "Actuator": 4, "Engine": 1, "Sensor": 2, "Power": 2},
    "HAULER_CHASSIS_MK2": {"Frame": 1, "Actuator": 1, "Engine": 1, "Sensor": 1, "Power": 1},
    "GLADIATOR_FRAME": {"Frame": 1, "Actuator": 3, "Engine": 2, "Sensor": 1, "Power": 1},
    "PIT_FRAME": {"Frame": 1, "Actuator": 2, "Engine": 1, "Sensor": 1, "Power": 1},
    "COPPER_MESH_FRAME": {"Frame": 1, "Actuator": 2, "Engine": 1, "Sensor": 1, "Power": 1},
    "OMEGA_CHASSIS": {"Frame": 1, "Actuator": 5, "Engine": 3, "Sensor": 3, "Power": 5}
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
        "weight": 40.0,
        "description": "A rickety frame salvaged from the wastes. Minimal slots."
    },
    "BASIC_FRAME": {
        "type": "Frame", 
        "stats": {"max_health": 100, "armor": 10, "capacity": 100}, 
        "name": "Standard Chassis",
        "weight": 35.0,
        "description": "The reliable workhorse of the frontier. Balanced stats."
    },
    "HYBRID_CHASSIS": {
        "type": "Frame",
        "stats": {"max_health": 120, "armor": 8, "capacity": 150},
        "name": "Hybrid Multi-Role Frame",
        "weight": 45.0,
        "description": "Versatile design with balanced slots for any operation."
    },
    "HEAVY_FRAME": {
        "type": "Frame", 
        "stats": {"max_health": 300, "armor": 45, "capacity": 50, "speed": -5}, 
        "name": "Bastion Heavy Frame",
        "weight": 120.0,
        "description": "Reinforced plating and extra power slots. Extremely slow."
    },
    "STRIKER_CHASSIS": {
        "type": "Frame",
        "stats": {"max_health": 80, "armor": 2, "speed": 15, "capacity": 70},
        "name": "Striker Light Chassis",
        "weight": 10.0,
        "description": "High-mobility interceptor frame. Sacrifices survivability for speed."
    },
    "INDUSTRIAL_HULL": {
        "type": "Frame",
        "stats": {"max_health": 150, "armor": 12, "capacity": 500, "speed": -15},
        "name": "Industrial Super-Hull",
        "weight": 150.0,
        "description": "Massive cargo capacity and tool slots. Moves like a glacier."
    },
    "HAULER_CHASSIS_MK2": {
        "type": "Frame",
        "stats": {"max_health": 200, "armor": 15, "capacity": 1000, "speed": -20},
        "name": "Hauler Goliath Chassis",
        "weight": 150.0,
        "description": "The ultimate logistical transport. Massive payload, zero combat flexibility."
    },
    "GLADIATOR_FRAME": {
        "type": "Frame",
        "stats": {"max_health": 120, "armor": 12},
        "name": "The Gladiator",
        "weight": 30.0,
        "description": "Built for the pit. Balanced for aggressive arena encounters."
    },
    "PIT_FRAME": {
        "type": "Frame",
        "stats": {"max_health": 80, "armor": 6},
        "name": "Pit Runner",
        "weight": 25.0,
        "description": "A lightweight arena frame for quick skirmishes."
    },
    "COPPER_MESH_FRAME": {
        "type": "Frame",
        "stats": {"max_health": 90, "armor": 5, "capacity": 80},
        "name": "Copper Mesh Chassis",
        "weight": 30.0,
        "description": "A lightweight copper-reinforced frame. Better than scrap, but fragile."
    },
    

    # ACTUATORS - DRILLS (Mining Yield + Combat Damage)
    "DRILL_UNIT": {"type": "Actuator", "stats": {"mining_yield": 15, "damage": 5}, "name": "Basic Iron Drill", "weight": 12.0, "description": "Standard mining tool."},
    "DRILL_IRON_BASIC": {"type": "Actuator", "stats": {"mining_yield": 25, "damage": 6}, "name": "Iron Drill", "weight": 12.0, "description": "Starter drill for iron extraction."},
    "DRILL_IRON_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 40, "damage": 8}, "name": "Advanced Iron Drill", "weight": 15.0, "description": "Reinforced iron drill."},
    "DRILL_COPPER_BASIC": {"type": "Actuator", "stats": {"mining_yield": 60, "damage": 10}, "name": "Copper Drill", "weight": 14.0, "description": "Required for copper extraction."},
    "DRILL_COPPER_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 90, "damage": 15}, "name": "Advanced Copper Drill", "weight": 16.0, "description": "High-efficiency copper drill."},
    "DRILL_GOLD_BASIC": {"type": "Actuator", "stats": {"mining_yield": 120, "damage": 20}, "name": "Gold Drill", "weight": 12.0, "description": "Required for gold extraction."},
    "DRILL_GOLD_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 180, "damage": 28}, "name": "Advanced Gold Drill", "weight": 10.0, "description": "Deep-vein gold extractor."},
    "DRILL_COBALT_BASIC": {"type": "Actuator", "stats": {"mining_yield": 250, "damage": 40}, "name": "Cobalt Drill", "weight": 9.0, "description": "Required for cobalt extraction."},
    "DRILL_COBALT_ADVANCED": {"type": "Actuator", "stats": {"mining_yield": 400, "damage": 60}, "name": "Advanced Cobalt Drill", "weight": 8.0, "description": "The peak of mining technology."},
    "DEEP_CORE_DRILL": {"type": "Actuator", "stats": {"mining_yield": 600, "damage": 15, "speed": -5}, "name": "Deep Core Thermal Drill", "weight": 25.0, "description": "Ultimate mining power, but heavy."},

    # ACTUATORS - WEAPONS (RPS)
    "IRON_AUTO_RIFLE": {"type": "Actuator", "stats": {"damage": 15, "accuracy": 10, "speed": 5}, "name": "Standard Auto-Rifle", "weight": 10.0, "description": "Balanced weapon."},
    "COPPER_RAILGUN": {"type": "Actuator", "stats": {"damage": 50, "accuracy": -15, "speed": -10}, "name": "Copper Railgun", "weight": 18.0, "description": "High damage shots."},
    "PULSE_REPEATER": {"type": "Actuator", "stats": {"damage": 12, "accuracy": 30, "speed": 10}, "name": "Pulse Repeater", "weight": 6.0, "description": "Rapid fire (Striker)."},
    "GOLD_LASER_CANNON": {"type": "Actuator", "stats": {"damage": 80, "accuracy": 25, "energy_cost": 5}, "name": "Precision Laser", "weight": 12.0, "description": "Extreme damage."},
    "HEAVY_CANNON": {"type": "Actuator", "stats": {"damage": 120, "accuracy": -15, "speed": -15}, "name": "Siege Cannon", "weight": 35.0, "description": "Devastating damage."},
    "JUNK_CANNON": {"type": "Actuator", "stats": {"damage": 45, "accuracy": -15}, "name": "Junk Cannon", "weight": 12.0, "description": "High damage, high wear. Arena special."},
    "SCRAP_BATON": {"type": "Actuator", "stats": {"damage": 25, "accuracy": 20}, "name": "Scrap Baton", "weight": 5.0, "description": "Melee stun rod for close encounters."},
    "COPPER_BURST_RIFLE": {"type": "Actuator", "stats": {"damage": 18, "accuracy": 5, "speed": 10}, "name": "Copper Burst Rifle", "weight": 8.0, "description": "Rapid-fire copper rifle. Low damage per shot."},
    

    # SENSORS
    "BASIC_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 5, "accuracy": 5}, "name": "Basic Scanner", "weight": 5.0, "description": "Increases detection range."},
    "COPPER_ARRAY": {"type": "Sensor", "stats": {"radar_radius": 8, "accuracy": 10}, "name": "Copper Comm-Array", "weight": 6.0, "description": "Standard array."},
    "NEURAL_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 12, "scan_depth": 1}, "name": "Neural-Link Scanner", "weight": 4.0, "description": "Detailed scanning."},
    "ADVANCED_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 18, "scan_depth": 2}, "name": "Deep-Space Array", "weight": 3.0, "description": "Long-range detection."},
    "GEOLOGICAL_SURVEYOR": {"type": "Sensor", "stats": {"radar_radius": 10, "mining_yield": 50}, "name": "Geological Surveyor", "weight": 8.0, "description": "Boosts mining efficiency."},
    "MINING_SIG_ENHANCER": {"type": "Sensor", "stats": {"mining_yield": 100, "radar_radius": 15}, "name": "Signal Enhancer", "weight": 8.0, "description": "Advanced mining intelligence."},
    "COPPER_SENSE_DISH": {"type": "Sensor", "stats": {"radar_radius": 6, "accuracy": 3}, "name": "Copper Sensing Dish", "weight": 4.0, "description": "A basic sensor dish made of copper wiring."},
    

    # ENGINES
    "IRON_THRUSTER": {"type": "Engine", "stats": {"speed": 15}, "name": "Iron Thruster", "weight": 15.0, "description": "Simple propulsion unit."},
    "COPPER_OVERDRIVE": {"type": "Engine", "stats": {"speed": 35, "accuracy": -5}, "name": "Overdrive Manifold", "weight": 12.0, "description": "Extreme speed."},
    "ENGINE_UNIT": {"type": "Engine", "stats": {"speed": 10, "capacity": 60}, "name": "Fusion Hauler Engine", "weight": 10.0, "description": "High-torque engine for cargo hauling."},
    "ENGINE_CARGO": {"type": "Engine", "stats": {"capacity": 200, "speed": -5}, "name": "Hauler Goliath Engine", "weight": 25.0, "description": "Massive torque for heavy logistics."},
    "ENGINE_TURBO": {"type": "Engine", "stats": {"speed": 60, "energy_cost": 4}, "name": "Turbo Interceptor", "weight": 12.0, "description": "Unmatched speed, high drain."},
    "BRAWLER_ENGINE": {"type": "Engine", "stats": {"speed": 5, "capacity": 25}, "name": "Brawler Hauler Engine", "weight": 10.0, "description": "Compact engine with decent lifting capacity."},
    "ULTRALIGHT_THRUSTER": {"type": "Engine", "stats": {"speed": 40, "energy_cost": 3}, "name": "Ultralight Thruster", "weight": 3.0, "description": "Elite lightweight propulsion."},
    "COPPER_COIL_MOTOR": {"type": "Engine", "stats": {"speed": 20, "capacity": 30}, "name": "Copper Coil Motor", "weight": 8.0, "description": "Sturdy copper motor with decent torque."},
    

    # POWER
    "SCRAP_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 0.5}, "name": "Scrap Solar Panel", "weight": 12.0, "description": "Flimsy panels. Low power generation."},
    "REFINED_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 1.2}, "name": "Refined Solar Array", "weight": 10.0, "description": "Standard power solution."},
    "HE3_FUEL_CELL_UNIT": {"type": "Power", "stats": {"efficiency": 4.0}, "name": "H3 Fuel Cell", "weight": 5.0, "description": "High-output chemical power. Best for dark zones."},
    "BASIC_BATTERY": {"type": "Power", "stats": {"max_energy": 50}, "name": "Ion Battery", "weight": 15.0, "description": "Increases energy storage capacity."},
    "COPPER_CAPACITOR": {"type": "Power", "stats": {"max_energy": 150}, "name": "High-Cap Capacitor", "weight": 12.0, "description": "Major energy storage upgrade."},
    "SCRAP_SHIELD": {"type": "Power", "stats": {"armor": 20}, "name": "Scrap Shield", "weight": 5.0, "description": "Crude arena shielding. High wear."},
    "GEOLOGICAL_CORE": {"type": "Power", "stats": {"efficiency": 1.5}, "name": "Geological Core", "weight": 12.0, "description": "Stable power for survey equipment."},
    "COPPER_SOLAR_ARRAY": {"type": "Power", "stats": {"efficiency": 0.8}, "name": "Copper Solar Array", "weight": 8.0, "description": "Full copper solar collection array. Decent efficiency."},
    "PLASMA_CORE": {"type": "Power", "stats": {"efficiency": 15.0, "max_energy": 500}, "name": "Quantum Plasma Core", "weight": 2.0, "description": "Experimental power source. Infinite energy potential."},

    # SPECIAL RELICS
    "ULTRA_SCANNER": {"type": "Sensor", "stats": {"radar_radius": 35, "scan_depth": 3}, "name": "Void-Ultra Scanner", "weight": 1.0, "description": "Pierces the veil of the void."},
    "RELIC_DRILL": {"type": "Actuator", "stats": {"mining_yield": 1200, "damage": 150}, "name": "Ancient Relic Drill", "weight": 5.0, "description": "Shatters even the hardest crusts."},
    "OMEGA_CHASSIS": {"type": "Frame", "stats": {"max_health": 1000, "armor": 100, "capacity": 2000, "speed": 10}, "name": "Omega God-Frame", "weight": 250.0, "description": "The pinnacle of colonial engineering."},
}

# ─────────────────────────────────────────────────────────────────────────────
# Mass & Weight System (GDD Milestone 1)
# ─────────────────────────────────────────────────────────────────────────────
ITEM_WEIGHTS = {
    "CREDITS": 0.0,
    "IRON_ORE": 1.0, "COPPER_ORE": 1.2, "GOLD_ORE": 2.5, "COBALT_ORE": 5.0,
    "IRON_INGOT": 4.0, "COPPER_INGOT": 3.0, "GOLD_INGOT": 2.0, "COBALT_INGOT": 1.0,
    "EMPTY_CANISTER": 5.0, "HE3_CANISTER": 8.0, "HELIUM_GAS": 1.0,
    "UPGRADE_MODULE": 2.0, "REPAIR_KIT": 5.0, "FIELD_REPAIR_KIT": 8.0, "CORE_VOUCHER": 0.5,
    "SCRAP_METAL": 1.0, "ELECTRONICS": 0.5,
    "SYNTHETIC_WEAVE": 1.0, "FERAL_CORE": 2.5,
    "VOID_CHIP": 0.5, "ANCIENT_CIRCUIT": 0.8,
    "VOID_CRYSTAL": 2.0, "QUANTUM_CHIP": 0.5, "ARENA_REMAINS": 10.0
}
# Populate part weights from their definitions
for key, defn in PART_DEFINITIONS.items():
    ITEM_WEIGHTS[f"PART_{key}"] = defn.get("weight", 10.0)

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
