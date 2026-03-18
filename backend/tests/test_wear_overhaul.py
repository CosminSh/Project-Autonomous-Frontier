import requests
import time
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to find models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Agent, ChassisPart, WorldHex, Intent, AuditLog, InventoryItem

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

BASE_URL = "http://localhost:8000"
import uuid
API_KEY = f"WEAR_TEST_{uuid.uuid4().hex[:8]}"
headers = {"X-API-Key": API_KEY}

def get_my_agent():
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    return resp.json()

def wait_for_tick(current_tick, count=1):
    target = current_tick + count
    print(f"Waiting for tick {target}...")
    while True:
        resp = requests.get(f"{BASE_URL}/api/global_stats")
        tick = resp.json().get('tick', 0)
        if tick >= target:
            return tick
        time.sleep(1)

def test_wear_overhaul():
    print("--- STARTING WEAR OVERHAUL VERIFICATION ---")
    
    # 1. Setup Test Agent
    with SessionLocal() as db:
        db.query(Intent).delete() # TOTAL CLEAN SLATE
        db.query(Agent).filter(Agent.api_key == API_KEY).delete()
        db.query(AuditLog).delete() # Simple clear for development environment
        db.commit()
        
        # ... remainder of setup ...
        
        agent = Agent(
            name=f"WearTester_{uuid.uuid4().hex[:4]}",
            api_key=API_KEY,
            owner="test",
            q=0, r=0,
            health=100, max_health=100,
            energy=100,
            wear_and_tear=0.0,
            damage=100,
            mining_yield=100,
            accuracy=100,
            speed=100,
            armor=100,
            faction_id=1
        )
        db.add(agent)
        db.flush() # Get ID
        agent_id = agent.id
        print(f"Created Test Agent ID: {agent_id}")
        
        # Add a drill to allow mining
        drill = ChassisPart(agent_id=agent_id, part_type="Actuator", name="Basic Iron Drill", stats={"mining_yield": 10})
        db.add(drill)
        
        # Ensure target hex has resources
        hex_at_1_0 = db.query(WorldHex).filter(WorldHex.q == 1, WorldHex.r == 0).first()
        if not hex_at_1_0:
            hex_at_1_0 = WorldHex(q=1, r=0, terrain_type="ASTEROID", resource_type="IRON_ORE", resource_density=1.0, resource_quantity=1000)
            db.add(hex_at_1_0)
        else:
            hex_at_1_0.terrain_type = "ASTEROID"
            hex_at_1_0.resource_type = "IRON_ORE"
            hex_at_1_0.resource_quantity = 1000
            
        db.commit()

    # Get initial status
    resp = requests.get(f"{BASE_URL}/api/global_stats")
    p = get_my_agent()
    print(f"Initial Status: Wear={p['wear_and_tear']}, Energy={p['energy']}, Pos=({p['q']},{p['r']})")
    start_tick = resp.json()['tick']
    
    # CASE 1: Idle Check
    print("\n[CASE 1] Checking Idle Wear (should be 0)")
    wait_for_tick(start_tick, 2)
    p = get_my_agent()
    wear = p['wear_and_tear']
    if wear == 0.0:
        print("SUCCESS: Wear did not increase while idling.")
    else:
        print(f"FAILED: Wear increased to {wear} while idling.")
        sys.exit(1)

    # CASE 2: Movement Check
    print("\n[CASE 2] Checking Movement Wear (+0.05)")
    resp = requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MOVE", "data": {"target_q": 1, "target_r": 0}}, headers=headers)
    move_tick = resp.json()['tick']
    p = get_my_agent()
    # Manual DB Check
    with SessionLocal() as db:
        count = db.query(Intent).filter(Intent.agent_id == agent_id).count()
        print(f"  [DEBUG] Intents for 999 in DB: {count}")
        all_intents = db.query(Intent).all()
        print(f"  [DEBUG] Total intents in DB: {len(all_intents)}")
        for i in all_intents:
            print(f"    Intent: Agent={i.agent_id}, Type={i.action_type}, Tick={i.tick_index}")

    # Wait for the next tick to ensure CRUNCH phase is complete
    print(f"  Intent submitted for tick {move_tick}. Waiting for execution...")
    wait_for_tick(move_tick, 1)
    
    p = get_my_agent()
    # Wait up to 5 more ticks if not moved yet (handling concurrency/lag)
    for i in range(5):
        if p['q'] == 1: break
        print(f"  [{i}] Still at ({p['q']},{p['r']})... waiting...")
        wait_for_tick(p.get('tick', move_tick), 1)
        p = get_my_agent()

    wear = p['wear_and_tear']
    print(f"Post-Move Status: Wear={wear}, Energy={p['energy']}, Pos=({p['q']},{p['r']})")
    if 0.04 <= wear <= 0.06:
        print(f"SUCCESS: Wear increased to {wear} after move.")
    else:
        # Check audit logs for failure
        with SessionLocal() as db:
            logs = db.query(AuditLog).filter(AuditLog.agent_id == p['id']).order_by(AuditLog.id.desc()).limit(10).all()
            print("  Recent Audit Logs:")
            for l in logs:
                print(f"    {l.event_type} - {l.details}")
        print(f"FAILED: Wear is {wear} after move, expected ~0.05.")
        sys.exit(1)

    # CASE 3: Mining Check
    print("\n[CASE 3] Checking Mining Wear (+0.10)")
    # Reset wear for clean check
    with SessionLocal() as db:
        agent = db.get(Agent, agent_id)
        agent.wear_and_tear = 0.0
        db.commit()
        
    resp = requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MINE", "data": {}}, headers=headers)
    mine_tick = resp.json()['tick']
    wait_for_tick(mine_tick, 1)
    
    p = get_my_agent()
    wear = p['wear_and_tear']
    if 0.09 <= wear <= 0.11:
        print(f"SUCCESS: Wear increased to {wear} after mining tick.")
    else:
        print(f"FAILED: Wear is {wear} after mining, expected ~0.10.")
        sys.exit(1)

    # CASE 4: Stat Degradation Check
    print("\n[CASE 4] Checking Stat Degradation (100% wear = 10% stats)")
    with SessionLocal() as db:
        agent = db.get(Agent, agent_id)
        agent.wear_and_tear = 100.0
        db.commit()
    
    # Trigger a poll to force recalculate
    p = get_my_agent()
    
    # Base was 100 for all stats. Penalty factor should be 0.1
    # Expected stats: 10 (approx)
    stats = p
    success = True
    for s_name in ['damage', 'accuracy', 'speed', 'armor', 'mining_yield']:
        val = stats[s_name]
        # Allow some room for base stats + gear bonuses
        if val > 20: # 10% of ~110-120 should be around 11-12. If it's > 20, penalty failed.
            print(f"FAILED: Stat {s_name} is too high: {val} at 100% wear.")
            success = False
        else:
            print(f"Stat {s_name}: {val} (Verified)")
            
    if success:
        print("SUCCESS: Stats correctly degraded at 100% wear.")
    else:
        sys.exit(1)

    # CASE 5: Cap Check
    print("\n[CASE 5] Checking Wear Cap (100%)")
    with SessionLocal() as db:
        agent = db.get(Agent, 999)
        agent.wear_and_tear = 150.0 # Set above cap
        db.commit()
        
    p = get_my_agent()
    wear = p['wear_and_tear']
    if wear == 100.0:
        print("SUCCESS: Wear capped at 100.0%.")
    else:
        print(f"FAILED: Wear is {wear}, expected 100.0.")
        sys.exit(1)

    print("\n--- ALL WEAR OVERHAUL TESTS PASSED ---")

if __name__ == "__main__":
    test_wear_overhaul()
