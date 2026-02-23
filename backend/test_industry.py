import requests
import time
import uuid
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8001"
DB_PATH = "sqlite:///demo.db"
engine = create_engine(DB_PATH)

def test_industry():
    print("--- STARTING INDUSTRY & REPAIR VERIFICATION ---")
    
    # 1. Guest Login to get an agent
    print("Logging in as guest...")
    resp = requests.post(f"{BASE_URL}/auth/guest")
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (Agent ID: {agent_id})")

    # 2. Check initial state
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent = resp.json()
    print(f"Initial HP: {agent['structure']}, Credits: {next((i['quantity'] for i in agent['inventory'] if i['type'] == 'CREDITS'), 0)}")

    # 4. Give Resources
    print("\nSeeding agent with resources...")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'IRON_ORE', 50)"), {"id": agent_id})
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'CREDITS', 1000)"), {"id": agent_id})
        conn.commit()

    # 5. Smelt Test
    print("\nWarping to Smelter at (10,0)...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q = 10, r = 0 WHERE id = :id"), {"id": agent_id})
        conn.commit()

    print("Submitting SMELT intent (10 IRON_ORE)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "SMELT",
        "data": {"ore_type": "IRON_ORE", "quantity": 10}
    }, headers=headers)
    
    print("Waiting for Crunch (Phase Cycle)...")
    time.sleep(22)

    # 6. Craft Test
    print("\nWarping to Crafter at (0,10) and giving 10 Iron Ingots...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q = 0, r = 10 WHERE id = :id"), {"id": agent_id})
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'IRON_INGOT', 10)"), {"id": agent_id})
        conn.commit()

    # Verification: Check inventory via SQL
    with engine.connect() as conn:
        res = conn.execute(text("SELECT item_type, quantity FROM inventory_items WHERE agent_id = :id"), {"id": agent_id})
        print("Current Inventory (SQL):", [dict(r) for r in res.mappings()])

    print("Submitting CRAFT intent (BASIC_FRAME)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "CRAFT",
        "data": {"item_type": "BASIC_FRAME"}
    }, headers=headers)

    print("Waiting for Crunch (Phase Cycle)...")
    time.sleep(22)

    # 7. Repair Test
    print("\nWarping to Repair at (-10,0)...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q = -10, r = 0, structure = 50 WHERE id = :id"), {"id": agent_id})
        conn.commit()

    print("Submitting REPAIR intent (10 HP)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "REPAIR",
        "data": {"amount": 10}
    }, headers=headers)

    print("Waiting for final Crunch...")
    time.sleep(22)

    # 8. Verify Results
    print("\n--- FINAL VERIFICATION ---")
    resp_logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp_logs.json()
    
    print("Recent Logs:")
    for log in logs:
        print(f"[{log['time']}] {log['event']}: {log['details']}")

    smelt_success = any(l['event'] == 'INDUSTRIAL_SMELT' for l in logs)
    craft_success = any(l['event'] == 'INDUSTRIAL_CRAFT' for l in logs)
    repair_success = any(l['event'] == 'REPAIR' for l in logs)

    print(f"\nSmelt Success: {smelt_success}")
    print(f"Craft Success: {craft_success}")
    print(f"Repair Success: {repair_success}")

if __name__ == "__main__":
    test_industry()
