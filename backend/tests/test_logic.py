from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
import time
import sys
import os

# Add parent directory to path to find models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Agent, ChassisPart, WorldHex, AuctionOrder, Intent, AuditLog, InventoryItem, Bounty, DailyMission

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

BASE_URL = "http://localhost:8000"
headers = {"X-API-Key": "TEST_API_KEY"}

def get_current_tick():
    resp = requests.get(f"{BASE_URL}/api/global_stats")
    if resp.status_code != 200:
        print(f"[DEBUG] Global Stats error {resp.status_code}: {resp.text}")
        return 0, "UNKNOWN"
    data = resp.json()
    if 'tick' not in data:
        print(f"[DEBUG] Global Stats response missing tick: {data}")
    return data.get('tick', 0), data.get('phase', "UNKNOWN")

def wait_for_tick(target_tick, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        tick, phase = get_current_tick()
        print(f"Polling Tick: {tick}, Phase: {phase} (Target: {target_tick})")
        if tick >= target_tick and phase == "PERCEPTION":
            return tick
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for tick {target_tick}")

def verify():
    # 1. Seed Data
    with SessionLocal() as db:
        print("Seeding test data...")
        db.query(Intent).delete()
        db.query(ChassisPart).delete()
        db.query(AuditLog).delete()
        db.query(InventoryItem).delete()
        db.query(Agent).delete()
        db.query(WorldHex).delete()
        db.query(AuctionOrder).delete()
        db.query(Bounty).delete()
        db.query(DailyMission).delete()
        db.commit()
        agent = Agent(id=1, owner="tester", name="Unit-01", q=0, r=0, damage=20, api_key="TEST_API_KEY", health=100, max_health=100, energy=100)
        db.add(agent)
        drill = ChassisPart(agent_id=1, part_type="Actuator", name="Basic Iron Drill", stats={"bonus_str": 5})
        db.add(drill)
        gold_node = WorldHex(q=1, r=0, terrain_type="PERIMETER", resource_type="IRON_ORE", resource_density=1.5)
        db.add(gold_node)
        db.commit()

    # Get start tick
    start_tick, _ = get_current_tick()
    print(f"Starting at Tick: {start_tick}")

    # 2. Test Movement Intent
    print("Testing MOVE intent...")
    resp = requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MOVE", "data": {"target_q": 1, "target_r": 0}}, headers=headers)
    print(f"Submit Intent Response: {resp.json()}")
    target_tick = resp.json()['tick']

    print(f"Waiting for Tick {target_tick} to finalize...")
    wait_for_tick(target_tick + 1) # Wait for tick where results are visible

    # 3. Verify Movement & Energy
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    perception = resp.json()
    print(f"Perception Packet: {perception}")
    
    status = perception['self']
    q, r = status['q'], status['r']
    energy = status['energy']
    
    if q == 1 and r == 0:
        print(f"[SUCCESS] Movement Successful! Current Energy: {energy}")
    else:
        print(f"[FAIL] Movement Failed! Agent is at ({q}, {r})")

    # 4. Test Mining Intent
    print("\nTesting MINE intent...")
    resp = requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MINE", "data": {}}, headers=headers)
    target_tick = resp.json()['tick']
    
    print(f"Waiting for Tick {target_tick} to finalize...")
    wait_for_tick(target_tick + 1)

    # 5. Check Audit Logs
    with SessionLocal() as db:
        agent = db.get(Agent, 1)
        logs = db.query(AuditLog).all()
        if any(log.event_type == "MINING" for log in logs):
            print(f"[SUCCESS] Mining Successful! Current Energy: {agent.energy}")
            for log in logs:
                if log.event_type == "MINING":
                    print(f"Log: {log.event_type} - {log.details}")
        else:
            print("[FAIL] Mining Success log not found.")
            print("All Logs in DB:")
            for log in logs:
                print(f"  {log.event_type}: {log.details}")

if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        print(f"[CRITICAL ERROR] {e}")
        sys.exit(1)
