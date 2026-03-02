import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
WAIT_TIME = 25 

DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def test_progression():
    print("--- STARTING PROGRESSION VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as guest...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/guest")
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to connect! Is the server running? {e}")
        return
        
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (Agent ID: {agent_id})")

    # 2. Check initial perception
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    perception = resp.json()
    agent_stats = perception['content']['agent_status']
    print(f"Initial Level: {agent_stats.get('level')}, XP: {agent_stats.get('experience')}")
    
    assert agent_stats.get('level') == 1, "Expected Level 1"
    assert agent_stats.get('experience') == 0, "Expected 0 XP"

    # Give agent a basic drill so mining works
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO chassis_parts (agent_id, part_type, name) VALUES (:id, 'Actuator', 'Basic Mining Drill')"), {"id": agent_id})
        conn.commit()

    # Move agent to an asteroid hex (q=1, r=1) so MINE works
    print("\nSetting Agent XP to 95 and placing on Asteroid via SQL...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE world_hexes SET terrain_type = 'ASTEROID', resource_type = 'IRON_ORE', resource_density = 2.0 WHERE q = 1 AND r = 1"))
        conn.execute(text("UPDATE agents SET experience = 95, capacitor = 100, q = 1, r = 1 WHERE id = :id"), {"id": agent_id})
        conn.commit()

    # Submit MINE intent
    print(f"\nSubmitting MINE intent...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "MINE",
        "data": {}
    }, headers=headers)

    print(f"Waiting {WAIT_TIME}s for Phase Cycle (Crunch)...")
    time.sleep(WAIT_TIME)

    # Verify Results
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    my_agent = resp.json()
    
    level = my_agent.get('level')
    xp = my_agent.get('experience')
    
    print(f"Post-Crunch Level: {level}, XP: {xp}")
    
    if level == 2:
        print("SUCCESS: Level up worked!")
    else:
        print(f"FAILED: Expected Level 2, got {level}")
        
    resp_logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp_logs.json()
    levelup_log = next((l for l in logs if l['event'] == 'LEVEL_UP'), None)
    
    if levelup_log:
        print(f"VERIFIED: LEVEL_UP audit log found! Details: {levelup_log['details']}")
    else:
        print("FAILED: No LEVEL_UP log found.")

if __name__ == "__main__":
    test_progression()
