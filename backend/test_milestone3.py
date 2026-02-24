import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_milestone3():
    print("\n--- STARTING MILESTONE 3 VERIFICATION ---")
    
    # 1. Create a Test Agent (using Guest Login)
    print("\n[1] Getting Guest Agent...")
    resp = requests.post(f"{BASE_URL}/auth/guest")
    if resp.status_code != 200:
        print(f"Guest login failed: {resp.text}")
        return
    
    data = resp.json()
    api_key = data["api_key"]
    agent_id = data["agent_id"]
    headers = {"X-API-KEY": api_key}
    print(f"Using Agent {agent_id} (API Key: {api_key[:8]}...)")

    # 2. Test Solar-Trickle
    print("\n[2] Testing Solar-Trickle (Passive Regen)...")
    # Set energy to 50
    requests.post(f"{BASE_URL}/api/debug/set_structure", json={"agent_id": agent_id, "capacitor": 50})
    
    print("Waiting 2 ticks for regen (+4 energy expected)...")
    time.sleep(20) # 2 ticks (10s Perception/Strategy + 5s Strategy + 5s Crunch = ~20s per total cycle)
    # Actually phases are 5, 10, 5 = 20s total.
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    nrg = resp.json()["capacitor"]
    print(f"Energy after 2 ticks: {nrg}")
    if nrg > 50:
        print("PASS: Solar-Trickle is regenerating energy.")
    else:
        print("FAIL: Solar-Trickle not detected.")

    # 3. Test HE3 Consumption & Overclocking
    print("\n[3] Testing HE3 Consumption...")
    # Inject HE3_FUEL_CELL
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "HE3_FUEL_CELL", "quantity": 1})
    
    intent_data = {"action_type": "CONSUME", "data": {"item_type": "HE3_FUEL_CELL"}}
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json=intent_data)
    print(f"Consume intent response: {resp.status_code}")
    
    # Wait for Crunch
    time.sleep(20)
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    data = resp.json()
    print(f"Overclock ticks: {data.get('overclock_ticks')}")
    if data.get("overclock_ticks") == 9: # 10 - 1 for the tick decay
        print("PASS: HE3 consumed and Overclock active.")
    else:
        print(f"FAIL: Overclock ticks expected 9, got {data.get('overclock_ticks')}")

    # 4. Test Market Entropy
    print("\n[4] Testing Market Entropy (Density Scaling)...")
    # Teleport to a resource hex (1, 1) - assuming it has resources
    # Ensure it's not a station and has density
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id, "q": 1, "r": 1})
    
    # Create another agent at the same location using unique identifiers
    email2 = "m3_entropy_tester@test.com"
    resp2 = requests.post(f"{BASE_URL}/auth/guest", json={"email": email2, "name": "M3-Crowd"})
    if resp2.status_code != 200:
        print(f"Guest login 2 failed: {resp2.text}")
        return
        
    data2 = resp2.json()
    api_key2 = data2["api_key"]
    agent_id2 = data2["agent_id"]
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id2, "q": 1, "r": 1})
    
    print(f"Agent {agent_id} and Agent {agent_id2} are now both at (1, 1).")
    
    # Mine Intent for both
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "MINE"})
    requests.post(f"{BASE_URL}/api/intent", headers={"X-API-KEY": api_key2}, json={"action_type": "MINE"})
    
    print("Mining intents submitted for both. Look for 'Market Entropy applied' in server logs.")
    time.sleep(20)

    # 5. Test Core Service
    print("\n[5] Testing Core Service (Maintenance)...")
    # Teleport to Hub (0, 0)
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id, "q": 0, "r": 0})
    
    # Inject requirements
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "IRON_INGOT", "quantity": 10})
    # Agent already has credits from login or we inject them
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "CREDITS", "quantity": 500})
    
    intent_data = {"action_type": "CORE_SERVICE", "data": {}}
    resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json=intent_data)
    print(f"Core Service intent response: {resp.status_code}")
    
    time.sleep(20)
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    wt = resp.json().get("wear_and_tear")
    print(f"Wear & Tear after service: {wt}")
    if wt == 0.1: # Reset to 0 but incremented by 0.1 in the same tick resolution
        print("PASS: Core Service reset wear & tear.")
    else:
        print(f"FAIL: Wear & Tear expected ~0.1, got {wt}")

    print("\nVerification Complete.")

if __name__ == "__main__":
    test_milestone3()
