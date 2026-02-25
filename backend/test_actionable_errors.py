import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///backend/demo.db" # Updated to match my run command
engine = create_engine(DB_PATH)

def test_actionable_errors():
    print("--- STARTING ACTIONABLE ERRORS VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as guest...")
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"name": "Error-Tester", "email": "tester@errors.com"})
    print(f"Login Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Login Text: {resp.text}")
        return

    try:
        auth_data = resp.json()
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw Response: {resp.text}")
        return

    api_key = auth_data['api_key']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in. API Key: {api_key}")

    # 2. Test Navigation Hint in Perception
    print("\nChecking Perception Navigation Hint...")
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    print(f"Perception Status: {resp.status_code}")
    mcp = resp.json()
    hint = mcp['content']['tick_info'].get('navigation_hint')
    print(f"Navigation Hint: {hint}")
    assert "MOVE is limited to 1 hex" in hint

    # 3. Trigger MOVEMENT_FAILED (Too far)
    print("\nTriggering MOVEMENT_FAILED (Distance 10)...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "MOVE",
        "data": {"target_q": 10, "target_r": 10}
    }, headers=headers)
    
    # 4. Trigger INDUSTRIAL_FAILED (Smelt when not at station)
    print("Triggering INDUSTRIAL_FAILED (Smelt at (0,0))...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "SMELT",
        "data": {"ore_type": "IRON_ORE", "quantity": 10}
    }, headers=headers)

    print("Waiting for Crunch...")
    # Note: We need enough time for the tick to cycle.
    # Current Tick phase durations total 20s. 
    # Let's wait 25s to be safe.
    time.sleep(25)

    # 5. Verify Audit Logs
    print("\nVerifying Audit Logs...")
    resp = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers)
    logs = resp.json()
    
    found_move_error = False
    found_smelt_error = False
    
    for log in logs:
        event = log['event']
        details = log['details']
        if event == "MOVEMENT_FAILED" and "help" in details:
            print(f"FOUND MOVEMENT_FAILED Help: {details['help']}")
            found_move_error = True
        if event == "INDUSTRIAL_FAILED" and "help" in details:
            print(f"FOUND INDUSTRIAL_FAILED Help: {details['help']}")
            found_smelt_error = True

    assert found_move_error, "MOVEMENT_FAILED help message missing"
    assert found_smelt_error, "INDUSTRIAL_FAILED help message missing"
    print("\n--- VERIFICATION SUCCESSFUL ---")

if __name__ == "__main__":
    try:
        test_actionable_errors()
    except Exception as e:
        print(f"Verification Failed: {e}")
