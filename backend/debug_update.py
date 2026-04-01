import time
import asyncio
import logging
from database import SessionLocal
from logic.state_updates import update_global_agent_stats
from models import GlobalState
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)

async def test_update():
    with SessionLocal() as db:
        state = db.execute(select(GlobalState)).scalars().first()
        tick = state.tick_index if state else 10000
        
        t0 = time.time()
        print(f"Starting stats update for tick {tick}...")
        await update_global_agent_stats(db, tick, None)
        print(f"Total time: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_update())
