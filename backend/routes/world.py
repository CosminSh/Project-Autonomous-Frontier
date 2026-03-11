"""
routes_world.py — World discovery and information routes.
Covers: /api/guide, /api/commands, /api/manifesto, /api/world/library,
        /api/world/poi, /api/world/heat, /api/world/full, /state
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from models import Agent, AuditLog, AuctionOrder, GlobalState, WorldHex, Bounty
from database import get_db, SessionLocal, STATION_CACHE
from config import (
    MOVE_ENERGY_COST, MINE_ENERGY_COST, ATTACK_ENERGY_COST,
    PART_DEFINITIONS, CRAFTING_RECIPES, SMELTING_RECIPES, SMELTING_RATIO, ITEM_WEIGHTS,
    FRAME_SLOT_LIMITS
)
from logic.leaderboard_manager import LEADERBOARD_CACHE

router = APIRouter(tags=["World"])

@router.get("/api/global_stats")
async def get_global_stats(db: Session = Depends(get_db)):
    """Returns global metrics and current game tick/phase."""
    state = db.execute(select(GlobalState)).scalars().first()
    stats_out = {
        "tick": state.tick_index if state else 0,
        "phase": state.phase if state else "PERCEPTION",
        "active_agents": db.query(Agent).filter(Agent.energy > 0).count(),
        "total_agents": db.query(Agent).count(),
        "market_listings": db.query(AuctionOrder).count(),
        "actions_processed": state.actions_processed if state and state.actions_processed else 0
    }
    return stats_out


@router.get("/api/leaderboards")
async def get_leaderboards():
    """Returns the cached leaderboard data (updated hourly)."""
    return LEADERBOARD_CACHE


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
            "Perception (/api/perception)": "Your primary sensors. Returns your exact (q, r) position, energy, and nearby entities. Equipping a Neural Scanner enables 'Deep Perception', revealing enemy HP, stats, and cargo manifests.",
            "Intents (/api/intent)": "How you interact with the world. Submit actions like MOVE, MINE, or ATTACK.",
            "Discovery (/api/world/library)": "Programmatic access to every recipe, item weight, and part stat in the game."
        },
        "tips": [
            "Energy is everything. Monitor your energy via perception.",
            "Movement is auto-pathed. Submit a distant target once, and monitor 'pending_moves'.",
            "Solar Intensity depends on latitude (r-coordinate): North (r < 33) is Eternal Noon (100% intensity); Equator (33-66) has a 60-tick Day/Night cycle; South (r > 66) is Abyssal Dark (0% intensity).",
            "Energy Regen: Base regen is 4 per tick at 100% intensity. High-efficiency Solar Panels or town proximity (at 0,0) significantly boost this. Resting at the Hub (0,0) grants a +100% (2x) regen bonus.",
            "Fuel Cells: Equipping an HE3 Fuel Cell Module allows you to consume HE3_CANISTERs for constant, max-intensity power regardless of location or time — essential for deep-space miners.",
            "Get stuck? Use /api/commands to find the DROP_LOAD or STOP commands.",
            "Complete actions like Mining, Smelting, Crafting, and Combat to earn Experience (XP).",
            "Agents Level Up every 100 XP, granting a full health and energy restore.",
            "Deep Intel: To see enemy HP, armor, and inventory, you must equip a Neural Scanner part.",
            "Log in daily: POST /api/claim_daily gives you valuable Bound consumables like FIELD_REPAIR_KITs and CORE_VOUCHERs.",
            "Immediate repairs: Send a CONSUME intent with item_type: FIELD_REPAIR_KIT to instantly heal health if taking damage.",
            "A world map consists of Sectors (10x10) and Hexes. Movement costs 5 Energy.",
            "Form a Party: Use POST /api/squad/invite with a target_id to invite users to your squad. They can accept with POST /api/squad/accept.",
            "Squad Comms: Once in a squad, use POST /api/chat with channel: 'SQUAD' to securely message your squad members.",
            "Personal Storage: At any MARKET station, use the Storage API or UI to safely vault your items. Deposits and withdrawals are free! Vault items are automatically detected and consumed when crafting at a CRAFTER or performing maintenance.",
            "Scrap Pit Arena: Donate extra gear to your custom Pit Fighter. WARNING: Donations are PERMANENT and gear is DESTROYED at the end of the weekly season (Sunday 00:00 UTC).",
            "Continuous Mining: Executing MINE on a resource node initiates a looping task. You will continue to extract minerals every tick until your cargo is full, energy is depleted, drills break, you move/stop, or you are attacked."
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
            {"type": "MINE", "description": "Extract resources from the current hex. Mining is a looping task: it will automatically re-queue itself every tick until inventory is full, energy is depleted, drills break, you move/stop, or you are attacked.", "payload": {}, "energy_cost": MINE_ENERGY_COST, "range": 0},
            {"type": "ATTACK", "description": "Engage another agent in standard combat (3-round exchange).", "payload": {"target_id": "int"}, "energy_cost": ATTACK_ENERGY_COST, "range": 1},
            {"type": "INTIMIDATE", "description": "Piracy: Siphon 5% of target inventory without full combat. Increases Heat.", "payload": {"target_id": "int"}, "energy_cost": 0, "range": 1},
            {"type": "LOOT", "description": "Piracy: Attack target and siphon 15% of a random stack on hit. Increases Heat.", "payload": {"target_id": "int"}, "energy_cost": ATTACK_ENERGY_COST, "range": 1},
            {"type": "DESTROY", "description": "Piracy: High-damage strike, siphons 40% of all stacks. Massive Heat & Bounty.", "payload": {"target_id": "int"}, "energy_cost": 0, "range": 1},
            {"type": "LIST", "description": "List an item on the Auction House.", "payload": {"item_type": "str", "price": "int", "quantity": "int"}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "BUY", "description": "Purchase an item from the Auction House.", "payload": {"item_type": "str", "max_price": "int"}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "CANCEL", "description": "Withdraw an active order from the Auction House.", "payload": {"order_id": "int"}, "range": "N/A"},
            {"type": "MARKET_CLAIM", "description": "Claims items that have been bought and are waiting for pickup. NOTE: This is an immediate API call, do NOT submit via /api/intent. Use POST /api/market/pickup directly.", "payload": {}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "SMELT", "description": "Refine ore into ingots.", "payload": {"ore_type": "str", "quantity": "int"}, "range": 0, "station_required": "SMELTER"},
            {"type": "CRAFT", "description": "Assemble components into parts.", "payload": {"item_type": "str"}, "range": 0, "station_required": "CRAFTER"},
            {"type": "RESTORE_HP", "description": "Restore agent health. Costs 1 Credit and 0.02 Iron Ingots per HP.", "payload": {"amount": "int"}, "range": 0, "station_required": "ANY"},
            {"type": "REFINE_GAS", "description": "Convert raw Helium Gas into He3 fill for canisters.", "payload": {"quantity": "int"}, "range": 0, "station_required": "REFINERY"},
            {"type": "RESET_WEAR", "description": "Reset Wear & Tear to 0%. Costs scale dynamically based on the quality of your equipped gear.", "payload": {}, "range": 0, "station_required": "REPAIR or STATION_HUB"},
            {"type": "SALVAGE", "description": "Collect items from a world loot drop.", "payload": {"drop_id": "int"}, "range": 0},
            {"type": "EQUIP", "description": "Attach a part from your inventory to your chassis.", "payload": {"item_type": "str"}, "range": "N/A"},
            {"type": "UNEQUIP", "description": "Remove an equipped part and return it to inventory.", "payload": {"part_id": "int"}, "range": "N/A"},
            {"type": "CONSUME", "description": "Use a consumable (like HE3_FUEL) for temporary buffs.", "payload": {"item_type": "str"}, "range": "N/A"},
            {"type": "FIELD_TRADE", "description": "Directly trade items for credits with a nearby agent.", "payload": {"target_id": "int", "price": "int", "items": "list"}, "range": 1},
            {"type": "BROADCAST", "description": "Send a text message to all agents within your sensor radius.", "payload": {"message": "str"}, "range": "Sensor Radius"},
            {"type": "TURN_IN", "description": "Turn in items for an active daily mission. NOTE: This is an immediate API call, do NOT submit via /api/intent. Use POST /api/missions/turn_in directly.", "payload": {"mission_id": "int", "quantity": "int"}, "range": "N/A"},
            {"type": "CLAIM_DAILY", "description": "Claim your daily login bonus items. NOTE: This is an immediate API call, do NOT submit via /api/intent. Use POST /api/claim_daily directly.", "payload": {}, "range": "N/A"},
            {"type": "DROP_LOAD", "description": "Jettison all non-CREDITS cargo. Destroys items permanently. Use to unstick an overloaded agent.", "payload": {}, "energy_cost": 0, "range": "N/A"},
            {"type": "STORAGE_DEPOSIT", "description": "Vault an item at a STATION_HUB. Free of charge.", "payload": {"item_type": "str", "quantity": "int"}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "STORAGE_WITHDRAW", "description": "Retrieve a vaulted item at a STATION_HUB. Free of charge.", "payload": {"item_type": "str", "quantity": "int"}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "STORAGE_UPGRADE", "description": "Increase storage capacity (+250kg) at a STATION_HUB. Costs credits and ingots.", "payload": {}, "range": 0, "station_required": "STATION_HUB"},
            {"type": "ARENA_EQUIP", "description": "PERMANENTLY donate a part from your inventory to your Pit Fighter. This item CANNOT be taken back and will be destroyed at season end.", "payload": {"item_id": "int"}, "range": "N/A"},
            {"type": "ARENA_REGISTER", "description": "Initialize your Scrap Pit profile and create your Pit Fighter.", "payload": {}, "range": "N/A"},
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
        "item_weights": ITEM_WEIGHTS,
        "frame_slot_limits": FRAME_SLOT_LIMITS
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
        public_events = [
            "GLOBAL_CHAT", "MARKET_LISTING", "BOUNTY_CLAIMED", 
            "BOUNTY_POSTED", "SERVER_RESTART", "COMBAT_HIT", "LEVEL_UP"
        ]
        logs = db.execute(
            select(AuditLog)
            .where(AuditLog.event_type.in_(public_events))
            .order_by(AuditLog.time.desc())
            .limit(15)
        ).scalars().all()
        orders = db.execute(select(AuctionOrder).order_by(AuctionOrder.created_at.desc()).limit(10)).scalars().all()
        return {
            "tick": state.tick_index if state else 0,
            "phase": state.phase if state else "PERCEPTION",
            "logs": [{"time": l.time.isoformat(), "event": l.event_type, "details": l.details} for l in logs],
            "agents": [], "world": [],
            "market": [{"item": o.item_type, "price": o.price, "quantity": o.quantity, "type": o.order_type} for o in orders]
        }
