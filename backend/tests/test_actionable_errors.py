import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///backend/verify.db"
engine = create_engine(DB_PATH)

def test_actionable_errors():
    print("--- STARTING EXPANDED ACTIONABLE ERRORS VERIFICATION ---")
    
    # 1. Guest Login (Attacker)
    print("Logging in as Attacker...")
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"name": "Attacker", "email": "attacker@errors.com"})
    attacker_data = resp.json()
    attacker_key = attacker_data['api_key']
    attacker_id = attacker_data['agent_id']
    attacker_headers = {"X-API-KEY": attacker_key}

    # 2. Guest Login (Target - to be out of range)
    print("Logging in as Target...")
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"name": "Target", "email": "target@errors.com"})
    target_data = resp.json()
    target_id = target_data['agent_id']
    # Move target away
    print("Moving target to (5,5)...")
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MOVE", "data": {"target_q": 5, "target_r": 5}}, headers={"X-API-KEY": target_data['api_key']})
    
    print("Waiting for target to relocate (10s)...")
    time.sleep(10)

    # 3. Trigger Combat Errors (Out of Range)
    print("\nTriggering COMBAT_FAILED (Out of Range)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "ATTACK",
        "data": {"target_id": target_id}
    }, headers=attacker_headers)

    # 4. Trigger Equip Errors (Invalid Part)
    print("Triggering EQUIP_FAILED (Invalid Part: IRON_ORE)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "EQUIP",
        "data": {"item_type": "IRON_ORE"}
    }, headers=attacker_headers)

    # 5. Trigger Consume Errors (Not Consumable)
    print("Triggering CONSUME_FAILED (Not Consumable: IRON_ORE)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "CONSUME",
        "data": {"item_type": "IRON_ORE"}
    }, headers=attacker_headers)

    # 6. Trigger Salvage Errors (Invalid Drop)
    print("Triggering SALVAGE_FAILED (Invalid Drop: 9999)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "SALVAGE",
        "data": {"drop_id": 9999}
    }, headers=attacker_headers)

    print("\nWaiting for Crunch (25s)...")
    time.sleep(25)

    # 7. Verify Audit Logs
    print("\nVerifying Audit Logs...")
    resp = requests.get(f"{BASE_URL}/api/agent_logs", headers=attacker_headers)
    logs = resp.json()
    
    expectations = {
        "COMBAT_FAILED": False,
        "EQUIP_FAILED": False,
        "CONSUME_FAILED": False,
        "SALVAGE_FAILED": False
    }
    
    for log in logs:
        event = log['event']
        details = log['details']
        if "help" in details:
            if event in expectations:
                print(f"FOUND {event} Help: {details['help']}")
                expectations[event] = True

    all_passed = True
    for event, found in expectations.items():
        if not found:
            print(f"FAILED: Help message missing for {event}")
            all_passed = False

    if all_passed:
        print("\n--- ALL ACTIONABLE ERRORS VERIFIED SUCCESSFUL ---")
    else:
        raise Exception("Some verification tests failed.")

if __name__ == "__main__":
    try:
        test_actionable_errors()
    except Exception as e:
        print(f"Verification Failed: {e}")
        exit(1)
