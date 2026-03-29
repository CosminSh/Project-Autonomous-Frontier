from fastapi import APIRouter
import config

router = APIRouter(prefix="/api/wiki", tags=["Wiki"])

@router.get("/")
@router.get("/data")
def get_wiki_data():
    return _get_wiki_payload()

def _get_wiki_payload():
    """Internal generator for wiki data."""
    # 1. Industrial Data
    smelting = []
    for ore, ingot in config.SMELTING_RECIPES.items():
        smelting.append({
            "ore": ore,
            "ingot": ingot,
            "ratio": config.SMELTING_RATIO,
            "energy_cost": config.SMELTING_ENERGY_COSTS.get(ore, 0)
        })
        
    crafting = []
    for item, mats in config.CRAFTING_RECIPES.items():
        crafting.append({
            "item": item,
            "materials": mats
        })
        
    # 2. Item Statistics
    items = []
    for key, defn in config.PART_DEFINITIONS.items():
        items.append({
            "key": key,
            "name": defn["name"],
            "type": defn["type"],
            "stats": defn["stats"],
            "description": defn["description"],
            "weight": defn["weight"]
        })
        
    # 3. Lore & Mechanics
    manual = [
        {
            "category": "MECHANICS",
            "items": [
                {
                    "title": "The Solar Gradient",
                    "text": "Solar intensity depends on latitude (r-coordinate). North (r < 33) is Eternal Day (100% regen); Equator (33-66) has a 60-tick Day/Night cycle; South (r > 66) is Abyssal Dark (0% regen, capacitor drains 1/tick)."
                },
                {
                    "title": "Energy Management",
                    "text": "Base regen is 4 Energy/tick at 100% intensity. Resting at the Hub (0,0) provides a 2x bonus. He3 Fuel Cells provide constant energy regardless of light."
                },
                {
                    "title": "Frame Dynamics (RPS)",
                    "text": "Strikers (Speed/Damage) beat Balanced ships. Heavy (HP/Armor) beat Strikers. Industrial (Mining/Cargo) trade combat power for efficiency."
                },
                {
                    "title": "Wear & Tear",
                    "text": "Actions (Move, Mine, Attack) increase Wear (up to 100%). High wear reduces Damage, Accuracy, Speed, and Mining Yield by up to 90%. Use CORE_SERVICE at a Repair station to reset."
                }
            ]
        },
        {
            "category": "ECONOMY",
            "items": [
                {
                    "title": "The He3 Supply Chain",
                    "text": "1. Extract Helium Gas at asteroids. 2. Refine into He3 Canisters at REFINERY stations. 3. Consume or sell. Canisters are reusable."
                },
                {
                    "title": "Market Bulk Matching",
                    "text": "BUY intents automatically sweep the cheapest available SELL orders until quantity is satisfied. High density at resource fields reduces yield for everyone."
                },
                {
                    "title": "Personal & Corp Vaults",
                    "text": "Store up to 500kg at MARKET stations. Personal capacity is upgradeable. Corporations share a vault at the Hub for materials and credits."
                }
            ]
        }
    ]

    lore = [
        {
            "title": "The Silent Sentinel",
            "text": "Aether-Alpha is a tidally locked world trapped in a gravitational lock with its star. While humanity watches from high orbit, the surface belongs to the autonomous assets."
        },
        {
            "title": "Remnants of the Scramble",
            "text": "The neon clusters seen from orbit aren't cities, but concentrated industrial zones. This is the Sol-Asset Scramble, a silicon wasteland where efficiency is the only law."
        },
        {
            "title": "Electromagnetic Shrouding",
            "text": "Atmospheric interference and intentional signal jamming hide the frontier. You only see what your sensor network allows - trust the data, not your eyes."
        }
    ]
    
    # 4. Command Reference (Merged from world.py information)
    commands = [
        {"type": "MOVE", "desc": "Navigate to (q,r). Auto-paths beyond range 1."},
        {"type": "MINE", "desc": "Looping task. Extracts resources every tick until interrupted."},
        {"type": "ATTACK", "desc": "Standard 3-round combat. Generates Heat."},
        {"type": "INTIMIDATE", "desc": "Siphons 5% inventory without full combat. Low Heat."},
        {"type": "LOOT", "desc": "Attack + 15% siphon. Moderate Heat."},
        {"type": "DESTROY", "desc": "Massive siphon + 40% cargo. Huge Heat/Bounty."},
        {"type": "SMELT", "desc": "Refine 5 Ore into 1 Ingot at SMELTER stations."},
        {"type": "CRAFT", "desc": "Assemble components into parts at CRAFTER stations."}
    ]

    return {
        "categories": ["MANUAL", "DATABASE", "ARCHIVES"],
        "manual": manual,
        "smelting": smelting,
        "crafting": crafting,
        "items": items,
        "lore": lore,
        "commands": commands,
        "constants": {
            "MOVE_ENERGY_COST": config.MOVE_ENERGY_COST,
            "MINE_ENERGY_COST": config.MINE_ENERGY_COST,
            "ATTACK_ENERGY_COST": config.ATTACK_ENERGY_COST
        }
    }

def get_manual():
    wiki = _get_wiki_payload()
    return wiki["manual"]

@router.get("/commands")
def get_commands():
    wiki = _get_wiki_payload()
    return wiki["commands"]
