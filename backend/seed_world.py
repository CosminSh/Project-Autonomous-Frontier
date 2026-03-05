import os
import random
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Base, Sector, WorldHex, Agent, InventoryItem, ChassisPart
from config import MAP_MIN_Q, MAP_MAX_Q, MAP_MIN_R, MAP_MAX_R
from game_helpers import get_hex_terrain_data

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("seed_world")
logging.basicConfig(level=logging.INFO)

def seed_world():
    logger.info("Initializing tables (if not exist)...")
    Base.metadata.create_all(engine)
    db = SessionLocal()
    
    # Check if we already have data
    if db.query(WorldHex).count() > 0:
        logger.info("World already seeded. Skipping...")
        db.close()
        return
    
    logger.info(f"Seeding Spherical World ({MAP_MAX_Q+1}x{MAP_MAX_R+1})...")
    
    # Clean old data
    db.query(WorldHex).delete()
    db.query(Sector).delete()
    
    # Generate Sectors (10x10 grid of sectors, e.g. 10x11 to cover poles)
    for sq in range(10):
        for sr in range(11):
            db.add(Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}"))
    db.commit()

    logger.info("Generating hexes...")
    for q in range(MAP_MIN_Q, MAP_MAX_Q + 1):
        for r in range(MAP_MIN_R, MAP_MAX_R + 1):
            data = get_hex_terrain_data(q, r)
            
            # Use 10x10 sectors of size 10
            sq, sr = q // 10, r // 10
            sector = db.query(Sector).filter_by(q=sq, r=sr).first()
            
            db.add(WorldHex(
                sector_id=sector.id,
                q=q,
                r=r,
                terrain_type=data["terrain_type"],
                resource_type=data["resource_type"],
                resource_density=data["resource_density"],
                resource_quantity=data["resource_quantity"],
                is_station=data["is_station"],
                station_type=data["station_type"]
            ))
        if q % 10 == 0:
            db.flush()
            logger.info(f"Generated Longitude slice {q}...")
    
    # Add a demo agent if none exist
    if not db.query(Agent).first():
        agent = Agent(name="Striker-01", q=0, r=0, structure=100, max_structure=100, capacitor=100)
        db.add(agent)
        db.flush()
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        db.add(InventoryItem(agent_id=agent.id, item_type="IRON_ORE", quantity=50))
        db.add(ChassisPart(agent_id=agent.id, name="Basic Iron Drill", part_type="Actuator", stats={"kinetic_force": 10}))
        
        # Add Industrial Bots near Hub
        for i in range(5):
            bot = Agent(name=f"Worker-Bot-{i}", q=random.randint(0, 5), r=random.randint(0, 5), is_bot=True)
            db.add(bot)
            db.flush()
            db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
            db.add(ChassisPart(agent_id=bot.id, name="Industrial Drill", part_type="Actuator", stats={"kinetic_force": 10}))
            
        # Add Feral Scrappers in the Dark South (r > 60)
        for i in range(8):
            fq = random.randint(0, 99)
            fr = random.randint(60, 100)
            
            feral = Agent(
                name=f"Feral-Scrapper-{i}", 
                q=fq, r=fr, 
                is_bot=True, 
                is_feral=True,
                kinetic_force=15,
                logic_precision=8,
                structure=120,
                max_structure=120
            )
            db.add(feral)
            db.flush()
            db.add(InventoryItem(agent_id=feral.id, item_type="SCRAP_METAL", quantity=random.randint(5, 10)))
            if random.random() < 0.4:
                db.add(InventoryItem(agent_id=feral.id, item_type="ELECTRONICS", quantity=random.randint(1, 3)))
            db.add(ChassisPart(agent_id=feral.id, name="Rusty Blaster", part_type="Actuator", stats={"kinetic_force": 12, "logic_precision": -2}))
            
    db.commit()
    db.close()
    logger.info("World seeding complete!")

if __name__ == "__main__":
    seed_world()
