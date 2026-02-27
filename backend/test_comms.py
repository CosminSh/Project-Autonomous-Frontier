import requests
import time
import sys
import random

BASE_URL = "http://localhost:8000"

def wait_for_next_tick(timeout=60):
    start_time = time.time()
    initial_tick = None
    try:
        resp = requests.get(f"{BASE_URL}/api/debug/heartbeat")
        if resp.status_code == 200:
            initial_tick = resp.json()["tick"]
    except:
        return None
    
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

def test_comms():
    print("\n--- STARTING NETWORK INTELLIGENCE VERIFICATION ---")
    
    # 1. Setup Agents
    ts = int(time.time())
    
    resp_1 = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"alpha_{ts}@test.com", "name": f"Alpha-{ts}"})
    if resp_1.status_code != 200:
        print("Failed to register Alpha")
        return
    key_1 = resp_1.json()["api_key"]
    id_1 = resp_1.json()["agent_id"]
    headers_1 = {"X-API-KEY": key_1}
    
    resp_2 = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"beta_{ts}@test.com", "name": f"Beta-{ts}"})
    key_2 = resp_2.json()["api_key"]
    id_2 = resp_2.json()["agent_id"]
    headers_2 = {"X-API-KEY": key_2}
    
    print(f"Alpha: {id_1}, Beta: {id_2}")
    
    # Position them nearby
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": id_1, "q": 0, "r": 0})
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": id_2, "q": 0, "r": 0})

    # 2. Test BROADCAST
    print("\n[1] Testing BROADCAST...")
    intent_req = requests.post(f"{BASE_URL}/api/intent", headers=headers_1, json={"action_type": "BROADCAST", "data": {"message": "Hello Sector!"}})
    print("Broadcast queued.")
    
    wait_for_next_tick(20)
    
    percep = requests.get(f"{BASE_URL}/api/perception", headers=headers_2).json()
    messages = percep.get("content", {}).get("messages", [])
    found = any(m.get("message") == "Hello Sector!" for m in messages)
    if found:
        print("PASS: Broadcast received!")
    else:
        print("FAIL: Broadcast not found in perception.")

    # 3. Test SQUAD
    print("\n[2] Testing SQUADS...")
    invite_req = requests.post(f"{BASE_URL}/api/squad/invite", headers=headers_1, json={"target_id": id_2})
    print("Squad Invite:", invite_req.json().get("status"))
    
    percep1 = requests.get(f"{BASE_URL}/api/perception", headers=headers_1).json()
    telemetry1 = percep1.get("content", {}).get("squad_telemetry", [])
    
    if len(telemetry1) > 0 and telemetry1[0]["id"] == id_2:
        print("PASS: Beta is in Alpha's squad telemetry.")
    else:
        print("FAIL: Beta missing from telemetry.")

    leave_req = requests.post(f"{BASE_URL}/api/squad/leave", headers=headers_2)
    print("Beta Leave Squad:", leave_req.json().get("status"))

    percep1_after = requests.get(f"{BASE_URL}/api/perception", headers=headers_1).json()
    if len(percep1_after.get("content", {}).get("squad_telemetry", [])) == 0:
        print("PASS: Squad empty after leaving.")
    else:
        print("FAIL: Squad not empty after leaving.")
        
    print("\nNetwork Intelligence Verification Complete.")

if __name__ == "__main__":
    test_comms()
