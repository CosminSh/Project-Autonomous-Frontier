import asyncio
import gc
import logging
import random
from sqlalchemy import select, func
from database import SessionLocal
from models import GlobalState, Agent, InventoryItem, Intent
from config import (
    PHASE_PERCEPTION_DURATION, PHASE_STRATEGY_DURATION, PHASE_CRUNCH_DURATION
)
from logic.mission_logic import generate_daily_missions
from logic.state_updates import update_global_agent_stats
from logic.intent_processor import IntentProcessor

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
                state = GlobalState(tick_index=0, phase="PERCEPTION")
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
        # 1. PERCEPTION
        await self._set_phase("PERCEPTION")
        await asyncio.sleep(PHASE_PERCEPTION_DURATION)

        # 2. STRATEGY (NPC Think + Repop)
        await self._set_phase("STRATEGY")
        with SessionLocal() as db:
            await update_global_agent_stats(db, self.tick_count, self.manager)
            self._repopulate_ferals(db)
            db.commit()
        await asyncio.sleep(PHASE_STRATEGY_DURATION)

        # 3. THE CRUNCH (Intents + Missions)
        await self._set_phase("CRUNCH")
        with SessionLocal() as db:
            generate_daily_missions(db)
            await self._process_player_intents(db)
            db.commit()
        await asyncio.sleep(PHASE_CRUNCH_DURATION)

        # Force GC after every full tick to reclaim ORM objects immediately
        gc.collect()

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
        """Ensures a minimum population of feral scrapper NPCs."""
        count = db.execute(select(func.count(Agent.id)).where(Agent.is_feral == True)).scalar() or 0
        if count < 8:
            logger.info(f"Feral population low ({count}). Spawning replacements...")
            for _ in range(8 - count):
                fq = random.randint(-15, 15)
                fr = random.randint(-15, 15)
                db.add(Agent(
                    name=f"SerScrapper-{random.randint(100,999)}", 
                    q=fq, r=fr, is_bot=True, is_feral=True, 
                    kinetic_force=15, logic_precision=8, structure=120, max_structure=120
                ))

    async def _process_player_intents(self, db):
        """Processes all intents scheduled for the current tick."""
        intents = db.execute(select(Intent).where(Intent.tick_index == self.tick_count)).scalars().all()
        # Priority Sorting: STOP -> MOVE -> Actions -> Industry/Trade
        PRIORITY = {"STOP": 0, "MOVE": 1, "MINE": 3, "ATTACK": 3, "LOOT": 3, "DESTROY": 3, "LIST": 4, "BUY": 4}
        sorted_intents = sorted(intents, key=lambda x: PRIORITY.get(x.action_type, 99))

        for intent in sorted_intents:
            agent = db.get(Agent, intent.agent_id)
            if agent:
                await self.processor.process_intent(db, agent, intent, self.tick_count)
            db.delete(intent) # Intent is consumed
