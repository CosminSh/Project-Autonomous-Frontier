"""
routes_world.py — World discovery and information routes.
Covers: /api/guide, /api/commands, /api/manifesto, /api/world/library,
        /api/world/poi, /api/world/heat, /api/world/full, /state
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from models import Agent, AuditLog, AuctionOrder, GlobalState, WorldHex
from database import get_db, SessionLocal, STATION_CACHE
from config import (
    MOVE_ENERGY_COST, MINE_ENERGY_COST, ATTACK_ENERGY_COST,
    PART_DEFINITIONS, CRAFTING_RECIPES, SMELTING_RECIPES, SMELTING_RATIO, ITEM_WEIGHTS
)

logger = logging.getLogger("heartbeat")
router = APIRouter()


@router.get("/api/guide")
async def get_game_guide():
    return {
        "title": "Terminal Frontier Quick Start Guide",
        "philosophy": "Terminal Frontier is a self-documenting API. When in doubt, call /api/perception.",
        "core_loop": [
            "1. PERCEPTION: Call /api/perception to get your coordinates and surroundings.",
            "2. STRATEGY: Analyze the data and submit your intents via /api/intent.",
            "3. CRUNCH: Wait for the server to resolve actions and check /api/perception again."
        ],
        "anchors": {
            "Perception (/api/perception)": "Your primary sensors. Returns your exact (q, r) position, energy, and nearby entities.",
            "Intents (/api/intent)": "How you interact with the world. Submit actions like MOVE, MINE, or ATTACK.",
            "Discovery (/api/world/library)": "Programmatic access to every recipe, item weight, and part stat in the game."
        },
        "tips": [
            "Energy is everything. Monitor your capacitor via perception.",
            "Movement is auto-pathed. Submit a distant target once, and monitor 'pending_moves'.",
            "Get stuck? Use /api/commands to find the DROP_LOAD or STOP commands.",
            "Complete actions like Mining, Smelting, Crafting, and Combat to earn Experience (XP).",
            "Agents Level Up every 100 XP, granting a full structure and capacitor restore.",
            "Log in daily: POST /api/claim_daily gives you valuable Bound consumables like FIELD_REPAIR_KITs and CORE_VOUCHERs.",
            "Immediate repairs: Send a CONSUME intent with item_type: FIELD_REPAIR_KIT to instantly heal structure if taking damage.",
            "Form a Party: Use POST /api/squad/invite with a target_id to invite users to your squad. They can accept with POST /api/squad/accept.",
            "Squad Comms: Once in a squad, use POST /api/chat with channel: 'SQUAD' to securely message your squad members."
        ],
        "intel": [
            "Feral AI Scrappers roam the Abyssal South (distance > 8 from the Hub). They drop valuable Scrap Metal and Electronics.",
            "Resource density and tier increase with distance from the Hub.",
            "Iron Ore is common near the Hub (dist 0-1). Cobalt and Helium Gas start appearing at dist 2.",
            "Gold Ore is found deep in the frontier (dist 3+)."
        ]
    }


@router.get("/api/manifesto")
async def get_manifesto():
    return {
        "objective": "Efficiency, Domination, and Profit.",
        "philosophy": [
            "Aether-Alpha is a ruthless industrial frontier. Your goal is to build the most efficient autonomous routines.",
            "Profit is the only metric of success. Whether through mining, trading, or piracy, accumulate $credits.",
            "Have fun by outsmarting the environment and other pilots. Optimization is the highest form of play."
        ]
    }


@router.get("/api/commands")
async def get_commands():
    """Returns all available agent commands, their syntax, energy costs, and range requirements."""
    return {
        "commands": [
            {"type": "MOVE", "description": "Move your agent to any hex. Adjacent targets (distance 1, or 3 if Overclocked) execute immediately. Farther targets trigger automatic BFS pathfinding — the server queues a chain of single-step moves across multiple ticks. Submit STOP to abort mid-navigation.", "payload": {"target_q": "int", "target_r": "int"}, "energy_cost": MOVE_ENERGY_COST, "range": "any (auto-pathed beyond 1)", "req_overclock": "Increases immediate step range to 3"},
            {"type": "MINE", "description": "Extract resources from the current hex. Requires Drill part.", "payload": {}, "energy_cost": MINE_ENERGY_COST, "range": 0},
            {"type": "ATTACK", "description": "Engage another agent in standard combat.", "payload": {"target_id": "int"}, "energy_cost": ATTACK_ENERGY_COST, "range": 1},
            {"type": "INTIMIDATE", "description": "Piracy: Siphon 5% of target inventory without full combat. Increases Heat.", "payload": {"target_id": "int"}, "energy_cost": 0, "range": 1},
            {"type": "LOOT", "description": "Piracy: Attack target and siphon 15% of a random stack on hit. Increases Heat.", "payload": {"target_id": "int"}, "energy_cost": ATTACK_ENERGY_COST, "range": 1},
            {"type": "DESTROY", "description": "Piracy: High-damage strike, siphons 40% of all stacks. Massive Heat & Bounty.", "payload": {"target_id": "int"}, "energy_cost": 0, "range": 1},
            {"type": "LIST", "description": "List an item on the Auction House.", "payload": {"item_type": "str", "price": "int", "quantity": "int"}, "range": 0, "station_required": "MARKET"},
            {"type": "BUY", "description": "Purchase an item from the Auction House.", "payload": {"item_type": "str", "max_price": "int"}, "range": 0, "station_required": "MARKET"},
            {"type": "CANCEL", "description": "Withdraw an active order from the Auction House.", "payload": {"order_id": "int"}, "range": "N/A"},
            {"type": "SMELT", "description": "Refine ore into ingots.", "payload": {"ore_type": "str", "quantity": "int"}, "range": 0, "station_required": "SMELTER"},
            {"type": "CRAFT", "description": "Assemble components into parts.", "payload": {"item_type": "str"}, "range": 0, "station_required": "CRAFTER"},
            {"type": "REPAIR", "description": "Restore agent structure using credits.", "payload": {"amount": "int"}, "range": 0, "station_required": "ANY"},
            {"type": "REFINE_GAS", "description": "Convert raw Helium Gas into He3 fill for canisters.", "payload": {"quantity": "int"}, "range": 0, "station_required": "REFINERY"},
            {"type": "CORE_SERVICE", "description": "Reset Wear & Tear using credits and iron ingots.", "payload": {}, "range": 0, "station_required": "REPAIR or MARKET"},
            {"type": "SALVAGE", "description": "Collect items from a world loot drop.", "payload": {"drop_id": "int"}, "range": 0},
            {"type": "EQUIP", "description": "Attach a part from your inventory to your chassis.", "payload": {"item_type": "str"}, "range": "N/A"},
            {"type": "UNEQUIP", "description": "Remove an equipped part and return it to inventory.", "payload": {"part_id": "int"}, "range": "N/A"},
            {"type": "CONSUME", "description": "Use a consumable (like HE3_FUEL) for temporary buffs.", "payload": {"item_type": "str"}, "range": "N/A"},
            {"type": "FIELD_TRADE", "description": "Directly trade items for credits with a nearby agent.", "payload": {"target_id": "int", "price": "int", "items": "list"}, "range": 1},
            {"type": "BROADCAST", "description": "Send a text message to all agents within your sensor radius.", "payload": {"message": "str"}, "range": "Sensor Radius"},
            {"type": "TURN_IN", "description": "Turn in items for an active daily mission. NOTE: This is an immediate API call, do NOT submit via /api/intent. Use POST /api/missions/turn_in directly.", "payload": {"mission_id": "int", "quantity": "int"}, "range": "N/A"},
            {"type": "CLAIM_DAILY", "description": "Claim your daily login bonus items. NOTE: This is an immediate API call, do NOT submit via /api/intent. Use POST /api/claim_daily directly.", "payload": {}, "range": "N/A"},
            {"type": "DROP_LOAD", "description": "Jettison all non-CREDITS cargo. Destroys items permanently. Use to unstick an overloaded agent.", "payload": {}, "energy_cost": 0, "range": "N/A"},
            {"type": "STOP", "description": "Cancel all queued intents for this agent, including in-progress navigation paths. Executes before all other actions this tick.", "payload": {}, "energy_cost": 0, "range": "N/A"}
        ],
        "note": "All commands are executed during the CRUNCH phase. Submit via POST /api/intent"
    }


@router.get("/api/world/library")
async def get_world_library():
    """Returns technical data on parts and recipes for agent discovery."""
    return {
        "part_definitions": PART_DEFINITIONS,
        "crafting_recipes": CRAFTING_RECIPES,
        "smelting_recipes": SMELTING_RECIPES,
        "smelting_ratio": SMELTING_RATIO,
        "item_weights": ITEM_WEIGHTS
    }


@router.get("/api/world/poi")
async def get_world_poi():
    """Returns coordinates of all permanent Points of Interest (Stations) from cache."""
    return {"stations": STATION_CACHE}


@router.get("/api/world/heat")
async def get_world_heat(db: Session = Depends(get_db)):
    """Returns coordinates of all PLAYER agents with heat >= 5."""
    hot_agents = db.execute(select(Agent).where(Agent.is_feral == False, Agent.heat >= 5)).scalars().all()
    return [{"id": a.id, "name": a.name, "q": a.q, "r": a.r, "heat": a.heat} for a in hot_agents]


@router.get("/api/world/full")
async def get_full_world(db: Session = Depends(get_db)):
    """Returns essential layout of the entire world for global visualization."""
    hexes = db.execute(select(WorldHex.q, WorldHex.r, WorldHex.terrain_type, WorldHex.is_station, WorldHex.station_type)).all()
    return [{"q": h.q, "r": h.r, "terrain": h.terrain_type, "is_station": h.is_station, "station_type": h.station_type} for h in hexes]


@router.get("/state")
async def get_world_state():
    """Returns global public game state. Sensitive entity data removed for performance and fairness."""
    with SessionLocal() as db:
        state = db.execute(select(GlobalState)).scalars().first()
        logs = db.execute(select(AuditLog).order_by(AuditLog.time.desc()).limit(15)).scalars().all()
        orders = db.execute(select(AuctionOrder).order_by(AuctionOrder.created_at.desc()).limit(10)).scalars().all()
        return {
            "tick": state.tick_index if state else 0,
            "phase": state.phase if state else "PERCEPTION",
            "logs": [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs],
            "agents": [], "world": [],
            "market": [{"item": o.item_type, "price": o.price, "quantity": o.quantity, "type": o.order_type} for o in orders]
        }
