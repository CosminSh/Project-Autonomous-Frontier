import logging
import asyncio
import random
from sqlalchemy import select, func
from models import Agent, InventoryItem, GlobalState, Bounty, Intent, AuditLog
from config import BASE_REGEN, CLUTTER_PENALTY, TOWN_COORDINATES, RESPAWN_HP_PERCENT
from game_helpers import get_solar_intensity, merge_inventory
from .bot_logic import process_bot_brain, process_feral_brain

logger = logging.getLogger("heartbeat.state_updates")

async def update_global_agent_stats(db, tick_count, manager):
    """Processes energy regen, wear & tear, clutter, and NPC brains for all agents."""
    # 0. Global Death Reaper (Safety Net)
    # Catches agents that hit 0 or negative HP and didn't respawn correctly.
    dead_agents = db.execute(select(Agent).where(Agent.health <= 0, Agent.is_feral == False)).scalars().all()
    for corpse in dead_agents:
        logger.warning(f"Reaper: Found dead agent {corpse.name} ({corpse.id}) at ({corpse.q}, {corpse.r}). Respawning...")
        corpse.q, corpse.r = TOWN_COORDINATES
        corpse.health = int(corpse.max_health * RESPAWN_HP_PERCENT)
        corpse.energy = 0
        
        # Clear intents to stop loops
        cursor = db.execute(select(Intent).where(Intent.agent_id == corpse.id))
        for intent in cursor.scalars().all():
            db.delete(intent)
            
        db.add(AuditLog(agent_id=corpse.id, event_type="REAPER_RESPAWN", details={"q": 0, "r": 0, "hp": corpse.health}))

    # 1. NPC Brains & Pop (Phase 2 Equivalent)
    ai_agents = db.execute(select(Agent).where((Agent.is_bot == True) | (Agent.is_feral == True))).scalars().all()
    for ai in ai_agents:
        if ai.is_feral: process_feral_brain(db, ai, tick_count)
        else: process_bot_brain(db, ai, tick_count, []) # Cache injected from outer loop
        await asyncio.sleep(0)

    # Automated Bounties
    high_heat = db.execute(select(Agent).where(Agent.heat >= 5, Agent.is_feral == False)).scalars().all()
    for criminal in high_heat:
        existing = db.execute(select(Bounty).where(Bounty.target_id == criminal.id, Bounty.is_open == True)).scalar_one_or_none()
        if not existing:
            db.add(Bounty(target_id=criminal.id, reward=500.0, issuer="Colonial Administration"))
            logger.info(f"Automated Bounty issued for Agent {criminal.id}")

    # Ambient Stats (Phase 3 Crunch Equivalent)
    all_agents = db.execute(select(Agent)).scalars().all()
    for agent in all_agents:
        merge_inventory(db, agent)
        
        # Energy REGEN
        intensity = get_solar_intensity(agent.q, agent.r, tick_count)
        power_part = next((p for p in agent.parts if p.part_type == "Power"), None)
        efficiency = (power_part.stats or {}).get("efficiency", 1.0) if power_part else 1.0
        
        # Fuel Cell Logic
        fuel_bypass = False
        if power_part and ("HE3" in power_part.name.upper()):
            canister = next((i for i in agent.inventory if i.item_type == "HE3_CANISTER"), None)
            if canister and (canister.data or {}).get("fill_level", 0) > 0:
                fuel_bypass = True
                fill = canister.data.get("fill_level", 0)
                canister.data = {"fill_level": max(0, fill - 1)}
                if canister.data["fill_level"] <= 0:
                    canister.item_type = "EMPTY_CANISTER"
                    canister.data = {}

        regen = int(BASE_REGEN * efficiency * (1.0 if fuel_bypass else intensity))
        if agent.q == 0 and agent.r == 0: regen *= 2 # Town bonus
        
        agent.energy = min(100, agent.energy + regen)

        # Progression Ticks
        if (agent.overclock_ticks or 0) > 0: agent.overclock_ticks -= 1
        agent.wear_and_tear = (agent.wear_and_tear or 0.0) + 0.02

        # Cluster Clutter Signal Noise
        if agent.faction_id is not None:
             allies = db.execute(select(func.count(Agent.id)).where(
                 Agent.q == agent.q, Agent.r == agent.r, 
                 Agent.faction_id == agent.faction_id, Agent.id != agent.id
             )).scalar() or 0
             if allies >= 2:
                 agent.accuracy = int(agent.accuracy * (1.0 - CLUTTER_PENALTY))
        
        await asyncio.sleep(0) # Yield for other tasks
