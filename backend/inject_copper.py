from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import WorldHex
import random

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def inject_copper():
    db = SessionLocal()
    # Find some VOID hexes at distance 2 to turn into Copper
    # In our world, Sector distance 2 starts at q=20, r=20 or similar.
    # Let's just look for VOID hexes generally.
    hexes = db.query(WorldHex).filter(WorldHex.terrain_type == "VOID").all()
    
    count = 0
    random.shuffle(hexes) # Randomize which VOID ones we pick
    
    for h in hexes:
        # Distance calculation based on axial q,r
        dist = (abs(h.q) + abs(h.q + h.r) + abs(h.r)) // 2
        
        # We want to place copper in a ring around the starting area (distance 15-25)
        if 15 <= dist <= 25 and not h.resource_type:
            h.terrain_type = "ASTEROID"
            h.resource_type = "COPPER_ORE"
            h.resource_density = random.uniform(1.0, 3.0)
            count += 1
            if count >= 30: break
            
    db.commit()
    print(f"Injected {count} Copper Ore nodes at distance 2!")
    db.close()

if __name__ == "__main__":
    inject_copper()
