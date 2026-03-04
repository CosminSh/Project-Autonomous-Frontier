import os
import time
import subprocess
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import random
import re

# Add backend to path so we can import models
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from models import Base, Agent, WorldHex, ChassisPart, InventoryItem, Sector

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

    print("Generating hex resources...")
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
                    terrain = "ASTEROID"
                    dist = (abs(sector.q) + abs(sector.q + sector.r) + abs(sector.r)) // 2
                    if dist <= 1: res_type = "IRON_ORE"
                    elif dist == 2: res_type = "COBALT_ORE"
                    else: res_type = "GOLD_ORE"
                    res_density = random.uniform(0.5, 2.0) * (1 + dist * 0.2)
                elif roll < 0.15: terrain = "OBSTACLE"
                
                if gq == 0 and gr == 0: terrain, is_station, st_type = "STATION", True, "STATION_HUB"
                if gq == 10 and gr == 0: terrain, is_station, st_type = "STATION", True, "SMELTER"
                if gq == 0 and gr == 10: terrain, is_station, st_type = "STATION", True, "CRAFTER"
                if gq == -10 and gr == 0: terrain, is_station, st_type = "STATION", True, "REPAIR"

                db.add(WorldHex(sector_id=sector.id, q=gq, r=gr, terrain_type=terrain, resource_type=res_type, resource_density=res_density, is_station=is_station, station_type=st_type))
    
    # Add Agents
    a1 = Agent(id=1, name="Striker-01", q=0, r=0, structure=100, max_structure=100, capacitor=100)
    db.add(a1)
    db.flush()
    db.add(InventoryItem(agent_id=1, item_type="CREDITS", quantity=1000))
    db.add(InventoryItem(agent_id=1, item_type="IRON_ORE", quantity=50))
    
    # Add Industrial Bots
    for i in range(5):
        bot = Agent(name=f"Worker-Bot-{i}", q=random.randint(-2, 2), r=random.randint(-2, 2), is_bot=True)
        db.add(bot)
        db.flush()
        db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
    
    # Add Feral Scrappers
    for i in range(8):
        fq = random.choice([q for q in range(-15, 15) if abs(q) > 8])
        fr = random.choice([r for r in range(-15, 15) if abs(r) > 8])
        feral = Agent(name=f"Feral-Scrapper-{i}", q=fq, r=fr, is_bot=True, is_feral=True, kinetic_force=15, logic_precision=8, structure=120, max_structure=120)
        db.add(feral)
        db.flush()
        db.add(ChassisPart(agent_id=feral.id, name="Rusty Blaster", part_type="Actuator", stats={"damage": 12}))
            
    db.commit()

print("Starting uvicorn server...")
env = os.environ.copy()
env["PYTHONPATH"] = os.path.join(os.getcwd(), "backend")
env["DATABASE_URL"] = f"sqlite:///{os.path.join(os.getcwd(), 'demo.db')}"
# Run backend.main from project root
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8001"], env=env)

print("\n--- DEMO READY ---")
print("1. IMPORTANT: Add http://localhost:8001 to your Google Cloud Console Origins (if using Google Auth)!")
print("2. Open: http://localhost:8001")
print("3. Press CTRL+C to stop.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping demo...")
    proc.terminate()
    print("Cleanup complete.")
