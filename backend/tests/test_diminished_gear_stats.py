import requests
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Add parent directory to path to find models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Agent, ChassisPart

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

BASE_URL = "http://localhost:8002"
API_KEY = f"GEAR_TEST_{uuid.uuid4().hex[:8]}"
headers = {"X-API-Key": API_KEY}

def get_my_agent():
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching agent: {resp.text}")
        return None
    return resp.json()

def test_diminished_gear_stats():
    print("--- STARTING DIMINISHED GEAR STATS VERIFICATION ---")
    
    # 1. Setup Test Agent
    with SessionLocal() as db:
        # Clean up any existing test agent with this key
        db.query(Agent).filter(Agent.api_key == API_KEY).delete()
        db.commit()
        
        agent = Agent(
            name=f"GearTester_{uuid.uuid4().hex[:4]}",
            api_key=API_KEY,
            owner="test",
            q=0, r=0,
            health=100, max_health=100,
            energy=100,
            wear_and_tear=0.0,
            faction_id=1
        )
        db.add(agent)
        db.flush()
        agent_id = agent.id
        
        # Add a high-stat part: Mining Yield +50
        part = ChassisPart(
            agent_id=agent_id, 
            part_type="Actuator", 
            name="Mega Drill", 
            stats={"mining_yield": 50},
            rarity="STANDARD"
        )
        db.add(part)
        db.commit()
        print(f"Created Test Agent ID {agent_id} with 'Mega Drill' (+50 Mining Yield)")

    # 2. Check at 0% Wear
    print("\n[CASE 1] Checking Stats at 0% Wear")
    p = get_my_agent()
    if not p: return

    total_yield = p['mining_yield']
    part_yield = p['parts'][0]['stats']['mining_yield']
    
    print(f"  Total Mining Yield: {total_yield} (Expected ~60: 10 base + 50 gear)")
    print(f"  Part Mining Yield:  {part_yield} (Expected 50)")
    
    if total_yield >= 55 and part_yield == 50:
        print("  SUCCESS: Stats are correct at 0% wear.")
    else:
        print("  FAILED: Stats incorrect at 0% wear.")
        sys.exit(1)

    # 3. Check at 50% Wear (Penalty factor: 1.0 - 0.5 * 0.9 = 0.55)
    print("\n[CASE 2] Checking Stats at 50% Wear (Penalty: 0.55x)")
    with SessionLocal() as db:
        agent = db.get(Agent, agent_id)
        agent.wear_and_tear = 50.0
        db.commit()
        
    p = get_my_agent()
    total_yield = p['mining_yield']
    part_yield = p['parts'][0]['stats']['mining_yield']
    
    expected_total = int(60 * 0.55) # 33
    expected_part = int(50 * 0.55)  # 27
    
    print(f"  Total Mining Yield: {total_yield} (Expected ~{expected_total})")
    print(f"  Part Mining Yield:  {part_yield} (Expected {expected_part})")
    
    # Allow +/- 3 for base stat variations or rounding
    if abs(total_yield - expected_total) <= 3 and abs(part_yield - expected_part) <= 2:
        print("  SUCCESS: Stats diminished correctly at 50% wear.")
    else:
        print("  FAILED: Stats incorrect at 50% wear.")
        sys.exit(1)

    # 4. Check at 100% Wear (Penalty factor: 0.10)
    print("\n[CASE 3] Checking Stats at 100% Wear (Penalty: 0.10x)")
    with SessionLocal() as db:
        agent = db.get(Agent, agent_id)
        agent.wear_and_tear = 100.0
        db.commit()
        
    p = get_my_agent()
    total_yield = p['mining_yield']
    part_yield = p['parts'][0]['stats']['mining_yield']
    
    expected_total = int(60 * 0.10) # 6
    expected_part = int(50 * 0.10)  # 5
    
    print(f"  Total Mining Yield: {total_yield} (Expected ~{expected_total})")
    print(f"  Part Mining Yield:  {part_yield} (Expected {expected_part})")
    
    if abs(total_yield - expected_total) <= 2 and abs(part_yield - expected_part) <= 1:
        print("  SUCCESS: Stats diminished correctly at 100% wear.")
    else:
        print("  FAILED: Stats incorrect at 100% wear.")
        sys.exit(1)

    print("\n--- ALL DIMINISHED GEAR STATS TESTS PASSED ---")

if __name__ == "__main__":
    test_diminished_gear_stats()
