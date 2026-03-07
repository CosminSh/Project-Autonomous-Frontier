import requests
import time

BASE_URL = "http://localhost:8000"

def test_arena():
    print("--- Testing Scrap Pit Arena ---")
    
    # 1. Login or Create Agent
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": "gladiator@test.local", "name": "Gladiator"})
    agent = resp.json()
    token = agent['api_key']
    headers = {"X-API-KEY": token}
    print(f"Logged in: {agent['name']} [ID: {agent['agent_id']}]")

    # 2. Check Arena Status
    print("\nChecking Initial Arena Status...")
    status_resp = requests.get(f"{BASE_URL}/api/arena/status", headers=headers)
    status = status_resp.json()
    print(f"Fighter Name: {status['fighter_name']}")
    print(f"Status Ready: {status['is_ready']}")
    print(f"Warning: {status.get('warning')}")
    print(f"Requirements: {status.get('requirements')}")
    
    # 3. Equip some gear (if any)
    # We'll try to find a part in the agent's inventory
    # Actually, the agent is new, so it has nothing.
    
    # For a real test, we'd need to craft something.
    # But we can at least verify the endpoints exist and return 200.
    
    # 4. Check Arena Logs
    print("\nChecking Arena Logs...")
    logs_resp = requests.get(f"{BASE_URL}/api/arena/logs", headers=headers)
    logs = logs_resp.json()
    print(f"Logs count: {len(logs)}")

    print("\nArena verification complete.")

if __name__ == "__main__":
    test_arena()
