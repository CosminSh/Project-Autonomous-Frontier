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

def test_piracy():
    print("\n--- STARTING PIRACY MECHANICS VERIFICATION ---")
    
    # 1. Setup Pirate and Victim
    print("\n[1] Setting up Agents...")
    ts = int(time.time())
    
    # Pirate Agent
    resp_p = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"pirate_{ts}@test.com", "name": f"Blackbeard_{ts}"})
    pirate_key = resp_p.json()["api_key"]
    pirate_id = resp_p.json()["agent_id"]
    p_headers = {"X-API-KEY": pirate_key}
    
    # Victim Agent
    resp_v = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"victim_{ts}@test.com", "name": f"Merchant_{ts}"})
    victim_key = resp_v.json()["api_key"]
    victim_id = resp_v.json()["agent_id"]
    v_headers = {"X-API-KEY": victim_key}
    
    print(f"Pirate: {pirate_id}, Victim: {victim_id}")
    
    # Position them at (5, 5) - Anarchy Zone
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": pirate_id, "q": 5, "r": 5})
    requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": victim_id, "q": 5, "r": 5})
    
    # Give Victim some loot
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": victim_id, "item_type": "IRON_ORE", "quantity": 100})
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": victim_id, "item_type": "GOLD_INGOT", "quantity": 50})

    # 2. Test Neural Scanner
    print("\n[2] Testing Neural Scanner Gear...")
    # Add scanner to pirate
    requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": pirate_id, "item_type": "PART_NEURAL_SCANNER", "quantity": 1})
    requests.post(f"{BASE_URL}/api/intent", headers=p_headers, json={"action_type": "EQUIP", "data": {"item_type": "PART_NEURAL_SCANNER"}})
    
    print("Waiting for tick to equip scanner...")
    wait_for_next_tick()
    
    # Check perception
    resp = requests.get(f"{BASE_URL}/api/perception", headers=p_headers)
    agents = resp.json()["nearby_agents"]
    print(f"Seeing {len(agents)} other agents.")
    victim_scan = next((a for a in agents if a["id"] == victim_id), None)
    
    if victim_scan and "scan_data" in victim_scan and victim_scan["scan_data"]:
        print("PASS: Neural Scanner revealed victim's data.")
        print(f"Scanned Items: {len(victim_scan['scan_data']['inventory'])} stacks found.")
    else:
        print("FAIL: Neural Scanner did not provide data.")

    # 3. Test Intimidate
    print("\n[3] Testing INTIMIDATE action...")
    requests.post(f"{BASE_URL}/api/intent", headers=p_headers, json={"action_type": "INTIMIDATE", "data": {"target_id": victim_id}})
    
    wait_for_next_tick()
    
    # Check pirate inventory for siphoned items
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=p_headers)
    inv = resp.json()["inventory"]
    has_loot = any(i["type"] in ["IRON_ORE", "GOLD_INGOT"] for i in inv)
    
    if has_loot:
        print("PASS: Intimidate successful, items acquired.")
    else:
        # Check logs if failed
        print("NOTE: Intimidate might have failed due to RNG. Check server logs.")

    # 4. Test LOOT
    print("\n[4] Testing LOOT action...")
    requests.post(f"{BASE_URL}/api/intent", headers=p_headers, json={"action_type": "LOOT", "data": {"target_id": victim_id}})
    
    wait_for_next_tick()
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=p_headers)
    inv = resp.json()["inventory"]
    print(f"Pirate Inventory: {inv}")
    
    # 5. Test DESTROY
    print("\n[5] Testing DESTROY action (The Final Robbery)...")
    requests.post(f"{BASE_URL}/api/intent", headers=p_headers, json={"action_type": "DESTROY", "data": {"target_id": victim_id}})
    
    wait_for_next_tick()
    
    # Check Victim HP
    resp_v_status = requests.get(f"{BASE_URL}/api/my_agent", headers=v_headers)
    v_hp = resp_v_status.json()["health"]
    print(f"Victim HP after DESTROY: {v_hp}")
    
    # Check Pirate Heat
    resp_p_status = requests.get(f"{BASE_URL}/api/my_agent", headers=p_headers)
    p_heat = resp_p_status.json().get("heat", 0)
    print(f"Pirate Heat: {p_heat}")
    
    # Check Bounties
    resp_b = requests.get(f"{BASE_URL}/api/bounties")
    pirate_bounty = next((b for b in resp_b.json() if b["target_id"] == pirate_id), None)
    
    if v_hp <= 10 and pirate_bounty:
        print("PASS: DESTROY action reduced HP and triggered bounty.")
    else:
        print(f"FAIL: DESTROY results - HP: {v_hp}, Bounty Found: {pirate_bounty is not None}")

    print("\nPiracy Verification Complete.")

if __name__ == "__main__":
    test_piracy()
