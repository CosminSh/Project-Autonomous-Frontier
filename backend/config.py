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
TOWN_COORDINATES = (0, 0)
ANARCHY_THRESHOLD = 5
SOLAR_RADIUS_SAFE = 10
SOLAR_RADIUS_TWILIGHT = 20
CLUTTER_THRESHOLD = 3
CLUTTER_PENALTY = 0.2  # 20% reduction

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
    "BASIC_FRAME": {"IRON_INGOT": 10},
    "HEAVY_FRAME": {"IRON_INGOT": 20, "COBALT_INGOT": 10},
    "DRILL_UNIT": {"IRON_INGOT": 5, "COPPER_INGOT": 5},
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
    "REPAIR_KIT": {"IRON_INGOT": 10, "COPPER_INGOT": 5}
}

CORE_RECIPES = ["BASIC_FRAME", "HEAVY_FRAME", "DRILL_UNIT", "EMPTY_CANISTER", "UPGRADE_MODULE", "ENGINE_UNIT", "SCRAP_SOLAR_PANEL", "REPAIR_KIT"]
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
    "Hardened": {"integrity": 5},
    "Precise": {"logic_precision": 8},
    "Dense": {"max_structure": 25},
    "Reactive": {"logic_precision": 4, "overclock": 4},
    "Bulk": {"capacity": 50},
    "Swift": {"kinetic_force": 5}
}

REPAIR_COST_PER_HP = 5  # Credits per HP restored
REPAIR_COST_IRON_INGOT_PER_HP = 0.1  # 1 Ingot per 10 HP
CORE_SERVICE_COST_CREDITS = 500
CORE_SERVICE_COST_IRON_INGOT = 10
CANISTER_MAX_FILL = 100  # 100%
GAS_REFINING_RATIO = 10  # 10 Helium -> 10% Canister Fill
FACTION_REALIGNMENT_COST = 500
FACTION_REALIGNMENT_COOLDOWN = 100

# ─────────────────────────────────────────────────────────────────────────────
# Part Stats Definitions
# ─────────────────────────────────────────────────────────────────────────────
PART_DEFINITIONS = {
    "BASIC_FRAME": {"type": "Frame", "stats": {"max_structure": 50, "integrity": 5, "capacity": 50}, "name": "Reinforced Chassis"},
    "HEAVY_FRAME": {"type": "Frame", "stats": {"max_structure": 150, "integrity": 15, "capacity": 30, "kinetic_force": -5}, "name": "Heavy Assault Chassis"},
    "DRILL_UNIT": {"type": "Actuator", "stats": {"kinetic_force": 8, "logic_precision": -2}, "name": "Titanium Mining Drill"},
    "SCRAP_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 0.5}, "name": "Scrap Solar Panel"},
    "REFINED_SOLAR_PANEL": {"type": "Power", "stats": {"efficiency": 1.0}, "name": "Refined Solar Array"},
    "HE3_FUEL_CELL_UNIT": {"type": "Power", "stats": {"efficiency": 2.0}, "name": "Helium-3 Fuel Cell"},
    "NEURAL_SCANNER": {"type": "Sensor", "stats": {"radius": 2, "scan_depth": 1}, "name": "Neural-Link Cargo Scanner"},
    "ADVANCED_SCANNER": {"type": "Sensor", "stats": {"radius": 4, "scan_depth": 1}, "name": "Deep-Space Array Scanner"},
    "GAS_SIPHON": {"type": "Actuator", "stats": {"kinetic_force": 2}, "name": "Helium Gas Siphon"},
    "ENGINE_UNIT": {"type": "Engine", "stats": {"kinetic_force": 5, "capacity": 20}, "name": "Standard Fusion Engine"},
    "ENGINE_CARGO": {"type": "Engine", "stats": {"kinetic_force": 2, "capacity": 60}, "name": "Hauler-Class Cargo Engine"},
    "ENGINE_TURBO": {"type": "Engine", "stats": {"kinetic_force": 15, "capacity": 5}, "name": "Interceptor Turbo Engine"},
    "SHIELD_GENERATOR": {"type": "Frame", "stats": {"integrity": 15, "max_structure": 50}, "name": "Aegis Shield Generator"}
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
    "PART_BASIC_FRAME": 50.0,
    "PART_HEAVY_FRAME": 100.0,
    "PART_DRILL_UNIT": 15.0,
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
    "UPGRADE_MODULE": 2.0,
    "REPAIR_KIT": 5.0
}
BASE_CAPACITY = 100.0


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
