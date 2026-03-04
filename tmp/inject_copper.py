from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import WorldHex
import random

DATABASE_URL = "sqlite:///./terminal_frontier.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def inject_copper():
    db = SessionLocal()
    # Find some VOID hexes at distance 2 to turn into Copper
    hexes = db.query(WorldHex).filter(WorldHex.terrain_type == "VOID").all()
    
    count = 0
    for h in hexes:
        # Distance calculation
        dist = (abs(h.q // 20) + abs((h.q // 20) + (h.r // 20)) + abs(h.r // 20)) // 2
        if dist == 2 and random.random() < 0.2:
            h.terrain_type = "ASTEROID"
            h.resource_type = "COPPER_ORE"
            h.resource_density = random.uniform(1.0, 3.0)
            count += 1
            if count >= 20: break
            
    db.commit()
    print(f"Injected {count} Copper Ore nodes at distance 2!")
    db.close()

if __name__ == "__main__":
    inject_copper()
