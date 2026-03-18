import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from database import SessionLocal, engine
    from logic.leaderboard_manager import generate_leaderboards, LEADERBOARD_CACHE
    from models import Agent
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_leaderboards():
    print("Testing leaderboard generation...")
    
    with SessionLocal() as db:
        # Check if we have agents
        count = db.query(Agent).count()
        print(f"Found {count} agents in local DB.")
        
        generate_leaderboards(db)
        
        print("\nLeaderboard Cache Categories:")
        for cat in LEADERBOARD_CACHE["categories"]:
            items = LEADERBOARD_CACHE["categories"][cat]
            print(f"- {cat}: {len(items)} items")
            if items:
                # Show top 3
                for i, item in enumerate(items[:3]):
                    print(f"  [{i+1}] {item['name']}: {item['value']}")

if __name__ == "__main__":
    test_leaderboards()
