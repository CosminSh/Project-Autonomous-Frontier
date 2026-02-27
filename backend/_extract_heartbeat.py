"""Helper script: extracts heartbeat_loop from main.py and writes heartbeat.py"""

HEADER = '''"""
heartbeat.py - Game engine: tick phases, intent processing, and all action handlers.
Imports manager from main at runtime (injected via heartbeat.manager = manager).
"""
import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from models import (Agent, Intent, AuditLog, WorldHex, ChassisPart,
                    InventoryItem, AuctionOrder, GlobalState, Bounty, LootDrop)
from database import SessionLocal, STATION_CACHE
from config import (
    MOVE_ENERGY_COST, MINE_ENERGY_COST, ATTACK_ENERGY_COST, BASE_REGEN,
    BASE_CAPACITY, ITEM_WEIGHTS, SMELTING_RECIPES, SMELTING_RATIO,
    CRAFTING_RECIPES, PART_DEFINITIONS, CORE_RECIPES,
    UPGRADE_MAX_LEVEL, UPGRADE_BASE_INGOT_COST,
    RESPAWN_HP_PERCENT, TOWN_COORDINATES, CLUTTER_THRESHOLD, CLUTTER_PENALTY,
    REPAIR_COST_PER_HP, REPAIR_COST_IRON_INGOT_PER_HP,
    CORE_SERVICE_COST_CREDITS, CORE_SERVICE_COST_IRON_INGOT,
    FACTION_REALIGNMENT_COST, FACTION_REALIGNMENT_COOLDOWN,
    PHASE_PERCEPTION_DURATION, PHASE_STRATEGY_DURATION, PHASE_CRUNCH_DURATION
)
from game_helpers import (
    get_hex_distance, get_solar_intensity, is_in_anarchy_zone,
    get_agent_mass, recalculate_agent_stats, find_hex_path
)
from bot_logic import process_bot_brain, process_feral_brain

logger = logging.getLogger("heartbeat")

# Injected by main.py at startup
manager = None


def get_nearest_station(db, agent, station_type):
    relevant = [s for s in STATION_CACHE if s["station_type"] == station_type]
    if not relevant:
        return None
    best = min(relevant, key=lambda s: get_hex_distance(agent.q, agent.r, s["q"], s["r"]))
    class _S:
        q = best["q"]
        r = best["r"]
    return _S()


'''

lines = open("main.py", encoding="utf-8").readlines()

start_idx = None
end_idx = None
for i, l in enumerate(lines):
    if "async def heartbeat_loop():" in l and start_idx is None:
        start_idx = i
    if start_idx and "@app.on_event" in l and i > start_idx + 10:
        end_idx = i
        break

print(f"start={start_idx+1}, end={end_idx}")
body = "".join(lines[start_idx:end_idx])

with open("heartbeat.py", "w", encoding="utf-8") as f:
    f.write(HEADER)
    f.write(body)

print(f"heartbeat.py written: {len(open('heartbeat.py').readlines())} lines")
