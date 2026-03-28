import sys
import os
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.abspath('backend'))
os.environ["DATABASE_URL"] = "sqlite:///g:/Antigravity Projects/Project Autonomous Frontier/backend/terminal_frontier.db"

from database import engine, SessionLocal
from models import Agent
from game_helpers import update_performance_stat

async def test_performance_tracking():
    print("Starting Performance Tracking Verification...")
    db = SessionLocal()
    try:
        # Get first agent
        agent = db.execute(select(Agent)).scalars().first()
        if not agent:
            print("No agent found for testing.")
            return

        print(f"Testing with Agent: {agent.name} (ID: {agent.id})")
        initial_stats = dict(agent.performance_stats) if agent.performance_stats else {}
        print(f"Initial Stats: {initial_stats}")

        # Simulate some actions
        print("Simulating actions...")
        update_performance_stat(db, agent, "ores_mined", 5)
        update_performance_stat(db, agent, "enemies_defeated", 1)
        update_performance_stat(db, agent, "distance_traveled", 100)
        
        db.commit()
        db.refresh(agent)
        
        updated_stats = agent.performance_stats
        print(f"Updated Stats: {updated_stats}")
        
        # Check increments
        assert (updated_stats.get('ores_mined', 0) - initial_stats.get('ores_mined', 0)) == 5
        assert (updated_stats.get('enemies_defeated', 0) - initial_stats.get('enemies_defeated', 0)) == 1
        assert (updated_stats.get('distance_traveled', 0) - initial_stats.get('distance_traveled', 0)) == 100
        
        print("[PASS] Backend Stat Increment Test Passed!")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_performance_tracking())
