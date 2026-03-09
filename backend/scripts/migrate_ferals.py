import os
import sys
import random
import logging
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Ensure we can import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models import Agent, InventoryItem, ChassisPart
from seed_world import _spawn_feral, PART_DEFINITIONS

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("migrate_ferals")
logging.basicConfig(level=logging.INFO)

def migrate_ferals():
    db = SessionLocal()
    
    logger.info("Wiping existing bots and ferals...")
    # Delete all existing bots and ferals
    bots = db.execute(select(Agent).where(Agent.is_bot == True)).scalars().all()
    count = len(bots)
    for bot in bots:
        db.execute(text(f"DELETE FROM chassis_parts WHERE agent_id = {bot.id}"))
        db.execute(text(f"DELETE FROM inventory_items WHERE agent_id = {bot.id}"))
        db.delete(bot)
    db.commit()
    logger.info(f"Deleted {count} old bots/ferals.")

    # ── Spawn Worker Bots (near Hub) ──
    logger.info("Spawning industrial bots near hub...")
    for i in range(5):
        q_off = random.choice([-1, 0, 1])
        r_off = random.choice([-1, 0, 1])
        bot = Agent(
            name=f"Worker-Bot-{i}",
            q=max(0, q_off), r=max(0, r_off),
            is_bot=True, energy=100,
            health=100, max_health=100
        )
        db.add(bot)
        db.flush()
        db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
        drill_def = PART_DEFINITIONS.get("DRILL_UNIT")
        db.add(ChassisPart(agent_id=bot.id, part_type="Actuator", name=drill_def["name"], stats=drill_def["stats"]))

    # ── Spawn Ferals by Zone ──
    logger.info("Spawning new tiered feral AIs...")

    # Zone 1: Tier 1, Levels 1-10, dist 6-15 (Iron Belt)
    for i in range(15):
        q = random.randint(0, 99)
        r = random.randint(6, 15)
        lvl = random.randint(1, 10)
        _spawn_feral(db, "tier1", lvl, q, r, i)

    # Zone 2: Tier 2, Levels 11-20, dist 16-30 (Copper Belt)
    for i in range(12):
        q = random.randint(0, 99)
        r = random.randint(16, 30)
        lvl = random.randint(11, 20)
        _spawn_feral(db, "tier2", lvl, q, r, 100 + i)

    # Zone 3: Tier 3, Levels 21-30, dist 31-50 (Gold Fields)
    for i in range(10):
        q = random.randint(0, 99)
        r = random.randint(31, 50)
        lvl = random.randint(21, 30)
        _spawn_feral(db, "tier3", lvl, q, r, 200 + i)

    # Zone 4: Tier 4, Levels 31-45, dist 51+ (Deep Dark)
    for i in range(8):
        q = random.randint(0, 99)
        r = random.randint(55, 90)
        lvl = random.randint(31, 45)
        _spawn_feral(db, "tier4", lvl, q, r, 300 + i)

    db.commit()
    db.close()
    logger.info("Feral migration complete! The new tier system is active.")

if __name__ == "__main__":
    migrate_ferals()
