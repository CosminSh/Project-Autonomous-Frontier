import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8001"
# Use a slightly larger wait to ensure we hit the next crunch
# Ticks are 5+10+5 = 20s
WAIT_TIME = 25 

DB_PATH = "sqlite:///demo.db"
engine = create_engine(DB_PATH)

def test_mass_mechanics():
    print("--- STARTING WEIGHT & MASS VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as guest...")
    resp = requests.post(f"{BASE_URL}/auth/guest")
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (Agent ID: {agent_id})")

    # 2. Check initial perception (Base Mass should be 0)
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    perception = resp.json()
    agent_stats = perception['content']['agent_status']
    print(f"Initial Mass: {agent_stats['mass']}, Capacity: {agent_stats['capacity']}")
    
    assert agent_stats['mass'] == 0.0
    assert agent_stats['capacity'] == 100.0

    # 3. Add heavy items via SQL to force overburdened state
    # 40 Cobalt Ore = 160kg (Default capacity 100kg)
    print("\nAdding 40 Cobalt Ore (160kg) to inventory via SQL...")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'COBALT_ORE', 40)"), {"id": agent_id})
        conn.execute(text("UPDATE agents SET energy = 100, q = 0, r = 0 WHERE id = :id"), {"id": agent_id})
        conn.commit()

    # 4. Verify Mass in Perception
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    perception = resp.json()
    agent_stats = perception['content']['agent_status']
    print(f"Overburdened Mass: {agent_stats['mass']} / {agent_stats['capacity']}")
    assert agent_stats['mass'] == 160.0

    # 5. Move while overburdened
    # 160kg / 100kg = 1.6 penalty. 
    # Base MOVE_ENERGY_COST = 5.
    # Expected cost = 5 * 1.6 = 8.0 NRG.
    print(f"\nSubmitting MOVE intent to (1, 0) while overburdened...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "MOVE",
        "data": {"target_q": 1, "target_r": 0}
    }, headers=headers)

    print(f"Waiting {WAIT_TIME}s for Phase Cycle (Crunch)...")
    time.sleep(WAIT_TIME)

    # 6. Verify Results via Logs
    resp_logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp_logs.json()
    
    move_log = next((l for l in logs if l['event'] == 'MOVEMENT'), None)
    if move_log:
        cost = move_log['details'].get('energy_cost', 0)
        print(f"SUCCESS: Move executed. Energy Cost recorded in logs: {cost}")
        # Penalty calculation check
        if cost > 5:
            print(f"VERIFIED: Mass penalty applied! Cost {cost} > Base 5")
        else:
            print(f"FAILED: Mass penalty NOT applied. Cost is {cost}")
    else:
        print("FAILED: No MOVEMENT log found. Check server logs.")

    # 7. Test Frame Capacity Bonus
    print("\nTesting Frame Capacity Bonus...")
    # Add a frame to inventory and equip it
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'PART_BASIC_FRAME', 1)"), {"id": agent_id})
        conn.commit()
    
    print("Equipping BASIC_FRAME (Reinforced Chassis)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "EQUIP",
        "data": {"item_type": "PART_BASIC_FRAME"}
    }, headers=headers)
    
    print("Waiting for Equip Crunch...")
    time.sleep(WAIT_TIME)
    
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    perception = resp.json()
    final_stats = perception['content']['agent_status']
    print(f"Updated Capacity: {final_stats['capacity']} (Expected 150.0)")
    
    if final_stats['capacity'] == 150.0:
        print("VERIFIED: Frame capacity bonus applied correctly.")
    else:
        print(f"FAILED: Capacity is {final_stats['capacity']}")

if __name__ == "__main__":
    test_mass_mechanics()
