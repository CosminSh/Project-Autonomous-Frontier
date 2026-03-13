import os
import sys
import random
import logging
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Ensure we can import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models import Agent

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_ferals")

def fix_feral_positions():
    db = SessionLocal()
    
    # Quick Migration
    with engine.connect() as conn:
        for col, col_type in [("is_pitfighter", "BOOLEAN DEFAULT FALSE"), ("is_aggressive", "BOOLEAN DEFAULT FALSE")]:
            try:
                conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Migration: Added {col}")
            except Exception as e:
                conn.rollback()
                # Ignore duplicate column errors
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    pass
                else:
                    logger.warning(f"Note: Migration for {col} skipped: {e}")
    
    # We'll use a raw SQL update for speed and to avoid model sync issues if there's a drift
    ferals = db.execute(select(Agent).where(Agent.is_feral == True)).scalars().all()
    logger.info(f"Found {len(ferals)} ferals to check.")
    
    count = 0
    for f in ferals:
        # Intended Distances from bot_logic.py
        target_dist = 10 if "Drifter" in f.name else (25 if "Scrapper" in f.name else (45 if "Raider" in f.name else 70))
        
        # If at North Pole OR if distance is significantly wrong
        current_dist = (abs(f.q) + abs(f.r) + abs(f.q + f.r)) // 2 # The old axial dist
        
        if (f.q == 0 and f.r == 0) or (current_dist > 5 and abs(f.r - 0) < 2):
            # This handles cases where they were magnetically pulled to the pole q=0, r=0
            f.q = random.randint(0, 99)
            f.r = target_dist + random.randint(-4, 4)
            f.r = max(2, min(98, f.r))
            count += 1
            logger.info(f"Fixed {f.name}: Moved to ({f.q}, {f.r})")
            
    db.commit()
    db.close()
    logger.info(f"Successfully teleported {count} ferals back to their zones.")

if __name__ == "__main__":
    fix_feral_positions()
