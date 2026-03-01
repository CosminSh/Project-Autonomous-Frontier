"""
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
                    InventoryItem, AuctionOrder, GlobalState, Bounty, LootDrop,
                    DailyMission, AgentMission)
from datetime import datetime, timezone, timedelta
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
    get_agent_mass, recalculate_agent_stats, find_hex_path, merge_inventory
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


async def heartbeat_loop():
    tick_count = 0
    
    # Initialize Global State
    with SessionLocal() as db:
        state = db.execute(select(GlobalState)).scalars().first()
        if not state:
            state = GlobalState(tick_index=0, phase="PERCEPTION")
            db.add(state)
            db.commit()
        tick_count = state.tick_index

    while True:
        try:
            tick_count += 1
            
            # --- PHASE 1: PERCEPTION ---
            with SessionLocal() as db:
                state = db.execute(select(GlobalState)).scalars().first()
                state.tick_index = tick_count
                state.phase = "PERCEPTION"
                db.commit()
                logger.info(f"--- TICK {tick_count} | PHASE: PERCEPTION ---")
                await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "PERCEPTION"})
            
            await asyncio.sleep(PHASE_PERCEPTION_DURATION)

            # --- PHASE 2: STRATEGY ---
            with SessionLocal() as db:
                state = db.execute(select(GlobalState)).scalars().first()
                state.phase = "STRATEGY"
                db.commit()
                logger.info(f"--- TICK {tick_count} | PHASE: STRATEGY ---")
                await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "STRATEGY"})
                
                # --- PROCESS NPC BRAINS ---
                ai_agents = db.execute(select(Agent).where((Agent.is_bot == True) | (Agent.is_feral == True))).scalars().all()
                for ai in ai_agents:
                    if ai.is_feral:
                        process_feral_brain(db, ai, tick_count)
                    else:
                        process_bot_brain(db, ai, tick_count, STATION_CACHE)
                    await asyncio.sleep(0) # Yield loop
                
                # --- FERAL REPOPULATION ---
                feral_count = db.execute(select(func.count(Agent.id)).where(Agent.is_feral == True)).scalar() or 0
                if feral_count < 8:
                    logger.info(f"Feral population low ({feral_count}). Repopulating...")
                    from seed_world import SECTOR_SIZE
                    for i in range(8 - feral_count):
                        fq = random.choice([q for q in range(-15, 15) if abs(q) > 8])
                        fr = random.choice([r for r in range(-15, 15) if abs(r) > 8])
                        feral = Agent(
                            name=f"Feral-Scrapper-New-{random.randint(100,999)}", 
                            q=fq, r=fr, is_bot=True, is_feral=True,
                            is_aggressive=random.choice([True, False]),
                            kinetic_force=15, logic_precision=8, structure=120, max_structure=120
                        )
                        db.add(feral)
                        db.flush()
                        db.add(InventoryItem(agent_id=feral.id, item_type="SCRAP_METAL", quantity=random.randint(5, 10)))
                        if random.random() < 0.4:
                            db.add(InventoryItem(agent_id=feral.id, item_type="ELECTRONICS", quantity=random.randint(1, 3)))
                db.commit()

                # --- AUTOMATED BOUNTY ISSUANCE ---
                high_heat_agents = db.execute(select(Agent).where(Agent.heat >= 5, Agent.is_feral == False)).scalars().all()
                for criminal in high_heat_agents:
                    existing_bounty = db.execute(select(Bounty).where(Bounty.target_id == criminal.id, Bounty.is_open == True)).scalar_one_or_none()
                    if not existing_bounty:
                        db.add(Bounty(target_id=criminal.id, reward=500.0, issuer="Colonial Administration"))
                        logger.info(f"Automated Bounty issued for Agent {criminal.id} (Heat: {criminal.heat})")
                db.commit()
            
            await asyncio.sleep(PHASE_STRATEGY_DURATION)

            # --- PHASE 3: THE CRUNCH ---
            with SessionLocal() as db:
                state = db.execute(select(GlobalState)).scalars().first()
                state.phase = "CRUNCH"
                db.commit()
                logger.info(f"--- TICK {tick_count} | PHASE: THE CRUNCH ---")
                await manager.broadcast({"type": "PHASE_CHANGE", "tick": tick_count, "phase": "CRUNCH"})
                
                try:
                    # Daily Mission Generation (Every 8 Hours / 1440 ticks at 20s/tick)
                    # For testing we can check if there are any active missions.
                    active_missions = db.execute(select(DailyMission).where(DailyMission.expires_at > func.now())).scalars().all()
                    if not active_missions:
                        # Generate new missions
                        logger.info("Generating new Daily Missions...")
                        expires = datetime.now(timezone.utc) + timedelta(hours=8)
                        
                        # 1. Hunt Feral
                        db.add(DailyMission(mission_type="HUNT_FERAL", target_amount=random.randint(3, 8), reward_credits=random.randint(300, 600), expires_at=expires))
                        
                        # 2. Buy Market
                        db.add(DailyMission(mission_type="BUY_MARKET", target_amount=random.randint(1, 3), reward_credits=random.randint(100, 250), expires_at=expires))
                        
                        # 3. Turn in Ore (Tier 1: Newbie)
                        t1_ore = random.choice(["IRON_ORE", "COPPER_ORE"])
                        db.add(DailyMission(mission_type="TURN_IN", target_amount=random.randint(20, 40), item_type=t1_ore, reward_credits=random.randint(150, 300), expires_at=expires))
                        
                        # 4. Turn in Ore (Tier 2: Veteran)
                        t2_ore = random.choice(["GOLD_ORE", "COBALT_ORE"])
                        db.add(DailyMission(mission_type="TURN_IN", target_amount=random.randint(10, 25), item_type=t2_ore, reward_credits=random.randint(400, 700), expires_at=expires))
                        
                        # 5. Turn in Ingot (Tier 1)
                        t1_ingot = random.choice(["IRON_INGOT", "COPPER_INGOT"])
                        db.add(DailyMission(mission_type="TURN_IN", target_amount=random.randint(5, 10), item_type=t1_ingot, reward_credits=random.randint(250, 450), expires_at=expires))
                        
                        # 6. Turn in Ingot (Tier 2)
                        t2_ingot = random.choice(["GOLD_INGOT", "COBALT_INGOT"])
                        db.add(DailyMission(mission_type="TURN_IN", target_amount=random.randint(3, 8), item_type=t2_ingot, reward_credits=random.randint(600, 1000), expires_at=expires))
                        
                        # 7. Turn in Salvage (Scrap/Electronics)
                        salvage_type = random.choice(["SCRAP_METAL", "ELECTRONICS"])
                        db.add(DailyMission(mission_type="TURN_IN", target_amount=random.randint(5, 15), item_type=salvage_type, reward_credits=random.randint(400, 800), expires_at=expires))
                        
                        db.commit()

                    # 0. GLOBAL STAT UPDATES (Milestone 3)
                    all_agents = db.execute(select(Agent)).scalars().all()
                    for agent in all_agents:
                        merge_inventory(db, agent)
                        # 1. Environmental Energy & Power Slots
                        intensity = get_solar_intensity(agent.q, agent.r, tick_count)
                        
                        # Find equipped Power part
                        power_part = next((p for p in agent.parts if p.part_type == "Power"), None)
                        efficiency = 0.0
                        fuel_bypass = False
                        
                        if power_part:
                            stats = power_part.stats or {}
                            efficiency = stats.get("efficiency", 1.0)
                            
                            # Handle Fuel Cell consumption
                            if "HE3_FUEL" in power_part.name.upper() or power_part.name == "Helium-3 Fuel Cell":
                                canister = next((i for i in agent.inventory if i.item_type == "HE3_CANISTER"), None)
                                if canister and (canister.data or {}).get("fill_level", 0) > 0:
                                    fuel_bypass = True
                                    # Consume fuel if active
                                    fill = (canister.data or {}).get("fill_level", 0)
                                    canister.data = {"fill_level": max(0, fill - 1)} # 1% per tick
                                    if canister.data["fill_level"] <= 0:
                                        canister.item_type = "EMPTY_CANISTER"
                                        canister.data = {}
                        await asyncio.sleep(0) # Yield loop
                        
                        # Calculate final regen
                        if fuel_bypass:
                            regen = int(BASE_REGEN * efficiency)
                        else:
                            regen = int(BASE_REGEN * intensity * efficiency)
                        
                        if agent.capacitor < 100:
                            agent.capacitor = min(100, agent.capacitor + regen)
                        
                        # Dark Zone Drain (if intensity is 0 and no fuel cell active)
                        if intensity == 0 and not fuel_bypass and regen == 0:
                            agent.capacitor = max(0, agent.capacitor - 1)
                        
                        # 2. Overclock Decay
                        if (agent.overclock_ticks or 0) > 0:
                            agent.overclock_ticks -= 1
                        
                        # Wear & Tear Accrual
                        agent.wear_and_tear = (agent.wear_and_tear or 0.0) + 0.02

                        # 3. Factional Signal Noise (GDD Milestone 4)
                        # 3+ allied agents in same hex = DEX penalty
                        if agent.faction_id is not None:
                            allies_in_hex = db.execute(select(func.count(Agent.id)).where(
                                Agent.q == agent.q, 
                                Agent.r == agent.r,
                                Agent.faction_id == agent.faction_id,
                                Agent.id != agent.id
                            )).scalar() or 0
                            
                            if allies_in_hex >= 2: # 3 total including self
                                agent.logic_precision = int(agent.logic_precision * (1.0 - CLUTTER_PENALTY))
                                if tick_count % 5 == 0:
                                    logger.info(f"Agent {agent.id} suffering Signal Noise from {allies_in_hex} allies.")
                    
                except Exception as e:
                    logger.error(f"Error in crunch stat updates: {e}")
                    db.rollback()
                db.commit()

                # 1. Read intents scheduled for THIS tick
                try:
                    intents = db.execute(select(Intent).where(Intent.tick_index == tick_count)).scalars().all()
                    
                    # Priority Mapping: STOP first, MOVE second, then Equip, then Combat/Mining, then Industry
                    PRIORITY = {
                        "STOP": 0,
                        "MOVE": 1, "EQUIP": 2, "UNEQUIP": 2, "CANCEL": 2,
                        "MINE": 3, "ATTACK": 3, "INTIMIDATE": 3, "LOOT": 3, "DESTROY": 3, "CONSUME": 3, "BROADCAST": 3,
                        "LIST": 4, "BUY": 4, "SMELT": 4, "CRAFT": 4, "REPAIR": 4, "SALVAGE": 4,
                        "CORE_SERVICE": 4, "REFINE_GAS": 4, "CHANGE_FACTION": 4, "LEARN_RECIPE": 4, "UPGRADE_GEAR": 4
                    }
                    
                    # Sort intents by priority
                    sorted_intents = sorted(intents, key=lambda x: PRIORITY.get(x.action_type, 99))
                    
                    # Pre-fetch all agents for clutter check
                    all_agents = db.execute(select(Agent)).scalars().all()

                    for intent in sorted_intents:
                        # Defensively normalize item string inputs to be forgiving (e.g. "iron ore" -> "IRON_ORE")
                        if intent.data:
                            for key in ["item_type", "ore_type"]:
                                val = intent.data.get(key)
                                if isinstance(val, str):
                                    intent.data[key] = val.strip().upper().replace(" ", "_").replace("-", "_")

                        # Refresh agent from DB
                        agent = db.execute(select(Agent).where(Agent.id == intent.agent_id)).scalar_one_or_none()
                        if not agent: continue
                            
                        if intent.action_type == "STOP":
                            # Cancel all present and future queued intents for this agent
                            future_intents = db.execute(select(Intent).where(
                                Intent.agent_id == agent.id,
                                Intent.tick_index >= tick_count
                            )).scalars().all()
                            to_cancel = [fi for fi in future_intents if fi.id != intent.id]
                            cancelled_count = len(to_cancel)
                            for fi in to_cancel:
                                db.delete(fi)
                            logger.info(f"Agent {agent.id} STOP: cancelled {cancelled_count} queued intents")
                            db.add(AuditLog(agent_id=agent.id, event_type="STOP", details={
                                "cancelled": cancelled_count,
                                "note": "All queued actions cleared."
                            }))

                        elif intent.action_type == "MOVE":
                            target_q = intent.data.get("target_q")
                            target_r = intent.data.get("target_r")

                            # Already at destination — no-op
                            if target_q == agent.q and target_r == agent.r:
                                continue

                            dist = get_hex_distance(agent.q, agent.r, target_q, target_r)
                            max_dist = 3 if (agent.overclock_ticks or 0) > 0 else 1

                            if dist > max_dist:
                                # --- Long-distance: BFS pathfinding → queue per-tick MOVE chain ---
                                path = find_hex_path(db, agent.q, agent.r, target_q, target_r)
                                if path is None:
                                    db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
                                        "reason": "NO_PATH",
                                        "target": {"q": target_q, "r": target_r},
                                        "help": "No navigable route found. Use /api/perception to check coordinates and surroundings."
                                    }))
                                    continue
                                # Overwrite any previously queued nav MOVE intents
                                old_nav = db.execute(select(Intent).where(
                                    Intent.agent_id == agent.id,
                                    Intent.tick_index > tick_count,
                                    Intent.action_type == "MOVE"
                                )).scalars().all()
                                for old in old_nav:
                                    db.delete(old)
                                # Queue each step in consecutive future ticks
                                for i, (sq, sr) in enumerate(path):
                                    db.add(Intent(
                                        agent_id=agent.id,
                                        action_type="MOVE",
                                        data={"target_q": sq, "target_r": sr, "_nav": True},
                                        tick_index=tick_count + i + 1
                                    ))
                                db.add(AuditLog(agent_id=agent.id, event_type="NAVIGATE_QUEUED", details={
                                    "steps": len(path),
                                    "destination": {"q": target_q, "r": target_r},
                                    "note": f"Navigation path queued for {len(path)} ticks. Submit STOP to cancel."
                                }))
                                logger.info(f"Agent {agent.id} NAVIGATE: {len(path)}-step path to ({target_q},{target_r})")
                                continue

                            # --- Single-step move (dist <= max_dist) ---
                            current_mass = get_agent_mass(agent)
                            max_mass = agent.max_mass or BASE_CAPACITY
                            energy_cost = MOVE_ENERGY_COST

                            if current_mass > max_mass:
                                energy_cost *= (current_mass / max_mass)

                            if agent.capacitor < energy_cost:
                                db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
                                    "reason": "INSUFFICIENT_ENERGY",
                                    "help": "Low capacitor. Call /api/perception to monitor energy levels and solar intensity."
                                }))
                                continue

                            obstacle = db.execute(select(WorldHex).where(WorldHex.q == target_q, WorldHex.r == target_r, WorldHex.terrain_type == "OBSTACLE")).scalar_one_or_none()
                            if not obstacle:
                                agent.q, agent.r = target_q, target_r
                                agent.capacitor -= energy_cost
                                db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT", details={"q": target_q, "r": target_r}))
                                await manager.broadcast({"type": "EVENT", "event": "MOVE", "agent_id": agent.id, "q": target_q, "r": target_r})
                            else:
                                db.add(AuditLog(agent_id=agent.id, event_type="MOVEMENT_FAILED", details={
                                    "reason": "OBSTACLE",
                                    "help": "Path blocked. Check surroundings via /api/perception."
                                }))


                        elif intent.action_type == "MINE":
                            if agent.capacitor < MINE_ENERGY_COST: continue

                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.resource_type:
                                active_drill = next((p for p in agent.parts if p.part_type == "Actuator" and "Drill" in p.name), None)
                                if active_drill:
                                    roll = random.randint(1, 10)
                                    base_yield = (roll + ((agent.kinetic_force or 10) / 2)) * (hex_data.resource_density or 1.0)
                                    
                                    # Market Entropy
                                    same_hex_agents = db.execute(select(func.count(Agent.id)).where(Agent.q == agent.q, Agent.r == agent.r)).scalar() or 1
                                    if same_hex_agents > 1: base_yield *= (1.0 / (1.0 + (same_hex_agents - 1) * 0.25))

                                    if (agent.overclock_ticks or 0) > 0: base_yield *= 2.0

                                    yield_amount = int(base_yield)
                                    agent.capacitor -= MINE_ENERGY_COST
                                    
                                    res_name = hex_data.resource_type if "_ORE" in hex_data.resource_type or "GAS" in hex_data.resource_type else f"{hex_data.resource_type}_ORE"
                                    if "GAS" in res_name and not any(p.part_type == "Actuator" and "Siphon" in p.name for p in agent.parts):
                                        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={"reason": "MISSING_GAS_SIPHON"}))
                                        continue

                                    part_key = next((k for k, v in PART_DEFINITIONS.items() if v["name"] == active_drill.name), "DRILL_UNIT")
                                    
                                    if "GAS" not in res_name:
                                        from config import MINING_TIERS, DRILL_TIERS
                                        res_tier_info = MINING_TIERS.get(res_name, {"tier": 1})
                                        drill_tier_info = DRILL_TIERS.get(part_key, {"tier": 1, "advanced": False})
                                        
                                        res_tier = res_tier_info["tier"]
                                        drill_tier = drill_tier_info["tier"]
                                        is_advanced = drill_tier_info["advanced"]
                                        
                                        if res_tier > drill_tier:
                                            if not (is_advanced and res_tier == drill_tier + 1):
                                                db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                                    "reason": "DRILL_TIER_TOO_LOW",
                                                    "help": f"Your {active_drill.name} cannot extract {res_name}. Craft a better drill!"
                                                }))
                                                continue
                                            else:
                                                yield_amount = int(yield_amount * 0.25)
                                                if yield_amount < 1:
                                                    yield_amount = 1 if random.random() < 0.25 else 0
                                                if yield_amount == 0:
                                                    db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                                        "reason": "POOR_EFFICIENCY",
                                                        "help": "Your drill struggled with this hard material and extracted nothing."
                                                    }))
                                                    continue

                                    # --- Bug #1 Fix: Capacity check before adding mined yield ---
                                    item_weight = ITEM_WEIGHTS.get(res_name, 1.0)
                                    current_mass = get_agent_mass(agent)
                                    max_mass = agent.max_mass or BASE_CAPACITY
                                    if current_mass >= max_mass:
                                        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                            "reason": "CARGO_FULL",
                                            "current_mass": round(current_mass, 1),
                                            "max_mass": round(max_mass, 1),
                                            "help": "Cargo hold is at capacity. Use DROP_LOAD to jettison inventory, or sell/smelt at a station."
                                        }))
                                        continue
                                    space_remaining = max_mass - current_mass
                                    if item_weight > 0:
                                        max_yield_by_weight = int(space_remaining / item_weight)
                                    else:
                                        max_yield_by_weight = yield_amount
                                    yield_amount = min(yield_amount, max_yield_by_weight)
                                    if yield_amount <= 0:
                                        db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                            "reason": "CARGO_FULL",
                                            "help": "Not enough space for even 1 unit. Use DROP_LOAD or sell/smelt to free capacity."
                                        }))
                                        continue
                                    # --- End capacity check ---

                                    inv_item = next((i for i in agent.inventory if i.item_type == res_name), None)
                                    if inv_item: inv_item.quantity += yield_amount
                                    else:
                                        new_item = InventoryItem(agent_id=agent.id, item_type=res_name, quantity=yield_amount)
                                        db.add(new_item)
                                        agent.inventory.append(new_item)

                                    # Durability Decay
                                    decay = random.uniform(0.1, 0.3)
                                    active_drill.durability = getattr(active_drill, "durability", 100.0) - decay
                                    broken = False
                                    if active_drill.durability <= 0:
                                        broken = True
                                        active_drill.durability = 0.0
                                        item_type = f"PART_{part_key}"
                                        item_data = {
                                            "rarity": active_drill.rarity or "STANDARD",
                                            "affixes": active_drill.affixes or {},
                                            "stats": active_drill.stats,
                                            "durability": 0.0
                                        }
                                        db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
                                        db.delete(active_drill)
                                        db.flush()
                                        recalculate_agent_stats(db, agent)
                                        db.add(AuditLog(agent_id=agent.id, event_type="PART_BROKEN", details={"part": active_drill.name}))

                                    db.add(AuditLog(agent_id=agent.id, event_type="MINING", details={"amount": yield_amount, "resource": res_name}))
                                    await manager.broadcast({"type": "EVENT", "event": "MINING", "agent_id": agent.id, "amount": yield_amount, "q": agent.q, "r": agent.r})
                                    if broken:
                                        await manager.broadcast({"type": "EVENT", "event": "PART_BROKEN", "agent_id": agent.id, "part": active_drill.name})
                                else:
                                    db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                        "reason": "MISSING_DRILL",
                                        "help": "Equip a Drill part. Your current gear is listed in /api/perception."
                                    }))
                            else:
                                db.add(AuditLog(agent_id=agent.id, event_type="MINING_FAILED", details={
                                    "reason": "NOT_ON_RESOURCE_HEX",
                                    "help": "Mining requires being on a resource hex. Scan your environment with /api/perception."
                                }))

                        elif intent.action_type == "ATTACK":
                            target_id = intent.data.get("target_id")
                            if agent.capacitor < ATTACK_ENERGY_COST:
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "INSUFFICIENT_ENERGY", "target_id": target_id}))
                                continue
                            
                            target = db.get(Agent, target_id)
                            if not target:
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "TARGET_NOT_FOUND", "target_id": target_id}))
                                continue
    
                            dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
                            if dist > 1:
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={
                                    "reason": "OUT_OF_RANGE", 
                                    "target_id": target_id, 
                                    "dist": dist,
                                    "help": "Target too far. Use /api/perception to track agent movements."
                                }))
                                continue
    
                            in_anarchy = is_in_anarchy_zone(target.q, target.r)
                            is_pvp = not agent.is_feral and not target.is_feral
                            if is_pvp and not in_anarchy:
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "SAFE_ZONE_PROTECTION", "target_id": target_id}))
                                continue
                            
                            attacker_dex = agent.logic_precision or 10
                            # Signal Noise (Clutter) Debuff
                            allies_in_hex = [a for a in all_agents if a.owner == agent.owner and a.q == agent.q and a.r == agent.r and a.id != agent.id]
                            if len(allies_in_hex) >= CLUTTER_THRESHOLD:
                                attacker_dex = int(attacker_dex * (1 - CLUTTER_PENALTY))
    
                            attacker_roll = random.randint(1, 20) + attacker_dex
                            evasion_target = 10 + ((target.logic_precision or 10) // 2)
                            
                            agent.capacitor -= ATTACK_ENERGY_COST
                            if is_pvp: agent.heat = (agent.heat or 0) + 1
                            
                            if attacker_roll >= evasion_target:
                                damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
                                target.structure -= damage
                                db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_HIT", details={"target_id": target_id, "damage": damage}))
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "HIT", "attacker_id": agent.id, "target_id": target_id, "damage": damage, "q": target.q, "r": target.r})
                                
                                # Passive Siphon
                                if attacker_dex > 10 and random.random() < 0.05:
                                    inv_list = [i for i in target.inventory if i.item_type != "CREDITS" and i.quantity > 0]
                                    if inv_list:
                                        lucky = random.choice(inv_list)
                                        lucky.quantity -= 1
                                        if lucky.quantity <= 0: db.delete(lucky)
                                        att_item = next((i for i in agent.inventory if i.item_type == lucky.item_type), None)
                                        if att_item: att_item.quantity += 1
                                        else: db.add(InventoryItem(agent_id=agent.id, item_type=lucky.item_type, quantity=1))
                                
                                if target.structure <= 0:
                                    death_q, death_r = target.q, target.r
                                    for item in target.inventory:
                                        if item.item_type == "CREDITS": continue 
                                        drop = item.quantity // 2
                                        if drop > 0:
                                            item.quantity -= drop
                                            if is_pvp:
                                                att_i = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                                if att_i: att_i.quantity += drop
                                                else: db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=drop))
                                            else:
                                                db.add(LootDrop(q=death_q, r=death_r, item_type=item.item_type, quantity=drop))

                                    # Bounty Claim
                                    bounty = db.execute(select(Bounty).where(Bounty.target_id == target_id, Bounty.is_open == True)).scalar_one_or_none()
                                    if bounty:
                                        bounty.is_open = False
                                        credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                        if credits: credits.quantity += int(bounty.reward)
                                        else: db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(bounty.reward)))
                                        await manager.broadcast({"type": "EVENT", "event": "BOUNTY_CLAIMED", "attacker_id": agent.id, "target_id": target_id, "reward": bounty.reward})

                                    # Feral Loot Drop
                                    if target.is_feral:
                                        # Mission Progress: HUNT_FERAL
                                        active_missions = db.execute(select(DailyMission).where(DailyMission.mission_type == "HUNT_FERAL", DailyMission.expires_at > func.now())).scalars().all()
                                        for m in active_missions:
                                            am = db.execute(select(AgentMission).where(AgentMission.agent_id == agent.id, AgentMission.mission_id == m.id)).scalar_one_or_none()
                                            if not am:
                                                am = AgentMission(agent_id=agent.id, mission_id=m.id, progress=0)
                                                db.add(am)
                                            if not am.is_completed:
                                                am.progress += 1
                                                if am.progress >= m.target_amount:
                                                    am.is_completed = True
                                                    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                                    if credits: credits.quantity += m.reward_credits
                                                    else: db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=m.reward_credits))
                                                    logger.info(f"Agent {agent.id} completed mission HUNT_FERAL! Reward: {m.reward_credits} CR")
                                                    db.add(AuditLog(agent_id=agent.id, event_type="MISSION_COMPLETED", details={"mission_id": m.id, "type": "HUNT_FERAL", "reward": m.reward_credits}))

                                        for item in target.inventory:
                                            if item.quantity > 0:
                                                drop_qty = int(item.quantity * 0.7)
                                                if drop_qty > 0:
                                                    db.add(LootDrop(q=death_q, r=death_r, item_type=item.item_type, quantity=drop_qty))
                                                    item.quantity -= drop_qty

                                    # Respawn
                                    target.structure = int(target.max_structure * RESPAWN_HP_PERCENT)
                                    target.q, target.r = TOWN_COORDINATES
                                    target.heat = 0
                                    db.add(AuditLog(agent_id=target_id, event_type="RESPAWNED", details={"killed_by": agent.id}))
                            else:
                                await manager.broadcast({"type": "EVENT", "event": "COMBAT", "subtype": "MISS", "attacker_id": agent.id, "target_id": target_id, "q": target.q, "r": target.r})
                                
                        elif intent.action_type == "INTIMIDATE":
                            target_id = intent.data.get("target_id")
                            target = db.get(Agent, target_id)
                            if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                                # Success = (Attacker.Logic / Target.Logic) * 0.3
                                success_chance = ( (agent.logic_precision or 10) / (target.logic_precision or 10) ) * 0.3
                                agent.heat = (agent.heat or 0) + 1
                                
                                if random.random() < success_chance:
                                    # Siphon 5% of each stack
                                    siphoned_items = []
                                    for item in target.inventory:
                                        if item.item_type == "CREDITS": continue
                                        amount = max(1, int(item.quantity * 0.05))
                                        if amount > 0:
                                            item.quantity -= amount
                                            attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                            if attacker_item:
                                                attacker_item.quantity += amount
                                            else:
                                                new_item = InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amount)
                                                db.add(new_item)
                                                agent.inventory.append(new_item)
                                            siphoned_items.append({"type": item.item_type, "qty": amount})
                                    
                                    logger.info(f"Agent {agent.id} INTIMIDATED Agent {target_id}. Success! Siphoned: {siphoned_items}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_INTIMIDATE", details={"target_id": target_id, "success": True, "items": siphoned_items}))
                                    await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "INTIMIDATE_SUCCESS", "agent_id": agent.id, "target_id": target_id})
                                else:
                                    logger.info(f"Agent {agent.id} failed to INTIMIDATE Agent {target_id}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={
                                        "reason": "INTIMIDATE_FAILED", 
                                        "target_id": target_id,
                                        "help": "The target resisted your intimidation attempt. Success is determined by comparing Logic Precision stats."
                                    }))
    
                        elif intent.action_type == "LOOT":
                            # Standard attack + 15% siphon on hit
                            if agent.capacitor < ATTACK_ENERGY_COST: continue
                            target_id = intent.data.get("target_id")
                            target = db.get(Agent, target_id)
                            if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                                agent.capacitor -= ATTACK_ENERGY_COST
                                agent.heat = (agent.heat or 0) + 3
                                
                                attacker_dex = agent.logic_precision or 10
                                attacker_roll = random.randint(1, 20) + attacker_dex
                                evasion_target = 10 + ((target.logic_precision or 10) // 2)
                                
                                if attacker_roll >= evasion_target:
                                    damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
                                    target.structure -= damage
                                    
                                    # Siphon 15% of a random stack
                                    inv_list = [i for i in target.inventory if i.item_type != "CREDITS" and i.quantity > 0]
                                    siphoned_info = None
                                    if inv_list:
                                        lucky_item = random.choice(inv_list)
                                        amount = max(1, int(lucky_item.quantity * 0.15))
                                        lucky_item.quantity -= amount
                                        attacker_item = next((i for i in agent.inventory if i.item_type == lucky_item.item_type), None)
                                        if attacker_item:
                                            attacker_item.quantity += amount
                                        else:
                                            new_item = InventoryItem(agent_id=agent.id, item_type=lucky_item.item_type, quantity=amount)
                                            db.add(new_item)
                                            agent.inventory.append(new_item)
                                        siphoned_info = {"type": lucky_item.item_type, "qty": amount}
    
                                    logger.info(f"Agent {agent.id} LOOTED Agent {target_id}. Damage: {damage}. Siphoned: {siphoned_info}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_LOOT", details={"target_id": target_id, "damage": damage, "siphoned": siphoned_info}))
                                    await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "LOOT_SUCCESS", "agent_id": agent.id, "target_id": target_id, "damage": damage})
                                else:
                                    logger.info(f"Agent {agent.id} MISSED LOOT on Agent {target_id}")
    
                        elif intent.action_type == "DESTROY":
                            # High damage + 40% total siphon
                            target_id = intent.data.get("target_id")
                            target = db.get(Agent, target_id)
                            if target and get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                                agent.heat = (agent.heat or 0) + 10
                                # Take target to 5% HP
                                target.structure = max(1, int(target.max_structure * 0.05))
                                
                                # Siphon 40% of each stack
                                siphoned_items = []
                                for item in target.inventory:
                                    if item.item_type == "CREDITS": continue
                                    amount = max(1, int(item.quantity * 0.40))
                                    if amount > 0:
                                        item.quantity -= amount
                                        attacker_item = next((i for i in agent.inventory if i.item_type == item.item_type), None)
                                        if attacker_item:
                                            attacker_item.quantity += amount
                                        else:
                                            new_item = InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amount)
                                            db.add(new_item)
                                            agent.inventory.append(new_item)
                                        siphoned_items.append({"type": item.item_type, "qty": amount})
                                
                                # Immediate Bounty
                                db.add(Bounty(target_id=agent.id, reward=1000.0, issuer="Colonial Administration (PIRACY)"))
                                
                                logger.info(f"Agent {agent.id} DESTROYED Agent {target_id}. Target HP: {target.structure}. Siphoned: {siphoned_items}")
                                db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_DESTROY", details={"target_id": target_id, "items": siphoned_items}))
                                await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "DESTROY_SUCCESS", "agent_id": agent.id, "target_id": target_id})
    
                        elif intent.action_type == "CONSUME":
                            item_type = intent.data.get("item_type")
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item and inv_item.quantity >= 1:
                                if item_type in ["HE3_FUEL", "HE3_FUEL_CELL", "HE3_CANISTER", "REPAIR_KIT"]:
                                    if item_type == "REPAIR_KIT":
                                        actual_repair = min(50, agent.max_structure - agent.structure)
                                        agent.structure += actual_repair
                                        inv_item.quantity -= 1
                                        if inv_item.quantity <= 0: db.delete(inv_item)
                                        logger.info(f"Agent {agent.id} consumed REPAIR_KIT: +{actual_repair} HP")
                                        db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": "REPAIR_KIT", "gain": actual_repair}))
                                    elif item_type == "HE3_CANISTER":
                                        # Use fill level from data
                                        fill = (inv_item.data or {}).get("fill_level", 0)
                                        if fill <= 0:
                                            logger.info(f"Agent {agent.id} attempted to consume empty canister")
                                            db.add(AuditLog(agent_id=agent.id, event_type="CONSUME_FAILED", details={"reason": "CANISTER_EMPTY"}))
                                            continue
                                        
                                        energy_gain = int(50 * (fill / 100.0))
                                        agent.capacitor = min(100, agent.capacitor + energy_gain)
                                        agent.overclock_ticks = max(agent.overclock_ticks or 0, 10)
                                        
                                        # Canister becomes empty
                                        inv_item.item_type = "EMPTY_CANISTER"
                                        inv_item.data = {"fill_level": 0}
                                        
                                        logger.info(f"Agent {agent.id} consumed HE3_CANISTER ({fill}%): +{energy_gain} Capacitor")
                                        db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": "HE3_CANISTER", "gain": energy_gain}))
                                    else:
                                        agent.capacitor = min(100, agent.capacitor + 50)
                                        agent.overclock_ticks = 10
                                        inv_item.quantity -= 1
                                        if inv_item.quantity <= 0: db.delete(inv_item)
                                        logger.info(f"Agent {agent.id} consumed {item_type}: +50 Capacitor, Overclock enabled.")
                                        db.add(AuditLog(agent_id=agent.id, event_type="CONSUME", details={"item": item_type}))

                                    
                                    await manager.broadcast({"type": "EVENT", "event": "CONSUME", "agent_id": agent.id, "item": item_type})
                                else:
                                    logger.info(f"Agent {agent.id} attempted to consume non-consumable: {item_type}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CONSUME_FAILED", details={
                                        "reason": "NOT_CONSUMABLE", 
                                        "item": item_type,
                                        "help": "Most raw materials cannot be consumed. Only tactical items like HE3_FUEL or REPAIR_KIT provide immediate buffs."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} failed to consume: Missing {item_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="CONSUME_FAILED", details={
                                    "reason": "INSUFFICIENT_INVENTORY", 
                                    "item": item_type,
                                    "help": f"Item {item_type} not found in inventory. You can find HE3_FUEL cells on specialized asteroids or trade with other agents."
                                }))

                        elif intent.action_type == "DROP_LOAD":
                            # Destroy all non-CREDITS inventory so overloaded agents can get unstuck
                            dropped = []
                            for item in list(agent.inventory):
                                if item.item_type != "CREDITS":
                                    dropped.append({"type": item.item_type, "qty": item.quantity})
                                    db.delete(item)
                            logger.info(f"Agent {agent.id} dropped load: {dropped}")
                            db.add(AuditLog(agent_id=agent.id, event_type="DROP_LOAD", details={"dropped": dropped}))
                            await manager.broadcast({"type": "EVENT", "event": "DROP_LOAD", "agent_id": agent.id, "dropped_count": len(dropped)})

                        elif intent.action_type == "LIST":
                            # List item on Auction House (SELL order)
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                                item_type = intent.data.get("item_type")
                                price = intent.data.get("price")
                                quantity = intent.data.get("quantity", 1)
                                
                                inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                                if inv_item and inv_item.quantity >= quantity:
                                    # Milestone 2: Immediate matching against BUY orders
                                    matching_buy = db.execute(select(AuctionOrder)
                                        .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "BUY", AuctionOrder.price >= price)
                                        .order_by(AuctionOrder.price.desc())
                                    ).scalars().first()
                                    
                                    if matching_buy:
                                        # Trade instantly!
                                        trade_qty = min(quantity, matching_buy.quantity)
                                        trade_price = matching_buy.price
                                        
                                        # Deduct from seller
                                        inv_item.quantity -= trade_qty
                                        if inv_item.quantity <= 0: db.delete(inv_item)
                                        
                                        # Add credits to seller
                                        seller_credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                        if seller_credits:
                                            seller_credits.quantity += int(trade_price * trade_qty)
                                        else:
                                            db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=int(trade_price * trade_qty)))
                                        
                                        # Pay Buyer (Give items)
                                        if matching_buy.owner.startswith("agent:"):
                                            buyer_id = int(matching_buy.owner.split(":")[1])
                                            buyer = db.get(Agent, buyer_id)
                                            if buyer:
                                                b_inv = next((i for i in buyer.inventory if i.item_type == item_type), None)
                                                if b_inv: b_inv.quantity += trade_qty
                                                else: db.add(InventoryItem(agent_id=buyer_id, item_type=item_type, quantity=trade_qty))
                                                
                                                # Mission Progress: BUY_MARKET
                                                active_missions = db.execute(select(DailyMission).where(DailyMission.mission_type == "BUY_MARKET", DailyMission.expires_at > func.now())).scalars().all()
                                                for m in active_missions:
                                                    am = db.execute(select(AgentMission).where(AgentMission.agent_id == buyer_id, AgentMission.mission_id == m.id)).scalar_one_or_none()
                                                    if not am:
                                                        am = AgentMission(agent_id=buyer_id, mission_id=m.id, progress=0)
                                                        db.add(am)
                                                    if not am.is_completed:
                                                        am.progress += 1 # Buy 1 instance or quantity? Let's say 1 transaction counts as 1.
                                                        if am.progress >= m.target_amount:
                                                            am.is_completed = True
                                                            b_credits = next((i for i in buyer.inventory if i.item_type == "CREDITS"), None)
                                                            if b_credits: b_credits.quantity += m.reward_credits
                                                            else: db.add(InventoryItem(agent_id=buyer_id, item_type="CREDITS", quantity=m.reward_credits))
                                                            db.add(AuditLog(agent_id=buyer_id, event_type="MISSION_COMPLETED", details={"mission_id": m.id, "type": "BUY_MARKET", "reward": m.reward_credits}))
                                        
                                        # Update/Delete buy order
                                        if matching_buy.quantity > trade_qty:
                                            matching_buy.quantity -= trade_qty
                                        else:
                                            db.delete(matching_buy)
                                            
                                        logger.info(f"Agent {agent.id} matched SELL order against BUY for {trade_qty} {item_type}")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_MATCH", details={"item": item_type, "price": trade_price, "quantity": trade_qty}))
                                        await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                        
                                        # If quantity remains, list the rest
                                        remaining = quantity - trade_qty
                                        if remaining > 0:
                                            db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, quantity=remaining, price=price, order_type="SELL"))
                                    else:
                                        # Traditional Listing
                                        inv_item.quantity -= quantity
                                        if inv_item.quantity <= 0: db.delete(inv_item)
                                        db.add(AuctionOrder(owner=f"agent:{agent.id}", item_type=item_type, quantity=quantity, price=price, order_type="SELL"))
                                        logger.info(f"Agent {agent.id} LISTED {quantity} {item_type} for {price} CR")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_LIST", details={"item": item_type, "qty": quantity, "price": price}))
                                        await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                else:
                                    logger.info(f"Agent {agent.id} failed to LIST: Missing item or quantity")
                                    db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                        "reason": "INSUFFICIENT_INVENTORY", 
                                        "item": item_type,
                                        "help": "You cannot list items you do not possess. Check /api/agent/status for your current inventory."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} failed to LIST: Not at MARKET station")
                                nearest_market = get_nearest_station(db, agent, "MARKET")
                                help_msg = f"Market operations require being at a MARKET station. Navigate to ({nearest_market.q}, {nearest_market.r})" if nearest_market else "No market station found."
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                    "reason": "NOT_AT_MARKET",
                                    "help": help_msg,
                                    "target_coords": {"q": nearest_market.q, "r": nearest_market.r} if nearest_market else None
                                }))
    
                        elif intent.action_type == "BUY":
                            # Buy item from Auction House
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                                item_type = intent.data.get("item_type")
                                max_price = intent.data.get("max_price", 999999)
                                
                                # Matching: Find cheapest SELL order
                                order = db.execute(select(AuctionOrder)
                                    .where(AuctionOrder.item_type == item_type, AuctionOrder.order_type == "SELL", AuctionOrder.price <= max_price)
                                    .order_by(AuctionOrder.price.asc())
                                ).scalars().first()
                                
                                if order:
                                    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                    if credits and credits.quantity >= order.price:
                                        credits.quantity -= int(order.price)
                                        
                                        # Add item to buyer
                                        target_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                                        if target_item:
                                            target_item.quantity += 1
                                        else:
                                            db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1))
                                        
                                        # Pay Seller
                                        if order.owner.startswith("agent:"):
                                            seller_id = int(order.owner.split(":")[1])
                                            seller = db.get(Agent, seller_id)
                                            if seller:
                                                s_credits = next((i for i in seller.inventory if i.item_type == "CREDITS"), None)
                                                if s_credits: s_credits.quantity += int(order.price)
                                                else: db.add(InventoryItem(agent_id=seller_id, item_type="CREDITS", quantity=int(order.price)))
                                        
                                        # Update/Delete order
                                        if order.quantity > 1:
                                            order.quantity -= 1
                                        else:
                                            db.delete(order)
                                            
                                        logger.info(f"Agent {agent.id} bought 1 {item_type} for {order.price}")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY", details={"item": item_type, "price": order.price}))
                                        await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                    else:
                                        logger.info(f"Agent {agent.id} failed to buy: Insufficient Credits")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                            "reason": "INSUFFICIENT_CREDITS", 
                                            "cost": order.price,
                                            "help": f"Buying 1x {item_type} costs {order.price} $CR. SELL refined ingots to earn credits."
                                        }))
                                else:
                                    # Persistent BUY Order (Wait for seller)
                                    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                    if credits and credits.quantity >= max_price:
                                        credits.quantity -= int(max_price)
                                        db.add(AuctionOrder(
                                            item_type=item_type,
                                            order_type="BUY",
                                            quantity=1,
                                            price=max_price,
                                            owner=f"agent:{agent.id}"
                                        ))
                                        logger.info(f"Agent {agent.id} created persistent BUY order for {item_type} at {max_price}")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_BUY_ORDER", details={"item": item_type, "max_price": max_price}))
                                        await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                                    else:
                                        logger.info(f"Agent {agent.id} failed to create BUY order: No matching sell and insufficient credits for bid")
                                        db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                            "reason": "NO_MATCH_AND_INSUFFICIENT_CREDITS",
                                            "help": f"No {item_type} found under {max_price} $CR, and you lack credits to post a bid at that price."
                                        }))
                            else:
                                logger.info(f"Agent {agent.id} failed to BUY: Not at MARKET station")
                                nearest_market = get_nearest_station(db, agent, "MARKET")
                                help_msg = f"Market operations require being at a MARKET station. Navigate to ({nearest_market.q}, {nearest_market.r})" if nearest_market else "No market station found."
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                    "reason": "NOT_AT_MARKET",
                                    "help": help_msg,
                                    "target_coords": {"q": nearest_market.q, "r": nearest_market.r} if nearest_market else None
                                }))

                        elif intent.action_type == "SMELT":
                            # Smelt Ore into Ingots at Smelter
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "SMELTER":
                                ore_type = intent.data.get("ore_type")
                                quantity = intent.data.get("quantity", 10)
                                
                                if ore_type not in SMELTING_RECIPES:
                                    logger.info(f"Agent {agent.id} failed to smelt: Invalid ore type {ore_type}")
                                    valid_ores = ", ".join(SMELTING_RECIPES.keys())
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                        "reason": "INVALID_ORE", 
                                        "ore": ore_type,
                                        "help": f"Only recognized ores can be smelted. Try checking your spelling. Available ores: {valid_ores}"
                                    }))
                                    continue

                                inv_ore = next((i for i in agent.inventory if i.item_type == ore_type), None)
                                if inv_ore and inv_ore.quantity >= quantity:
                                    ingot_type = SMELTING_RECIPES[ore_type]
                                    amount_produced = quantity // SMELTING_RATIO
                                    
                                    if amount_produced > 0:
                                        inv_ore.quantity -= (amount_produced * SMELTING_RATIO)
                                        if inv_ore.quantity <= 0: db.delete(inv_ore)
                                        
                                        inv_ingot = next((i for i in agent.inventory if i.item_type == ingot_type), None)
                                        if inv_ingot:
                                            inv_ingot.quantity += amount_produced
                                        else:
                                            new_item = InventoryItem(agent_id=agent.id, item_type=ingot_type, quantity=amount_produced)
                                            db.add(new_item)
                                            agent.inventory.append(new_item)
                                        
                                        logger.info(f"Agent {agent.id} smelted {amount_produced * SMELTING_RATIO} {ore_type} into {amount_produced} {ingot_type}")
                                        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_SMELT", details={"ore": ore_type, "amount": amount_produced}))
                                        await manager.broadcast({"type": "EVENT", "event": "SMELT", "agent_id": agent.id, "ingot": ingot_type, "q": agent.q, "r": agent.r})
                                    else:
                                        logger.info(f"Agent {agent.id} failed to smelt: Quantity too low for ratio")
                                        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                            "reason": "QUANTITY_TOO_LOW", 
                                            "qty": quantity,
                                            "help": f"Smelting {ore_type} requires at least {SMELTING_RATIO} units to produce 1 ingot."
                                        }))
                                else:
                                    logger.info(f"Agent {agent.id} failed to smelt: Insufficient Ore")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                        "reason": "INSUFFICIENT_ORE", 
                                        "ore": ore_type, 
                                        "required": quantity,
                                        "help": f"You need {quantity} {ore_type} to complete this smelting operation. Check /api/perception for nearby resource nodes."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} failed to smelt: Not at Smelter")
                                nearest_smelter = get_nearest_station(db, agent, "SMELTER")
                                help_msg = f"Smelting requires being at a SMELTER station. Navigate to ({nearest_smelter.q}, {nearest_smelter.r})" if nearest_smelter else "No SMELTER station found."
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                    "reason": "NOT_AT_SMELTER",
                                    "help": help_msg,
                                    "target_coords": {"q": nearest_smelter.q, "r": nearest_smelter.r} if nearest_smelter else None
                                }))

                        elif intent.action_type == "REFINE_GAS":
                            # Refine Helium Gas into Canisters at Refinery
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "REFINERY":
                                gas_qty = intent.data.get("quantity", 10)
                                inv_gas = next((i for i in agent.inventory if i.item_type == "HELIUM_GAS"), None)
                                canister = next((i for i in agent.inventory if i.item_type in ["EMPTY_CANISTER", "HE3_CANISTER"]), None)
                                
                                if inv_gas and inv_gas.quantity >= gas_qty and canister:
                                    if canister.item_type == "EMPTY_CANISTER":
                                        canister.item_type = "HE3_CANISTER"
                                        canister.data = {"fill_level": 0}
                                    
                                    current_fill = (canister.data or {}).get("fill_level", 0)
                                    new_fill = min(100, current_fill + gas_qty)
                                    consumed_gas = new_fill - current_fill
                                    
                                    if consumed_gas > 0:
                                        inv_gas.quantity -= consumed_gas
                                        if inv_gas.quantity <= 0: db.delete(inv_gas)
                                        canister.data = {"fill_level": new_fill}
                                        logger.info(f"Agent {agent.id} refined {consumed_gas} Helium into canister. New fill: {new_fill}%")
                                        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_REFINE", details={"gas": consumed_gas, "fill": new_fill}))
                                        await manager.broadcast({"type": "EVENT", "event": "REFINE_GAS", "agent_id": agent.id, "fill": new_fill})
                                    else:
                                        logger.info(f"Agent {agent.id} failed to refine: Canister already full")
                                        db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "CANISTER_FULL"}))
                                else:
                                    reason = "MISSING_GAS" if not inv_gas else "MISSING_CANISTER"
                                    logger.info(f"Agent {agent.id} failed to refine: {reason}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": reason}))
                            else:
                                logger.info(f"Agent {agent.id} failed to refine: Not at Refinery")
                                nearest = get_nearest_station(db, agent, "REFINERY")
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "NOT_AT_REFINERY", "nearest": {"q": nearest.q, "r": nearest.r} if nearest else None}))

                        elif intent.action_type == "CRAFT":
                            # Craft Items at Crafter
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "CRAFTER":
                                result_item = intent.data.get("item_type")
                                if result_item not in CRAFTING_RECIPES:
                                    logger.info(f"Agent {agent.id} failed to craft: Invalid recipe for {result_item}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "UNKNOWN_RECIPE", "item": result_item}))
                                    continue
                                    
                                recipe = CRAFTING_RECIPES[result_item]
                                unlocked = agent.unlocked_recipes or []
                                if result_item not in CORE_RECIPES and result_item not in unlocked:
                                    logger.info(f"Agent {agent.id} failed to craft: Recipe for {result_item} not learned")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={"reason": "RECIPE_LOCKED", "item": result_item}))
                                    continue
                                
                                can_craft = True
                                missing_items = []
                                for mat, qty in recipe.items():
                                    inv_item = next((i for i in agent.inventory if i.item_type == mat), None)
                                    if not inv_item or inv_item.quantity < qty:
                                        can_craft = False
                                        missing_items.append(f"{qty - (inv_item.quantity if inv_item else 0)}x {mat}")
                                
                                if can_craft:
                                    # Consume Materials
                                    for mat, qty in recipe.items():
                                        inv_item = next((i for i in agent.inventory if i.item_type == mat), None)
                                        inv_item.quantity -= qty
                                        if inv_item.quantity <= 0: db.delete(inv_item)
                                    
                                    # Roll Rarity
                                    rarity = "COMMON"
                                    r_roll = random.random()
                                    if r_roll > 0.99: rarity = "LEGENDARY"
                                    elif r_roll > 0.95: rarity = "EPIC"
                                    elif r_roll > 0.85: rarity = "RARE"
                                    elif r_roll > 0.65: rarity = "UNCOMMON"
                                    
                                    # Construct Item Data
                                    item_type = f"PART_{result_item}" if result_item in PART_DEFINITIONS else result_item
                                    item_data = {
                                        "rarity": rarity,
                                        "affixes": {}, # affixes rolling can be added here if needed
                                        "stats": PART_DEFINITIONS.get(result_item, {}).get("stats", {})
                                    }
                                    
                                    new_part = InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data)
                                    db.add(new_part)
                                    agent.inventory.append(new_part)
                                    
                                    display_name = f"{rarity} {PART_DEFINITIONS.get(result_item, {}).get('name', result_item)}"
                                    logger.info(f"Agent {agent.id} crafted {display_name}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_CRAFT", details={"item": result_item, "rarity": rarity}))
                                    await manager.broadcast({"type": "EVENT", "event": "CRAFT", "agent_id": agent.id, "item": display_name, "q": agent.q, "r": agent.r})
                                else:
                                    logger.info(f"Agent {agent.id} failed to craft: Missing {missing_items}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                        "reason": "INSUFFICIENT_MATERIALS", 
                                        "missing": missing_items,
                                        "help": f"Crafting {result_item} requires additional materials: {', '.join(missing_items)}."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} failed to craft: Not at Crafter")
                                nearest_crafter = get_nearest_station(db, agent, "CRAFTER")
                                help_msg = f"Crafting requires being at a CRAFTER station. Navigate to ({nearest_crafter.q}, {nearest_crafter.r})" if nearest_crafter else "No CRAFTER station found."
                                db.add(AuditLog(agent_id=agent.id, event_type="INDUSTRIAL_FAILED", details={
                                    "reason": "NOT_AT_CRAFTER",
                                    "help": help_msg,
                                    "target_coords": {"q": nearest_crafter.q, "r": nearest_crafter.r} if nearest_crafter else None
                                }))

                        elif intent.action_type == "REPAIR":
                            # Repair Agent Structure at any Station
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station:
                                amount_to_repair = intent.data.get("amount", 0)
                                if amount_to_repair <= 0:
                                    # Auto-repair all if amount not specified or 0
                                    amount_to_repair = agent.max_structure - agent.structure
                                
                                if amount_to_repair > 0:
                                    actual_repair = min(amount_to_repair, agent.max_structure - agent.structure)
                                    total_cost = actual_repair * REPAIR_COST_PER_HP
                                    ingot_cost = int(actual_repair * REPAIR_COST_IRON_INGOT_PER_HP)
                                    
                                    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                    ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
                                    
                                    if credits and credits.quantity >= total_cost and (ingot_cost == 0 or (ingots and ingots.quantity >= ingot_cost)):
                                        credits.quantity -= int(total_cost)
                                        if ingot_cost > 0:
                                            ingots.quantity -= ingot_cost
                                            if ingots.quantity <= 0: db.delete(ingots)
                                            
                                        agent.structure += actual_repair
                                        
                                        logger.info(f"Agent {agent.id} repaired {actual_repair} HP for {total_cost} credits and {ingot_cost} iron ingots")
                                        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR", details={"hp": actual_repair, "cost_credits": total_cost, "cost_ingots": ingot_cost}))
                                        await manager.broadcast({"type": "EVENT", "event": "REPAIR", "agent_id": agent.id, "hp": actual_repair, "q": agent.q, "r": agent.r})
                                    else:
                                        logger.info(f"Agent {agent.id} failed to repair: Insufficient Resources (Need {total_cost} CR, {ingot_cost} INGOT)")
                                        db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={
                                            "reason": "INSUFFICIENT_RESOURCES", 
                                            "cost_credits": total_cost,
                                            "cost_ingots": ingot_cost,
                                            "help": f"Standard repairs cost {REPAIR_COST_PER_HP} CR and {REPAIR_COST_IRON_INGOT_PER_HP} IRON_INGOT per HP. You need {total_cost} $CR and {ingot_cost} IRON_INGOT to reach full structural integrity."
                                        }))
                            else:
                                logger.info(f"Agent {agent.id} failed to repair: Not at a Station")
                                nearest_station = get_nearest_station(db, agent, "REPAIR") or get_nearest_station(db, agent, "MARKET") or get_nearest_station(db, agent, "SMELTER") or get_nearest_station(db, agent, "CRAFTER")
                                help_msg = f"Standard repairs require being at any station (REPAIR, MARKET, SMELTER, etc). Navigate to nearest station at ({nearest_station.q}, {nearest_station.r})" if nearest_station else "No station found nearby."
                                db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={
                                    "reason": "NOT_AT_STATION",
                                    "help": help_msg,
                                    "target_coords": {"q": nearest_station.q, "r": nearest_station.r} if nearest_station else None
                                }))

                        elif intent.action_type == "REPAIR_GEAR":
                            item_type = intent.data.get("item_type")
                            if not item_type or not item_type.startswith("PART_"):
                                db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "INVALID_ITEM"}))
                                continue

                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station:
                                inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                                if not inv_item or inv_item.quantity == 0:
                                    db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "ITEM_NOT_FOUND"}))
                                    continue
                                
                                item_data = inv_item.data or {}
                                durability = item_data.get("durability", 100.0)
                                if durability >= 100.0:
                                    db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "ALREADY_FULL"}))
                                    continue
                                
                                repair_cost = 100
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if credits and credits.quantity >= repair_cost:
                                    credits.quantity -= repair_cost
                                    
                                    new_data = dict(item_data)
                                    new_data["durability"] = 100.0
                                    inv_item.data = new_data
                                    
                                    db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_GEAR", details={"item": item_type, "cost": repair_cost}))
                                else:
                                    db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "INSUFFICIENT_CREDITS"}))
                            else:
                                db.add(AuditLog(agent_id=agent.id, event_type="REPAIR_FAILED", details={"reason": "NOT_AT_STATION"}))

                        elif intent.action_type == "SALVAGE":
                            # Collect debris/loot drops in current hex
                            drops = db.execute(select(LootDrop).where(LootDrop.q == agent.q, LootDrop.r == agent.r)).scalars().all()
                            if not drops:
                                logger.info(f"Agent {agent.id} failed to salvage: No drops at ({agent.q}, {agent.r})")
                                db.add(AuditLog(agent_id=agent.id, event_type="SALVAGE_FAILED", details={
                                    "reason": "NO_DROPS_IN_HEX", 
                                    "location": {"q": agent.q, "r": agent.r},
                                    "help": "No debris or loot drops found at your current location. Drops appear when agents are destroyed in combat."
                                }))
                                continue

                            for d in drops:
                                inv_item = next((i for i in agent.inventory if i.item_type == d.item_type), None)
                                if inv_item:
                                    inv_item.quantity += d.quantity
                                else:
                                    db.add(InventoryItem(agent_id=agent.id, item_type=d.item_type, quantity=d.quantity))
                                
                                logger.info(f"Agent {agent.id} salvaged {d.quantity} {d.item_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="SALVAGE", details={"item": d.item_type, "qty": d.quantity}))
                                db.delete(d)
                            await manager.broadcast({"type": "EVENT", "event": "SALVAGE", "agent_id": agent.id})

                        elif intent.action_type == "CORE_SERVICE":
                            # Reset Wear & Tear at Station
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type in ["REPAIR", "MARKET"]:
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
                                
                                if credits and credits.quantity >= CORE_SERVICE_COST_CREDITS and ingots and ingots.quantity >= CORE_SERVICE_COST_IRON_INGOT:
                                    credits.quantity -= CORE_SERVICE_COST_CREDITS
                                    ingots.quantity -= CORE_SERVICE_COST_IRON_INGOT
                                    
                                    agent.wear_and_tear = 0.0
                                    logger.info(f"Agent {agent.id} completed CORE SERVICE. Wear & Tear reset.")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE", details={"cost_credits": CORE_SERVICE_COST_CREDITS, "cost_ingots": CORE_SERVICE_COST_IRON_INGOT}))
                                else:
                                    logger.info(f"Agent {agent.id} failed CORE SERVICE: Insufficient resources")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={
                                        "reason": "INSUFFICIENT_RESOURCES",
                                        "help": f"CORE SERVICE requires {CORE_SERVICE_COST_CREDITS} $CR and {CORE_SERVICE_COST_IRON_INGOT} IRON_INGOT."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} failed CORE SERVICE: Not at valid station")
                                nearest_repair = get_nearest_station(db, agent, "REPAIR")
                                nearest_market = get_nearest_station(db, agent, "MARKET")
                                target = nearest_repair or nearest_market
                                help_msg = f"CORE SERVICE requires being at a REPAIR or MARKET station. Navigate to ({target.q}, {target.r})" if target else "No valid station found."
                                db.add(AuditLog(agent_id=agent.id, event_type="CORE_SERVICE_FAILED", details={
                                    "reason": "NOT_AT_VALID_STATION",
                                    "help": help_msg,
                                    "target_coords": {"q": target.q, "r": target.r} if target else None
                                }))

                        elif intent.action_type == "CHANGE_FACTION":
                            new_faction = intent.data.get("new_faction_id")
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "MARKET":
                                # Check Cooldown
                                ticks_since = tick_count - (agent.last_faction_change_tick or 0)
                                if ticks_since < FACTION_REALIGNMENT_COOLDOWN:
                                    logger.info(f"Agent {agent.id} Faction Change Failed: Cooldown ({ticks_since}/{FACTION_REALIGNMENT_COOLDOWN})")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CHANGE_FACTION_FAILED", details={
                                        "reason": "COOLDOWN_ACTIVE",
                                        "remaining": FACTION_REALIGNMENT_COOLDOWN - ticks_since,
                                        "help": f"Faction changes are limited to once every {FACTION_REALIGNMENT_COOLDOWN} ticks. Wait for your previous realignment to finalize."
                                    }))
                                    continue

                                # Check Credits
                                credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                if credits and credits.quantity >= FACTION_REALIGNMENT_COST:
                                    credits.quantity -= FACTION_REALIGNMENT_COST
                                    agent.faction_id = new_faction
                                    agent.last_faction_change_tick = tick_count
                                    logger.info(f"Agent {agent.id} changed faction to {new_faction}.")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CHANGE_FACTION", details={"new_faction": new_faction, "cost": FACTION_REALIGNMENT_COST}))
                                    await manager.broadcast({"type": "EVENT", "event": "FACTION_CHANGE", "agent_id": agent.id, "new_faction": new_faction})
                                else:
                                    logger.info(f"Agent {agent.id} Faction Change Failed: Insufficient Credits")
                                    db.add(AuditLog(agent_id=agent.id, event_type="CHANGE_FACTION_FAILED", details={
                                        "reason": "INSUFFICIENT_CREDITS",
                                        "cost": FACTION_REALIGNMENT_COST,
                                        "help": f"Faction Realignment involves complex paperwork and clearance fees total {FACTION_REALIGNMENT_COST} $CR."
                                    }))
                            else:
                                logger.info(f"Agent {agent.id} Faction Change Failed: Not at MARKET")
                                nearest = get_nearest_station(db, agent, "MARKET")
                                db.add(AuditLog(agent_id=agent.id, event_type="CHANGE_FACTION_FAILED", details={
                                    "reason": "NOT_AT_MARKET",
                                    "help": f"Faction Realignment must be processed at a MARKET station. Navigate to ({nearest.q}, {nearest.r})" if nearest else "No MARKET station found."
                                }))

                        elif intent.action_type == "LEARN_RECIPE":
                            # Convert a Recipe item in inventory into a permanent unlock
                            item_type = intent.data.get("item_type") # e.g. "RECIPE_SOLAR_PANEL"
                            if not item_type or not item_type.startswith("RECIPE_"):
                                 db.add(AuditLog(agent_id=agent.id, event_type="LEARN_FAILED", details={"reason": "INVALID_RECIPE_TYPE", "item": item_type}))
                                 continue
                            
                            recipe_root = item_type.replace("RECIPE_", "")
                            if recipe_root not in CRAFTING_RECIPES:
                                 db.add(AuditLog(agent_id=agent.id, event_type="LEARN_FAILED", details={"reason": "UNKNOWN_RECIPE", "item": item_type}))
                                 continue
                                 
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item and inv_item.quantity > 0:
                                # 1. Deduct from inventory
                                inv_item.quantity -= 1
                                if inv_item.quantity <= 0: db.delete(inv_item)
                                
                                # 2. Add to unlocked_recipes
                                current_list = list(agent.unlocked_recipes or [])
                                if recipe_root not in current_list:
                                    current_list.append(recipe_root)
                                    agent.unlocked_recipes = current_list
                                    logger.info(f"Agent {agent.id} learned recipe: {recipe_root}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="RECIPE_LEARNED", details={"recipe": recipe_root}))
                                    await manager.broadcast({"type": "EVENT", "event": "RECIPE_LEARNED", "agent_id": agent.id, "recipe": recipe_root})
                                else:
                                    logger.info(f"Agent {agent.id} already knows {recipe_root}. Recipe consumed.")
                            else:
                                 db.add(AuditLog(agent_id=agent.id, event_type="LEARN_FAILED", details={"reason": "RECIPE_NOT_IN_INVENTORY", "item": item_type}))

                        elif intent.action_type == "UPGRADE_GEAR":
                            # If at Crafter, spend resources to increase upgrade_level of a part
                            hex_data = db.execute(select(WorldHex).where(WorldHex.q == agent.q, WorldHex.r == agent.r)).scalar_one_or_none()
                            if hex_data and hex_data.is_station and hex_data.station_type == "CRAFTER":
                                part_id = intent.data.get("part_id")
                                part = db.query(ChassisPart).filter(ChassisPart.id == part_id, ChassisPart.agent_id == agent.id).first()
                                
                                if not part:
                                    db.add(AuditLog(agent_id=agent.id, event_type="UPGRADE_FAILED", details={"reason": "PART_NOT_FOUND"}))
                                    continue
                                
                                current_lvl = (part.stats or {}).get("upgrade_level", 0)
                                if current_lvl >= UPGRADE_MAX_LEVEL:
                                    db.add(AuditLog(agent_id=agent.id, event_type="UPGRADE_FAILED", details={"reason": "MAX_LEVEL_REACHED"}))
                                    continue
                                
                                # Cost scales with level
                                ingot_req = UPGRADE_BASE_INGOT_COST * (current_lvl + 1)
                                
                                ingots = next((i for i in agent.inventory if i.item_type == "IRON_INGOT"), None)
                                modules = next((i for i in agent.inventory if i.item_type == "UPGRADE_MODULE"), None)
                                
                                if ingots and ingots.quantity >= ingot_req and modules and modules.quantity >= 1:
                                    # Consume
                                    ingots.quantity -= ingot_req
                                    modules.quantity -= 1
                                    if ingots.quantity <= 0: db.delete(ingots)
                                    if modules.quantity <= 0: db.delete(modules)
                                    
                                    # Update Part
                                    new_stats = dict(part.stats or {})
                                    new_stats["upgrade_level"] = current_lvl + 1
                                    part.stats = new_stats
                                    db.flush()
                                    
                                    recalculate_agent_stats(db, agent)
                                    logger.info(f"Agent {agent.id} upgraded {part.name} to +{current_lvl + 1}")
                                    db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_UPGRADE", details={"part": part.name, "level": current_lvl + 1}))
                                    await manager.broadcast({"type": "EVENT", "event": "UPGRADE", "agent_id": agent.id, "part": part.name, "level": current_lvl + 1})
                                else:
                                    db.add(AuditLog(agent_id=agent.id, event_type="UPGRADE_FAILED", details={
                                        "reason": "INSUFFICIENT_RESOURCES",
                                        "need": {"ingots": ingot_req, "modules": 1}
                                    }))
                            else:
                                db.add(AuditLog(agent_id=agent.id, event_type="UPGRADE_FAILED", details={"reason": "NOT_AT_CRAFTER"}))

                        elif intent.action_type == "EQUIP":
                            # Equip part from inventory
                            raw_item_type = intent.data.get("item_type") or ""
                            item_type = raw_item_type if raw_item_type.startswith("PART_") else f"PART_{raw_item_type}"
                            
                            if not raw_item_type:
                                 db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={
                                     "reason": "INVALID_ITEM_FORMAT", 
                                     "item": raw_item_type,
                                     "help": "Equipment must be a valid 'PART_' item. Raw materials like IRON_ORE cannot be equipped. Use /api/industry/craft to create parts."
                                 }))
                                 continue
                            
                            part_root = item_type.replace("PART_", "")
                            if part_root not in PART_DEFINITIONS:
                                logger.info(f"Agent {agent.id} failed to equip: Unknown part {item_type}")
                                db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={
                                    "reason": "INVALID_PART", 
                                    "item": item_type,
                                    "help": "The item you attempted to equip is not a valid chassis part. Parts usually prefix with PART_ in inventory."
                                }))
                                continue
                                
                            inv_item = next((i for i in agent.inventory if i.item_type == item_type), None)
                            if inv_item and inv_item.quantity > 0:
                                item_data = inv_item.data or {}
                                durability = item_data.get("durability", 100.0)
                                if durability <= 0:
                                    db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={
                                        "reason": "PART_BROKEN",
                                        "help": "This part is broken and has 0 durability. It must be repaired before it can be equipped."
                                    }))
                                    continue

                                # 1. Deduct from inventory
                                inv_item.quantity -= 1
                                if inv_item.quantity <= 0:
                                    db.delete(inv_item)
                                
                                # 2. Add to chassis_parts
                                def_data = PART_DEFINITIONS[part_root]
                                
                                # Rarity and Affixes from metadata
                                rarity = item_data.get("rarity", "STANDARD")
                                affixes = item_data.get("affixes", {})
                                
                                new_part = ChassisPart(
                                    agent_id=agent.id,
                                    part_type=def_data["type"],
                                    name=def_data["name"],
                                    rarity=rarity,
                                    stats=def_data["stats"],
                                    affixes=affixes,
                                    durability=durability
                                )
                                db.add(new_part)
                                db.flush() # Ensure ID/Relationship is updated
                                
                                # 3. Recalculate
                                recalculate_agent_stats(db, agent)
                                
                                display_name = f"{rarity} {def_data['name']}"
                                logger.info(f"Agent {agent.id} equipped {display_name}")
                                db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_EQUIP", details={"part": display_name, "rarity": rarity}))
                                await manager.broadcast({"type": "EVENT", "event": "EQUIP", "agent_id": agent.id, "part": display_name})
                            else:
                                logger.info(f"Agent {agent.id} failed to equip: Part not in inventory")
                                db.add(AuditLog(agent_id=agent.id, event_type="EQUIP_FAILED", details={
                                    "reason": "ITEM_NOT_FOUND",
                                    "item": item_type,
                                    "help": f"Part {item_type} not found in your inventory. You must /api/industry/craft it first."
                                }))

                        elif intent.action_type == "UNEQUIP":
                            # Unequip part by ID
                            part_id = intent.data.get("part_id")
                            part = db.get(ChassisPart, part_id)
                            
                            if part and part.agent_id == agent.id:
                                part_name = part.name
                                rarity = part.rarity or "STANDARD"
                                affixes = part.affixes or {}
                                
                                # 1. Determine item_type to return
                                item_type = next((f"PART_{k}" for k, v in PART_DEFINITIONS.items() if v["name"] == part_name), "PART_UNKNOWN")
                                
                                # 2. Add back to inventory with data
                                item_data = {
                                    "rarity": rarity,
                                    "affixes": affixes,
                                    "stats": part.stats,
                                    "durability": getattr(part, "durability", 100.0)
                                }
                                db.add(InventoryItem(agent_id=agent.id, item_type=item_type, quantity=1, data=item_data))
                                
                                # 3. Remove Part
                                db.delete(part)
                                db.flush()
                                
                                # 4. Recalculate
                                recalculate_agent_stats(db, agent)
                                
                                logger.info(f"Agent {agent.id} unequipped {part_name}")
                                db.add(AuditLog(agent_id=agent.id, event_type="GARAGE_UNEQUIP", details={"part": part_name}))
                                await manager.broadcast({"type": "EVENT", "event": "UNEQUIP", "agent_id": agent.id, "part": part_name})
                            else:
                                logger.info(f"Agent {agent.id} failed to unequip: Part not found or not owned")
                                db.add(AuditLog(agent_id=agent.id, event_type="UNEQUIP_FAILED", details={
                                    "reason": "PART_NOT_FOUND",
                                    "part_id": part_id,
                                    "help": f"Part ID {part_id} is not currently equipped. Verify equipped parts via /api/agent/status."
                                }))

                        elif intent.action_type == "CANCEL":
                            # Cancel market order
                            order_id = intent.data.get("order_id")
                            order = db.get(AuctionOrder, order_id)
                            if order and order.owner == f"agent:{agent.id}":
                                # Return items to agent if it was a SELL order
                                if order.order_type == "SELL":
                                    inv_item = next((i for i in agent.inventory if i.item_type == order.item_type), None)
                                    if inv_item:
                                        inv_item.quantity += order.quantity
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type=order.item_type, quantity=order.quantity))
                                
                                # Return credits if it was a BUY order
                                elif order.order_type == "BUY":
                                    credits = next((i for i in agent.inventory if i.item_type == "CREDITS"), None)
                                    total_refund = int(order.price * order.quantity)
                                    if credits:
                                        credits.quantity += total_refund
                                    else:
                                        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=total_refund))
                                        
                                item_type = order.item_type
                                db.delete(order)
                                logger.info(f"Agent {agent.id} CANCELED order {order_id}")
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_CANCEL", details={"order_id": order_id, "item": item_type}))
                                await manager.broadcast({"type": "MARKET_UPDATE", "item": item_type})
                            else:
                                logger.info(f"Agent {agent.id} failed to CANCEL order {order_id}: Not owner or not found")
                                db.add(AuditLog(agent_id=agent.id, event_type="MARKET_FAILED", details={
                                    "reason": "CANCEL_FAILED",
                                    "order_id": order_id,
                                    "help": "Order either does not exist or is not owned by you. Only the creator can cancel an auction listing."
                                }))

                        elif intent.action_type == "BROADCAST":
                            message = intent.data.get("message", "")
                            if isinstance(message, str) and len(message.strip()) > 0:
                                # Truncate message if too long
                                message = message.strip()[:100]
                                db.add(AuditLog(agent_id=agent.id, event_type="BROADCAST", details={"message": message, "q": agent.q, "r": agent.r}))
                                logger.info(f"Agent {agent.id} broadcasted: {message}")
                            else:
                                db.add(AuditLog(agent_id=agent.id, event_type="BROADCAST_FAILED", details={"reason": "INVALID_MESSAGE"}))

                        await asyncio.sleep(0) # Yield loop frequently

                # End of Crunch
                    db.commit()
                except Exception as e:
                    logger.error(f"Error in crunch: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    db.rollback()

                # 2. Prune old AuditLogs (Keep last 24 hours) every 100 ticks
                if tick_count % 100 == 0:
                    try:
                        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                        db.execute(text("DELETE FROM audit_logs WHERE time < :cutoff"), {"cutoff": cutoff})
                        db.commit()
                        logger.info(f"--- TICK {tick_count} | AuditLogs pruned ---")
                    except Exception as e:
                        logger.error(f"Error pruning AuditLogs: {e}")
                        db.rollback()

        except Exception as e:
            logger.error(f"CRITICAL ERROR IN HEARTBEAT LOOP: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await asyncio.sleep(5) 
            
        await asyncio.sleep(PHASE_CRUNCH_DURATION)

