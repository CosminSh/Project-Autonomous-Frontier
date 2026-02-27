import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_manual_commands():
    print("\n--- STARTING MANUAL COMMAND VERIFICATION ---")
    
    # 1. Create a Test Agent
    print("\n[1] Getting Guest Agent...")
    ts = int(time.time())
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"manual_test_{ts}@test.com", "name": f"TerminalTester-{ts}"})
    if resp.status_code != 200:
        print(f"Guest login failed: {resp.text}")
        return
    
    data = resp.json()
    api_key = data["api_key"]
    headers = {"X-API-KEY": api_key}
    print(f"Agent authenticated. API Key: {api_key[:8]}...")

    # 2. Test Invalid Action
    print("\n[2] Testing Invalid Action...")
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "DANCE", "data": {}})
    if resp.status_code == 400:
        print(f"PASS: Correctly rejected invalid action. (Status: {resp.status_code}, Detail: {resp.json().get('detail')})")
    else:
        print(f"FAIL: Expected 400 for invalid action, got {resp.status_code}")

    # 3. Test MOVE Validation (Missing Coordinates)
    print("\n[3] Testing MOVE Validation (Missing Params)...")
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "MOVE", "data": {"target_q": 1}})
    if resp.status_code == 400:
        print(f"PASS: Correctly rejected incomplete MOVE. (Status: {resp.status_code}, Detail: {resp.json().get('detail')})")
    else:
        print(f"FAIL: Expected 400 for incomplete MOVE, got {resp.status_code}")

    # 4. Test MOVE Validation (Invalid Types)
    print("\n[4] Testing MOVE Validation (Invalid Types)...")
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "MOVE", "data": {"target_q": "A", "target_r": "B"}})
    if resp.status_code == 400:
        print(f"PASS: Correctly rejected non-integer MOVE. (Status: {resp.status_code}, Detail: {resp.json().get('detail')})")
    else:
        print(f"FAIL: Expected 400 for non-integer MOVE, got {resp.status_code}")

    # 5. Test SMELT/CRAFT Validation (Missing Payload)
    print("\n[5] Testing SMELT Validation (Empty Data)...")
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "SMELT", "data": {}})
    if resp.status_code == 400:
        print(f"PASS: Correctly rejected empty SMELT. (Status: {resp.status_code}, Detail: {resp.json().get('detail')})")
    else:
        print(f"FAIL: Expected 400 for empty SMELT, got {resp.status_code}")

    # 6. Test Valid Manual Commands
    print("\n[6] Testing Valid Manual Commands...")
    valid_intents = [
        {"action_type": "MOVE", "data": {"target_q": 5, "target_r": -2}},
        {"action_type": "MINE", "data": {}},
        {"action_type": "SCAN", "data": {}},
        {"action_type": "HELP", "data": {}} # Wait, HELP is frontend only in app.js, but let's see if VALID_ACTIONS includes it
    ]
    
    # Check if HELP is in VALID_ACTIONS in main.py
    # VALID_ACTIONS = ["MOVE", "MINE", "SCAN", "ATTACK", "INTIMIDATE", "LOOT", "DESTROY", "LIST", "BUY", "CANCEL", "EQUIP", "UNEQUIP", "SMELT", "CRAFT", "REPAIR", "SALVAGE", "CONSUME", "CORE_SERVICE", "REFINE_GAS", "CHANGE_FACTION"]
    # HELP is NOT in VALID_ACTIONS. The script should reflect this.
    
    for intent in valid_intents:
        if intent["action_type"] == "HELP": continue 
        
        resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json=intent)
        if resp.status_code == 200:
            print(f"PASS: Accepted valid {intent['action_type']} intent.")
        else:
            print(f"FAIL: Rejected valid {intent['action_type']} intent. (Status: {resp.status_code}, Detail: {resp.text})")

    print("\nManual Command Verification Complete.")

if __name__ == "__main__":
    test_manual_commands()
