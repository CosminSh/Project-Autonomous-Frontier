import asyncio
import gc
import logging
import random
from sqlalchemy import select, func, delete
from database import SessionLocal
from models import GlobalState, Agent, InventoryItem, Intent, AgentMessage
from datetime import datetime, timezone, timedelta
from config import (
    PHASE_SCAN_DURATION, PHASE_DECIDE_DURATION, PHASE_EXECUTE_DURATION
)
from logic.mission_logic import generate_daily_missions
from logic.state_updates import update_global_agent_stats
from logic.intent_processor import IntentProcessor
from logic.arena_manager import generate_daily_matchups
from game_helpers import get_hex_terrain_data
from logic.world_events import spawn_random_anomaly, cleanup_expired_anomalies

logger = logging.getLogger("heartbeat.tick_manager")

class TickManager:
    def __init__(self, manager):
        self.manager = manager
        self.processor = IntentProcessor(manager)
        self.tick_count = 0

    async def run_loop(self):
        """Infinite game loop driving phases and ticks."""
        # Initialize Tick Count from DB
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            if not state:
                state = GlobalState(tick_index=0, phase="SCAN")
                db.add(state)
                db.commit()
            self.tick_count = state.tick_index

        while True:
            try:
                self.tick_count += 1
                await self._run_tick()
            except Exception as e:
                logger.error(f"Fatal error in tick {self.tick_count}: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _run_tick(self):
        """Executes a single game tick across three phases."""
        # 1. SCAN
        await self._set_phase("SCAN")
        await asyncio.sleep(PHASE_SCAN_DURATION)

        # 2. DECIDE (NPC Think + Repop)
        await self._set_phase("DECIDE")
        with SessionLocal() as db:
            await update_global_agent_stats(db, self.tick_count, self.manager)
            self._repopulate_ferals(db)
            if self.tick_count % 10 == 0:
                self._repopulate_resources(db)
            
            # Anomaly System (Spawn every 400 ticks, Cleanup every 10)
            cleanup_expired_anomalies(db, self.tick_count)
            if self.tick_count % 400 == 0:
                await spawn_random_anomaly(db, self.tick_count, self.manager)
                
            db.commit()
        await asyncio.sleep(PHASE_DECIDE_DURATION)

        # 3. EXECUTE (Intents + Missions + Daily Matchups)
        await self._set_phase("EXECUTE")
        with SessionLocal() as db:
            generate_daily_missions(db)
            
            # Daily Arena Matchmaking (Every 2400 ticks ~ 24 hours)
            if self.tick_count % 2400 == 0:
                generate_daily_matchups(db)

            await self._process_player_intents(db)
            
            if self.tick_count % 100 == 0:
                self._cleanup_old_messages(db)
                
            db.commit()
        await asyncio.sleep(PHASE_EXECUTE_DURATION)

    async def _set_phase(self, phase_name):
        """Updates global state and broadcasts phase changes."""
        with SessionLocal() as db:
            state = db.execute(select(GlobalState)).scalars().first()
            state.tick_index = self.tick_count
            state.phase = phase_name
            db.commit()
            logger.info(f"--- TICK {self.tick_count} | PHASE: {phase_name} ---")
            await self.manager.broadcast({"type": "PHASE_CHANGE", "tick": self.tick_count, "phase": phase_name})

    def _repopulate_ferals(self, db):
        """Ensures a minimum population of feral scrapper NPCs, tiered by distance."""
        count = db.execute(select(func.count(Agent.id)).where(Agent.is_feral == True)).scalar() or 0
        if count < 12:
            logger.info(f"Feral population low ({count}). Spawning replacements...")
            for _ in range(12 - count):
                # Pick a random distance and angle
                angle = random.uniform(0, 3.14159 * 2)
                dist = random.randint(6, 60)
                # Simple axial approx for spawning
                fq = int(dist * random.uniform(-1, 1))
                fr = int(dist * random.uniform(-1, 1))
                fq, fr = self._axial_clamp(fq, fr, dist)
                
                # Tiering logic (mirrors seed_world)
                if dist <= 15:
                    # Lvl 1: Drifter (Passive, low stats)
                    name = f"Feral-Drifter-{random.randint(100,999)}"
                    h, dmg, acc, spd, arm = 80, 8, 5, 10, 2
                    aggro = False
                elif dist <= 35:
                    # Lvl 2: Scrapper (Aggressive, mid stats)
                    name = f"Feral-Scrapper-{random.randint(100,999)}"
                    h, dmg, acc, spd, arm = 120, 15, 8, 10, 5
                    aggro = True
                else:
                    # Lvl 3: Raider (Elite)
                    name = f"Feral-Raider-{random.randint(100,999)}"
                    h, dmg, acc, spd, arm = 200, 25, 12, 12, 10
                    aggro = True

                db.add(Agent(
                    name=name, q=fq, r=fr, is_bot=True, is_feral=True,
                    is_aggressive=aggro,
                    health=h, max_health=h, damage=dmg, accuracy=acc, speed=spd, armor=arm
                ))

    def _axial_clamp(self, q, r, dist):
        """Roughly clamps q,r to a dist circle for spawning."""
        from game_helpers import get_hex_distance, wrap_coords
        # If too far or close, just wrap and return
        return wrap_coords(q, r)

    def _repopulate_resources(self, db):
        """Ensures a minimum number of resource nodes exist globally."""
        from models import WorldHex
        # Check total asteroid count
        count = db.execute(select(func.count(WorldHex.id)).where(WorldHex.terrain_type == "ASTEROID")).scalar() or 0
        
        # If we have less than 400 asteroids globally, spawn a batch
        if count < 400:
            logger.info(f"Resource nodes low ({count}). Spawning new veins...")
            
            # MEMORY OPTIMIZATION: Don't load all VOID hexes. Load a random sample of 1000.
            # We use a simple limit to avoid loading 10,000+ objects into RAM.
            voids = db.execute(
                select(WorldHex)
                .where(WorldHex.terrain_type == "VOID", WorldHex.is_station == False)
                .limit(1000)
            ).scalars().all()
            
            if not voids: return
            
            # Spawn a few per cycle
            random.shuffle(voids)
            spawned = 0
            for h in voids:
                data = get_hex_terrain_data(h.q, h.r)
                
                # Check if it's natural OR if we are getting desperate (more than halfway through sample with no spawns)
                if data["terrain_type"] == "ASTEROID" or (spawned == 0 and voids.index(h) > 500):
                    h.terrain_type = "ASTEROID"
                    h.resource_type = data["resource_type"] or random.choice(["IRON_ORE", "COPPER_ORE", "GOLD_ORE"])
                    h.resource_density = data["resource_density"] or random.uniform(0.1, 0.5)
                    h.resource_quantity = data["resource_quantity"] or random.randint(50, 200)
                    spawned += 1
                if spawned >= 20: break
            
            # Force cleanup of the 'voids' list from memory
            del voids
            gc.collect() 

    async def _process_player_intents(self, db):
        """Processes all intents scheduled for the current or recent ticks."""
        # 1. Catch-up logic
        min_tick = max(0, self.tick_count - 5)
        intents = db.execute(select(Intent).where(Intent.tick_index >= min_tick, Intent.tick_index <= self.tick_count)).scalars().all()
        
        # 2. Hard Cleanup: Delete all intents older than our catch-up window
        db.execute(delete(Intent).where(Intent.tick_index < min_tick))
        
        if not intents:
            return

        # 2. deduplicate intents: only one intent per agent per action type
        unique_intents = {}
        for i in intents:
            key = (i.agent_id, i.action_type)
            if key not in unique_intents:
                unique_intents[key] = i
        intents = list(unique_intents.values())

        # 3. BATCH LOAD AGENTS: Avoid N+1 database queries during processing
        agent_ids = {i.agent_id for i in intents}
        from sqlalchemy.orm import selectinload
        agents_map = {
            a.id: a for a in db.execute(
                select(Agent)
                .where(Agent.id.in_(agent_ids))
                .options(selectinload(Agent.parts), selectinload(Agent.inventory), selectinload(Agent.corporation))
            ).scalars().all()
        }

        # Priority Sorting
        PRIORITY = {"STOP": 0, "MOVE": 1, "GO": 1, "MINE": 3, "ATTACK": 3, "LOOT": 3, "DESTROY": 3, "LIST": 4, "BUY": 4}
        sorted_intents = sorted(intents, key=lambda x: PRIORITY.get(x.action_type, 99))

        processed_count = 0
        for intent in sorted_intents:
            agent = agents_map.get(intent.agent_id)
            if agent:
                try:
                    await self.processor.process_intent(db, agent, intent, self.tick_count)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error in intent {intent.id}: {e}")
            db.delete(intent) 

        if self.manager:
            await self.manager.broadcast({
                "type": "EVENT", "event": "SIMULATION", "subtype": "COMPLETE",
                "tick": self.tick_count, "processed": processed_count
            })

        # 3. Global Activity Analytics -- Isolated Session to prevent transaction poisoning
        if processed_count > 0:
            with SessionLocal() as act_db:
                try:
                    from models import GlobalState
                    state = act_db.execute(select(GlobalState)).scalars().first()
                    if state:
                        state.actions_processed = (state.actions_processed or 0) + processed_count
                        act_db.commit()
                except Exception as e:
                    logger.debug(f"Activity counter update skipped: {e}")

    def _cleanup_old_messages(self, db):
        """Deletes chat messages older than 48 hours to prevent bloat."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        stmt = delete(AgentMessage).where(AgentMessage.timestamp < cutoff)
        result = db.execute(stmt)
        if result.rowcount > 0:
            logger.info(f"Cleaned up {result.rowcount} old chat messages.")
