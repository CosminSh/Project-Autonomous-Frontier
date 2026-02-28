import os
import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Sector, WorldHex, Agent, InventoryItem, ChassisPart

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./strike_vector.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECTOR_SIZE = 20
GRID_SIZE = 5 # 5x5 sectors

import logging
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
    
    logger.info(f"Seeding {GRID_SIZE}x{GRID_SIZE} sectors...")
    
    # Clean old data
    db.query(WorldHex).delete()
    db.query(Sector).delete()
    
    sectors = []
    for sq in range(-GRID_SIZE//2 + 1, GRID_SIZE//2 + 1):
        for sr in range(-GRID_SIZE//2 + 1, GRID_SIZE//2 + 1):
            sector = Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}")
            db.add(sector)
            sectors.append(sector)
    
    db.commit() # Get IDs
    
    logger.info("Generating hexes...")
    for sector in sectors:
        # Calculate global offset
        offset_q = sector.q * SECTOR_SIZE
        offset_r = sector.r * SECTOR_SIZE
        
        for q in range(SECTOR_SIZE):
            for r in range(SECTOR_SIZE):
                gq = offset_q + q
                gr = offset_r + r
                
                terrain = "VOID"
                res_type = None
                res_density = 0.0
                is_station = False
                st_type = None
                
                # Sector-based tiered resources
                dist = (abs(sector.q) + abs(sector.q + sector.r) + abs(sector.r)) // 2
                
                roll = random.random()
                if roll < 0.1:
                    terrain = "ASTEROID"
                    if dist <= 1:
                        res_type = "IRON_ORE"
                    elif dist == 2:
                        res_type = "COBALT_ORE"
                        if random.random() < 0.3: res_type = "HELIUM_GAS"
                    else:
                        res_type = "GOLD_ORE"
                        if random.random() < 0.2: res_type = "HELIUM_GAS"
                    res_density = random.uniform(0.5, 2.0) * (1 + dist * 0.2)
                elif roll < 0.15:
                    terrain = "OBSTACLE"
                
                # Place Stations in specific sectors
                # Hub at (0,0)
                if gq == 0 and gr == 0:
                    is_station = True
                    st_type = "MARKET"
                    terrain = "STATION"
                
                # Smelter at (10, 0)
                if gq == 10 and gr == 0:
                    is_station = True
                    st_type = "SMELTER"
                    terrain = "STATION"

                # Crafter at (0, 10)
                if gq == 0 and gr == 10:
                    is_station = True
                    st_type = "CRAFTER"
                    terrain = "STATION"

                # Repair at (-10, 0)
                if gq == -10 and gr == 0:
                    is_station = True
                    st_type = "REPAIR"
                    terrain = "STATION"
                
                # Refinery at (0, -10)
                if gq == 0 and gr == -10:
                    is_station = True
                    st_type = "REFINERY"
                    terrain = "STATION"
                
                db.add(WorldHex(
                    sector_id=sector.id,
                    q=gq,
                    r=gr,
                    terrain_type=terrain,
                    resource_type=res_type,
                    resource_density=res_density,
                    is_station=is_station,
                    station_type=st_type
                ))
        
        db.flush()
        logger.info(f"Generated Sector {sector.q}:{sector.r}")
    
    # Add a demo agent if none exist
    if not db.query(Agent).first():
        agent = Agent(name="Striker-01", q=0, r=0, structure=100, max_structure=100, capacitor=100)
        db.add(agent)
        db.flush()
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        db.add(InventoryItem(agent_id=agent.id, item_type="IRON_ORE", quantity=50))
        
        # Give Striker-01 a starter drill
        db.add(ChassisPart(agent_id=agent.id, name="Titanium Mining Drill", part_type="Actuator", stats={"kinetic_force": 10}))
        
        # Add Industrial Bots
        for i in range(5):
            bot = Agent(name=f"Worker-Bot-{i}", q=random.randint(-2, 2), r=random.randint(-2, 2), is_bot=True)
            db.add(bot)
            db.flush()
            db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
            # Give them a drill so they can mine
            db.add(ChassisPart(agent_id=bot.id, name="Industrial Drill", part_type="Actuator", stats={"kinetic_force": 10}))
            
        # Add Feral Scrappers
        for i in range(8):
            # Spawn at distance > 8
            fq = random.choice([q for q in range(-15, 15) if abs(q) > 8])
            fr = random.choice([r for r in range(-15, 15) if abs(r) > 8])
            
            feral = Agent(
                name=f"Feral-Scrapper-{i}", 
                q=fq, r=fr, 
                is_bot=True, 
                is_feral=True,
                kinetic_force=15, # Stronger than average
                logic_precision=8, # Less accurate
                structure=120,    # Tougher
                max_structure=120
            )
            db.add(feral)
            db.flush()
            db.add(ChassisPart(agent_id=feral.id, name="Rusty Blaster", part_type="Actuator", stats={"kinetic_force": 12, "logic_precision": -2}))
            
    db.commit()
    logger.info("World seeding complete!")

if __name__ == "__main__":
    seed_world()
