import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Agent
from logic.leaderboard_manager import generate_leaderboards, LEADERBOARD_CACHE

DATABASE_URL = "sqlite:///g:/Antigravity Projects/Project Autonomous Frontier/demo.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def verify_fixes():
    db = SessionLocal()
    try:
        # 1. Test Leaderboard Logic
        print("--- Verifying Leaderboard Filtering ---")
        generate_leaderboards(db)
        xp_leaders = LEADERBOARD_CACHE["categories"]["experience"]
        pitfighters_in_xp = [l for l in xp_leaders if "-PitFighter" in l["name"]]
        print(f"PitFighters in XP Leaderboard: {len(pitfighters_in_xp)}")
        
        credit_leaders = LEADERBOARD_CACHE["categories"]["credits"]
        pitfighters_in_credits = [l for l in credit_leaders if "-PitFighter" in l["name"]]
        print(f"PitFighters in Credits Leaderboard: {len(pitfighters_in_credits)}")

        # 2. Test Perception Logic (Simulated)
        print("\n--- Verifying Perception Filtering ---")
        # Find a normal agent and a pitfighter near (0,0)
        hub_agent = db.execute(select(Agent).where(Agent.name == "Striker-01")).scalar_one()
        pitfighter = db.execute(select(Agent).where(Agent.is_pitfighter == True)).first()
        
        if pitfighter:
            print(f"Found PitFighter: {pitfighter[0].name} (is_pitfighter={pitfighter[0].is_pitfighter})")
            
            # Using the same filter logic from perception.py
            visible_agents = db.execute(select(Agent).where(
                Agent.is_pitfighter.isnot(True)
            )).scalars().all()
            
            pitfighters_visible = [a for a in visible_agents if "-PitFighter" in a.name]
            print(f"PitFighters visible in filtered perception: {len(pitfighters_visible)}")
        else:
            print("No PitFighters found to test with.")

    finally:
        db.close()

if __name__ == "__main__":
    verify_fixes()
