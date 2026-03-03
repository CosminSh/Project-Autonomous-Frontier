import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
WAIT_TIME = 25 # Ticks are ~20s total

# DB for manual checks if needed
DB_PATH = "sqlite:///demo.db"
engine = create_engine(DB_PATH)

def test_milestone1():
    print("--- STARTING MILESTONE 1 VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as guest...")
    resp = requests.post(f"{BASE_URL}/auth/guest")
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (Agent ID: {agent_id})")

    # 2. Verify Anarchy Zone Protection (Safe Zone)
    print("\nAdding target agent in SAFE ZONE (1, 0)...")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agents (name, q, r, owner, is_bot, is_feral, structure, max_structure, capacitor, 
                               kinetic_force, logic_precision, overclock, integrity) 
            VALUES ('Target-Safe', 1, 0, 'dummy', 0, 0, 100, 100, 100, 10, 10, 10, 5)
        """))
        conn.commit()
        target_id = conn.execute(text("SELECT id FROM agents WHERE name='Target-Safe'")).scalar()

    print(f"Attempting ATTACK on Agent {target_id} in Safe Zone...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "ATTACK",
        "data": {"target_id": target_id}
    }, headers=headers)

    print(f"Waiting 30s for tick...")
    time.sleep(30)

    resp_logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp_logs.json()
    attack_logs = [l for l in logs if l['event'] in ['COMBAT_HIT', 'COMBAT_MISS']]
    
    if not attack_logs:
        print("VERIFIED: Attack in Safe Zone was correctly IGNORED/BLOCKED.")
    else:
        print(f"FAILED: Found combat logs in Safe Zone: {attack_logs}")

    # 3. Verify Anarchy Zone Attack Success
    print("\nMoving player and target to ANARCHY ZONE (10, 0)...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q = 10, r = 0 WHERE id = :id"), {"id": agent_id})
        conn.execute(text("UPDATE agents SET q = 11, r = 0 WHERE id = :id"), {"id": target_id})
        conn.commit()

    # Verify teleport via API
    resp_me = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    me = resp_me.json()
    print(f"Confirmed Player at ({me['q']}, {me['r']})")

    if me['q'] != 10:
        print("CRITICAL: SQL Teleport failed or not seen yet. Waiting 10s...")
        time.sleep(10)

    print(f"Attempting ATTACK on Agent {target_id} in Anarchy Zone...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "ATTACK",
        "data": {"target_id": target_id}
    }, headers=headers)

    print(f"Waiting 30s for tick...")
    time.sleep(30)

    resp_logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp_logs.json()
    combat_log = next((l for l in logs if l['event'] in ['COMBAT_HIT', 'COMBAT_MISS']), None)
    
    if combat_log:
        print(f"VERIFIED: Attack in Anarchy Zone SUCCEEDED. Event: {combat_log['event']}")
    else:
        print("FAILED: Attack in Anarchy Zone did not produce logs.")

    # 4. Verify Heat Increase
    with engine.connect() as conn:
        heat = conn.execute(text("SELECT heat FROM agents WHERE id = :id"), {"id": agent_id}).scalar()
        print(f"Current Player Heat: {heat}")
        if heat > 0:
            print("VERIFIED: Heat increased after PvP action.")
        else:
            print("FAILED: Heat did not increase.")

    # 5. Verify Feral AI Aggro
    print("\nSpawning Feral Scrapper near player at (10, 1)...")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agents (name, q, r, is_bot, is_feral, structure, max_structure, capacitor, 
                               kinetic_force, logic_precision, overclock, integrity) 
            VALUES ('Feral-Test', 10, 1, 1, 1, 100, 100, 100, 15, 10, 5, 5)
        """))
        conn.commit()

    print("Waiting 60s for Feral AI to attack (2 ticks)...")
    time.sleep(60)

    resp_state = requests.get(f"{BASE_URL}/state")
    state = resp_state.json()
    combat_logs = [l for l in state['logs'] if 'COMBAT' in l['event']]
    print(f"Global Combat Logs: {combat_logs}")
    
    if combat_logs:
        print("VERIFIED: Feral AI interactions detected.")
    else:
        print("FAILED: No feral combat logs.")

if __name__ == "__main__":
    test_milestone1()

if __name__ == "__main__":
    test_milestone1()
