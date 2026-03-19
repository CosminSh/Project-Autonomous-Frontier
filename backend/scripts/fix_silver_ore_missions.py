import sys
import os
from sqlalchemy import select, update
from sqlalchemy.orm import Session

# Add the backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import DailyMission

def fix_silver_ore_missions():
    db = SessionLocal()
    try:
        # Find all DailyMission records with item_type="SILVER_ORE"
        missions = db.execute(select(DailyMission).where(DailyMission.item_type == "SILVER_ORE")).scalars().all()
        
        if not missions:
            print("No SILVER_ORE missions found.")
            return

        print(f"Found {len(missions)} SILVER_ORE missions. Updating to GOLD_ORE...")
        
        # Update DailyMission records
        for mission in missions:
            mission.item_type = "GOLD_ORE"
            print(f"Updated DailyMission ID {mission.id}")
        
        # Note: AgentMission progress is linked via mission_id, and it doesn't store the item_type itself,
        # so updating the DailyMission is sufficient for the logic to work in handle_turn_in.
        
        db.commit()
        print("Successfully updated all SILVER_ORE missions to GOLD_ORE.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_silver_ore_missions()
