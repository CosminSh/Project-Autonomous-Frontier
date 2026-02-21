import os
import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Sector, WorldHex, Agent, InventoryItem

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./strike_vector.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECTOR_SIZE = 20
GRID_SIZE = 5 # 5x5 sectors

def seed_world():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    
    print(f"Seeding {GRID_SIZE}x{GRID_SIZE} sectors...")
    
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
    
    print("Generating hexes...")
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
                
                # Random terrain/resources
                roll = random.random()
                if roll < 0.1:
                    terrain = "ASTEROID"
                    res_type = "ORE"
                    res_density = random.uniform(0.5, 2.0)
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
        print(f"Generated Sector {sector.q}:{sector.r}")
    
    # Add a demo agent if none exist
    if not db.query(Agent).first():
        agent = Agent(name="Striker-01", q=0, r=0, structure=100, max_structure=100, capacitor=100)
        db.add(agent)
        db.flush()
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        db.add(InventoryItem(agent_id=agent.id, item_type="ORE", quantity=50))
    
    db.commit()
    print("World seeding complete!")

if __name__ == "__main__":
    seed_world()
