import os
import time
import subprocess
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import random

# Add backend to path so we can import models
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from models import Base, Agent, WorldHex, ChassisPart, InventoryItem, Sector

# 1. Modify main.py to use SQLite temporarily
print("Adjusting main.py for demo mode...")
main_path = os.path.join(os.getcwd(), "backend", "main.py")
demo_main_path = os.path.join(os.getcwd(), "backend", "main_demo.py")

with open(main_path, "r") as f:
    content = f.read()

# Replace DB URL with SQLite
lite_content = content.replace(
    'DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/strike_vector")',
    'DATABASE_URL = "sqlite:///../demo.db"'
)

with open(demo_main_path, "w") as f:
    f.write(lite_content)

# 2. Setup SQLite DB and Seed Data
print("Seeding demo database...")
db_path = os.path.join(os.getcwd(), "demo.db")
engine = create_engine(f"sqlite:///{db_path}")
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

with SessionLocal() as db:
    # Use the logic from seed_world.py but for the demo DB
    SECTOR_SIZE = 20
    GRID_SIZE = 5

    sectors = []
    for sq in range(-GRID_SIZE//2 + 1, GRID_SIZE//2 + 1):
        for sr in range(-GRID_SIZE//2 + 1, GRID_SIZE//2 + 1):
            sector = Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}")
            db.add(sector)
            sectors.append(sector)
    db.commit()

    print("Generating 10,000 hexes...")
    for sector in sectors:
        offset_q = sector.q * SECTOR_SIZE
        offset_r = sector.r * SECTOR_SIZE
        for q in range(SECTOR_SIZE):
            for r in range(SECTOR_SIZE):
                gq = offset_q + q
                gr = offset_r + r
                terrain, res_type, res_density, is_station, st_type = "VOID", None, 0.0, False, None
                
                roll = random.random()
                if roll < 0.1:
                    terrain, res_type, res_density = "ASTEROID", "ORE", random.uniform(0.5, 2.0)
                elif roll < 0.15: terrain = "OBSTACLE"
                
                if gq == 0 and gr == 0: terrain, is_station, st_type = "STATION", True, "MARKET"
                if gq == 10 and gr == 0: terrain, is_station, st_type = "STATION", True, "SMELTER"
                if gq == 0 and gr == 10: terrain, is_station, st_type = "STATION", True, "CRAFTER"

                db.add(WorldHex(sector_id=sector.id, q=gq, r=gr, terrain_type=terrain, resource_type=res_type, resource_density=res_density, is_station=is_station, station_type=st_type))
    
    # Add Agents
    a1 = Agent(id=1, name="Striker-01", q=0, r=0, structure=100, max_structure=100, capacitor=100)
    db.add(a1)
    db.flush()
    db.add(InventoryItem(agent_id=1, item_type="CREDITS", quantity=1000))
    db.add(InventoryItem(agent_id=1, item_type="ORE", quantity=50))
    db.commit()

print("Starting backend server...")
# Start uvicorn in a separate process
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main_demo:app", "--host", "127.0.0.1", "--port", "8001"], cwd="backend")

print("\n--- DEMO READY ---")
print("1. Open your browser and go to: http://localhost:8001")
print("2. You should see the 3D map and unit stats.")
print("3. Press CTRL+C in this terminal when you want to stop the demo.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping demo...")
    proc.terminate()
    if os.path.exists(demo_main_path):
        os.remove(demo_main_path)
    if os.path.exists(db_path):
        os.remove(db_path)
    print("Cleanup complete.")
