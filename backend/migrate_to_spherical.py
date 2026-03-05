import os
import sys
import logging
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Base, Agent, LootDrop, AgentMessage, Intent, WorldHex, Sector
from game_helpers import wrap_coords

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("db_migration")
logging.basicConfig(level=logging.INFO)

def migrate_database():
    db = SessionLocal()
    logger.info("Starting Spherical World Database Migration...")

    # 1. Wrap Agents
    agents = db.execute(select(Agent)).scalars().all()
    wrapped_agents = 0
    for agent in agents:
        wq, wr = wrap_coords(agent.q, agent.r)
        if wq != agent.q or wr != agent.r:
            agent.q = wq
            agent.r = wr
            wrapped_agents += 1
    logger.info(f"Wrapped {wrapped_agents} Agents.")

    # 2. Wrap LootDrops
    loots = db.execute(select(LootDrop)).scalars().all()
    wrapped_loot = 0
    for loot in loots:
        wq, wr = wrap_coords(loot.q, loot.r)
        if wq != loot.q or wr != loot.r:
            loot.q = wq
            loot.r = wr
            wrapped_loot += 1
    logger.info(f"Wrapped {wrapped_loot} Loot Drops.")

    # 3. Wrap AgentMessages
    messages = db.execute(select(AgentMessage)).scalars().all()
    wrapped_msgs = 0
    for msg in messages:
        if msg.q is not None and msg.r is not None:
            wq, wr = wrap_coords(msg.q, msg.r)
            if wq != msg.q or wr != msg.r:
                msg.q = wq
                msg.r = wr
                wrapped_msgs += 1
    logger.info(f"Wrapped {wrapped_msgs} Agent Messages.")

    # 4. Wrap Pending Intents
    intents = db.execute(select(Intent)).scalars().all()
    wrapped_intents = 0
    for intent in intents:
        if isinstance(intent.data, dict) and "target_q" in intent.data and "target_r" in intent.data:
            tq = intent.data["target_q"]
            tr = intent.data["target_r"]
            if tq is not None and tr is not None:
                wq, wr = wrap_coords(int(tq), int(tr))
                if wq != int(tq) or wr != int(tr):
                    # Create a new dict to ensure SQLAlchemy detects the JSON mutation
                    new_data = dict(intent.data)
                    new_data["target_q"] = wq
                    new_data["target_r"] = wr
                    intent.data = new_data
                    wrapped_intents += 1
    logger.info(f"Wrapped {wrapped_intents} Pending Intents.")

    # 5. Clear Old Map Data (WorldHex and Sector)
    # We delete these because the spherical map is generated differently.
    # The subsequent run of `seed_world.py` will rebuild the 100x101 map exactly.
    logger.info("Clearing old WorldHex and Sector data to prepare for re-seeding...")
    deleted_hexes = db.query(WorldHex).delete()
    deleted_sectors = db.query(Sector).delete()
    logger.info(f"Deleted {deleted_hexes} legacy hexes and {deleted_sectors} legacy sectors.")

    # Commit the changes
    db.commit()
    db.close()
    
    logger.info("Migration Step 1 Complete! Data has been wrapped.")
    logger.info("Please run `python backend/seed_world.py` next to rebuild the map.")

if __name__ == "__main__":
    migrate_database()
