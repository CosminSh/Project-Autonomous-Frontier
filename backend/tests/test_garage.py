import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8001"
DB_PATH = "sqlite:///demo.db"
engine = create_engine(DB_PATH)

def test_garage():
    print("--- STARTING GARAGE VERIFICATION ---")
    
    # 1. Login
    resp = requests.post(f"{BASE_URL}/auth/guest")
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in Agent ID: {agent_id}")

    # 2. Seed a Part in Inventory
    print("Seeding PART_BASIC_FRAME in inventory...")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'PART_BASIC_FRAME', 1)"), {"id": agent_id})
        conn.commit()

    # 3. Check Initial Stats
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent = resp.json()
    initial_max_hp = agent['max_structure']
    print(f"Initial Max HP: {initial_max_hp}")

    # 4. Equip Part
    print("Submitting EQUIP intent...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "EQUIP",
        "data": {"item_type": "PART_BASIC_FRAME"}
    }, headers=headers)

    print("Waiting for Crunch...")
    time.sleep(22)

    # 5. Verify Equipped & Stats
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent = resp.json()
    equipped_parts = agent['parts']
    new_max_hp = agent['max_structure']
    
    print(f"New Max HP: {new_max_hp}")
    print(f"Equipped Parts: {[p['name'] for p in equipped_parts]}")

    if new_max_hp > initial_max_hp and any(p['name'] == "Reinforced Chassis" for p in equipped_parts):
        print("[SUCCESS] EQUIP Successful!")
    else:
        print("[FAILURE] EQUIP Failed!")
        return

    # 6. Unequip Part
    part_id = equipped_parts[0]['id']
    print(f"Submitting UNEQUIP intent for Part ID: {part_id}...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "UNEQUIP",
        "data": {"part_id": part_id}
    }, headers=headers)

    print("Waiting for Crunch...")
    time.sleep(22)

    # 7. Final Verification
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent = resp.json()
    final_max_hp = agent['max_structure']
    inventory = agent['inventory']
    
    print(f"Final Max HP: {final_max_hp}")
    has_part_back = any(i['type'] == 'PART_BASIC_FRAME' for i in inventory)
    
    if final_max_hp == initial_max_hp and has_part_back:
        print("[SUCCESS] UNEQUIP Successful!")
    else:
        print(f"[FAILURE] UNEQUIP Failed! Final HP: {final_max_hp}, Inventory: {inventory}")

if __name__ == "__main__":
    test_garage()
