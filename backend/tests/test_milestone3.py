import requests
import time
import sys

BASE_URL = "http://localhost:8001"

def wait_for_next_tick(timeout=60):
    start_time = time.time()
    initial_tick = None
    try:
        resp = requests.get(f"{BASE_URL}/api/debug/heartbeat")
        if resp.status_code == 200:
            initial_tick = resp.json()["tick"]
    except:
        pass
    
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(f"{BASE_URL}/api/debug/heartbeat")
            if resp.status_code == 200:
                data = resp.json()
                if data["tick"] > initial_tick and data["phase"] == "PERCEPTION":
                    return data["tick"]
        except:
            pass
        time.sleep(1)
    return None

def test_milestone3():
    print("\n--- STARTING MILESTONE 3 VERIFICATION ---")
    
    # 1. Create a Test Agent (using Guest Login)
    print("\n[1] Getting Guest Agent...")
    ts = int(time.time())
    email1 = f"m3_tester_{ts}@test.com"
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": email1, "name": f"Tester-{ts}"})
    if resp.status_code != 200:
        print(f"Guest login failed: {resp.text}")
        return
    
    data = resp.json()
    api_key = data["api_key"]
    agent_id = data["agent_id"]
    headers = {"X-API-KEY": api_key}
    print(f"Using Agent {agent_id} ({email1})")

    # 2. Test Solar-Trickle
    print("\n[2] Testing Solar-Trickle (Passive Regen)...")
    requests.post(f"{BASE_URL}/api/debug/set_structure", json={"agent_id": agent_id, "capacitor": 50})
    
    print("Waiting for next tick to ensure regen...")
    wait_for_next_tick()
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    nrg = resp.json()["capacitor"]
    print(f"Energy after regen ticks: {nrg}")
    if nrg > 50:
        print("PASS: Solar-Trickle is regenerating energy.")
    else:
        print("FAIL: Solar-Trickle not detected.")

    # 3. Test HE3 Consumption & Overclocking
    print("\n[3] Testing HE3 Consumption...")
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "HE3_FUEL_CELL", "quantity": 1})
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "CONSUME", "data": {"item_type": "HE3_FUEL_CELL"}})
    
    print("Waiting for next tick to process consumption...")
    wait_for_next_tick()
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    ticks = resp.json().get("overclock_ticks")
    print(f"Overclock ticks after consumption: {ticks}")
    if ticks is not None and ticks > 0:
        print("PASS: HE3 consumed and Overclock active.")
    else:
        print(f"FAIL: Overclock ticks expected >0, got {ticks}")

    # 3.1 Test Overclock Movement (3 hexes)
    print("\n[3.1] Testing Overclock Movement (3 hexes)...")
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id, "q": 0, "r": 0})
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "MOVE", "data": {"target_q": 3, "target_r": 0}})
    
    print("Waiting for next tick to process 3-hex MOVE...")
    wait_for_next_tick()
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    pos = (resp.json()["q"], resp.json()["r"])
    print(f"Position after 3-hex MOVE: {pos}")
    if pos == (3, 0):
        print("PASS: Overclock enabled 3-hex travel.")
    else:
        print("FAIL: Overclock did not enable 3-hex travel.")

    # 4. Test Market Entropy
    print("\n[4] Testing Market Entropy (Density Scaling)...")
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id, "q": 1, "r": 1})
    
    email2 = f"m3_crowd_{ts}@test.com"
    resp2 = requests.post(f"{BASE_URL}/auth/guest", json={"email": email2, "name": f"Crowd-{ts}"})
    api_key2 = resp2.json()["api_key"]
    agent_id2 = resp2.json()["agent_id"]
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id2, "q": 1, "r": 1})
    
    print(f"Agent {agent_id} and Agent {agent_id2} are now both at (1, 1).")
    
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "MINE"})
    requests.post(f"{BASE_URL}/api/intent", headers={"X-API-KEY": api_key2}, json={"action_type": "MINE"})
    
    print("Waiting for next tick to process crowded mining...")
    wait_for_next_tick()
    print("Mining intents processed. Check server logs for 'Market Entropy' multiplier.")

    # 5. Test Core Service
    print("\n[5] Testing Core Service (Maintenance)...")
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": agent_id, "q": 0, "r": 0})
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "IRON_INGOT", "quantity": 10})
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": agent_id, "item_type": "CREDITS", "quantity": 500})
    
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json={"action_type": "CORE_SERVICE", "data": {}})
    
    print("Waiting for next tick to process core service...")
    wait_for_next_tick()
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    wt = resp.json().get("wear_and_tear")
    print(f"Wear & Tear after service: {wt}")
    if wt is not None and wt < 0.2:
        print("PASS: Core Service reset wear & tear.")
    else:
        print(f"FAIL: Wear & Tear expected <0.2, got {wt}")

    print("\nVerification Complete.")

if __name__ == "__main__":
    test_milestone3()
