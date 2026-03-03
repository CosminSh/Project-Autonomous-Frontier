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
        logger.error("Heartbeat started without a broadcast manager. Broadcasts will be disabled.")
    
    tick_manager = TickManager(manager)
    await tick_manager.run_loop()
