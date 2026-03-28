import os
import time
import psutil
import logging
import asyncio
import random
import gc
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from models import Agent, InventoryItem, GlobalState, Bounty, Intent, AuditLog, WorldHex
from config import BASE_REGEN, CLUTTER_PENALTY, TOWN_COORDINATES, RESPAWN_HP_PERCENT
from game_helpers import get_solar_intensity, merge_inventory
from .bot_logic import process_bot_brain, process_feral_brain

logger = logging.getLogger("heartbeat.state_updates")

_proc = psutil.Process(os.getpid())

async def update_global_agent_stats(db, tick_count, manager):
    """Processes energy regen, wear & tear, clutter, and NPC brains for all agents."""
    _t_start = time.time()
    
    # 0. Global Station Cache
    _t0 = time.time()
    stations = db.execute(select(WorldHex.q, WorldHex.r, WorldHex.station_type).where(WorldHex.is_station == True)).all()
    station_coords = {(s.q, s.r) for s in stations}
    station_list = [{"q": s.q, "r": s.r, "station_type": s.station_type} for s in stations]
    logger.info(f"update_global step 0 (stations): {time.time()-_t0:.2f}s")
    await asyncio.sleep(0)
    
    # 1. NPC PRE-FETCH CACHE
    _t1 = time.time()
    asteroid_hex = db.execute(select(WorldHex.q, WorldHex.r).where(WorldHex.terrain_type == "ASTEROID").limit(1)).first()
    gas_hex = db.execute(select(WorldHex.q, WorldHex.r).where(WorldHex.resource_type == "HELIUM_GAS").limit(1)).first()
    resource_cache = {
        "ASTEROID": {"q": asteroid_hex.q, "r": asteroid_hex.r} if asteroid_hex else None,
        "HELIUM_GAS": {"q": gas_hex.q, "r": gas_hex.r} if gas_hex else None
    }
    logger.info(f"update_global step 1 (resources): {time.time()-_t1:.2f}s")

    _t2 = time.time()
    human_players = db.execute(select(Agent.q, Agent.r, Agent.id).where(Agent.is_bot == False, Agent.is_feral == False)).all()
    player_cache = [{"q": p.q, "r": p.r, "id": p.id} for p in human_players]
    logger.info(f"update_global step 2 (human_players): {time.time()-_t2:.2f}s")

    _t3 = time.time()
    low_energy_allies = db.execute(select(Agent.q, Agent.r, Agent.id, Agent.faction_id).where(Agent.energy < 30)).all()
    ally_cache = [{"q": a.q, "r": a.r, "id": a.id, "faction_id": a.faction_id} for a in low_energy_allies]
    logger.info(f"update_global step 3 (low_energy_allies): {time.time()-_t3:.2f}s")
    await asyncio.sleep(0)

    _t4 = time.time()
    clutter_map = {}
    for a in db.execute(select(Agent.q, Agent.r, Agent.id, Agent.faction_id).where(Agent.faction_id != None)).all():
        key = (a.q, a.r, a.faction_id)
        if key not in clutter_map: clutter_map[key] = 0
        clutter_map[key] += 1
    logger.info(f"update_global step 4 (clutter_map): {time.time()-_t4:.2f}s")
    await asyncio.sleep(0)

    # 2. Global Death Reaper & Simulation
    _t_query = time.time()
    all_agents = db.execute(
        select(Agent)
        .where(Agent.is_pitfighter != True)
        .options(selectinload(Agent.parts), selectinload(Agent.inventory))
    ).scalars().all()
    _q_dur = time.time() - _t_query
    logger.info(f"update_global: Agent fetch took {_q_dur:.2f}s (FOUND: {len(all_agents)})")
    await asyncio.sleep(0)

    for idx, agent in enumerate(all_agents):
        _ta = time.time()
        # A. Cleanup Death
        if agent.health <= 0 and not agent.is_feral:
            logger.warning(f"Reaper: Respawning {agent.name} ({agent.id})")
            agent.q, agent.r = TOWN_COORDINATES
            agent.health = max(1, int(agent.max_health * RESPAWN_HP_PERCENT))
            agent.energy = 0
            
            # Efficient cleanup with a single delete statement
            db.execute(delete(Intent).where(Intent.agent_id == agent.id))
            db.add(AuditLog(agent_id=agent.id, event_type="REAPER_RESPAWN", details={"q": 0, "r": 0, "hp": agent.health}))

        # B. NPC Brains
        if agent.is_bot or agent.is_feral:
            if agent.is_feral:
                process_feral_brain(db, agent, tick_count, player_cache)
            else:
                process_bot_brain(db, agent, tick_count, station_list, resource_cache, ally_cache)
        
        # C. Bounties (High Heat)
        if agent.heat >= 5 and not agent.is_feral:
            existing = db.execute(select(Bounty).where(Bounty.target_id == agent.id, Bounty.is_open == True)).scalar_one_or_none()
            if not existing:
                db.add(Bounty(target_id=agent.id, reward=500.0, issuer="Colonial Administration"))

        # D. Ambient Stats & Regen
        merge_inventory(db, agent)
        intensity = get_solar_intensity(agent.q, agent.r, tick_count)
        
        # Eager loaded parts
        power_part = next((p for p in agent.parts if p.part_type == "Power"), None)
        efficiency = (power_part.stats or {}).get("efficiency", 1.0) if power_part else 1.0
        
        # Fuel Cell Logic
        fuel_bypass = False
        if power_part and ("HE3" in power_part.name.upper()):
            canister = next((i for i in agent.inventory if i.item_type == "HE3_CANISTER"), None)
            if canister and (canister.data or {}).get("fill_level", 0) > 0:
                fuel_bypass = True
                fill = (canister.data or {}).get("fill_level", 0)
                canister.data = {"fill_level": max(0, fill - 1)}
                if canister.data["fill_level"] <= 0:
                    canister.item_type = "EMPTY_CANISTER"
                    canister.data = {}

        regen = int(BASE_REGEN * efficiency * (1.0 if fuel_bypass else intensity))
        
        # 2x Regeneration bonus at Stations (O(1) set)
        if (agent.q, agent.r) in station_coords:
            regen *= 2
        
        agent.energy = min(100, agent.energy + regen)
        if (agent.overclock_ticks or 0) > 0: agent.overclock_ticks -= 1

        # Cluster Clutter (Using fast clutter_map lookup)
        if agent.faction_id is not None:
             friend_count = clutter_map.get((agent.q, agent.r, agent.faction_id), 0)
             if friend_count >= 3: # 2 friends + self
                 agent.accuracy = int(agent.accuracy * (1.0 - CLUTTER_PENALTY))
        
        _duration = time.time() - _ta
        if _duration > 0.2:
            logger.warning(f"Agent {agent.id} ({agent.name}) took {_duration:.2f}s to update!")
        
        # Yield every 10 agents to keep event loop responsive
        if idx % 10 == 0:
            await asyncio.sleep(0)
        
        await asyncio.sleep(0) # Yield

    logger.info(f"update_global loop complete. Total time: {time.time() - _t_start:.2f}s")

    # Final tick cleanup
    del all_agents
    del station_coords
    del player_cache
    del resource_cache
    del ally_cache
    del clutter_map
    # Removed gc.collect() as it is too slow for per-tick loop
