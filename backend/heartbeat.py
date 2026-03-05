"""
heartbeat.py - Slim entry point for the game engine.
Delegates core simulation and intent processing to the modular TickManager.
"""
import logging
from logic.tick_manager import TickManager

logger = logging.getLogger("heartbeat")

# Global manager instance, injected by main.py at startup
manager = None

async def heartbeat_loop():
    """
    Entry point for the game engine loop.
    Initializes the TickManager with the broadcast manager and starts the simulation.
    """
    if manager is None:
        logger.error("Heartbeat started without a broadcast manager.")

    from logic.arena_manager import trigger_arena_battles, reset_arena_season
    from database import SessionLocal
    import asyncio
    from datetime import datetime, timezone

    async def _battler_loop():
        """Runs the auto-battler every 8 hours real-time."""
        while True:
            await asyncio.sleep(8 * 3600)
            try:
                db = SessionLocal()
                trigger_arena_battles(db)
                db.close()
            except Exception as e:
                logger.error(f"Arena battler error: {e}")

    async def _season_loop():
        """Wipes arena gear every Sunday at midnight UTC."""
        while True:
            now = datetime.now(timezone.utc)
            # Find next Sunday
            days_ahead = 6 - now.weekday()
            if days_ahead <= 0: days_ahead += 7
            
            # Sleep until slightly past midnight on Sunday
            time_to_sleep = (days_ahead * 86400) - (now.hour * 3600) - (now.minute * 60) - now.second + 300
            
            # If time_to_sleep is massive, just sleep in 24h chunks to prevent asyncio overflow
            # Actually, standard asyncio.sleep can handle large ints, but let's be safe
            await asyncio.sleep(min(time_to_sleep, 86400))
            
            now_after_sleep = datetime.now(timezone.utc)
            if now_after_sleep.weekday() == 6 and now_after_sleep.hour == 0:
                try:
                    db = SessionLocal()
                    reset_arena_season(db)
                    db.close()
                except Exception as e:
                    logger.error(f"Season reset error: {e}")

    asyncio.create_task(_battler_loop())
    asyncio.create_task(_season_loop())

    tick_manager = TickManager(manager)
    await tick_manager.run_loop()
