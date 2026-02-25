import requests
import time

BASE_URL = "http://localhost:8000"

def test_hazards():
    print("--- Testing Milestone 4: Social Hazards ---")
    
    # 1. Verify /api/world/heat exists
    print("Checking /api/world/heat...")
    resp = requests.get(f"{BASE_URL}/api/world/heat")
    if resp.status_code == 200:
        print("SUCCESS: Heat API operational.")
        print(f"Hot Agents: {resp.json()}")
    else:
        print(f"FAILURE: Heat API returned {resp.status_code}")

    # 2. Verify Bounties
    print("\nChecking /api/bounties...")
    resp = requests.get(f"{BASE_URL}/api/bounties")
    if resp.status_code == 200:
        bounties = resp.json()
        print(f"SUCCESS: Bounties operational. Found {len(bounties)} bounties.")
        for b in bounties:
            print(f" - Target Agent {b['target_id']}: Reward {b['reward']}")
    else:
        print(f"FAILURE: Bounties API returned {resp.status_code}")

    # 3. Create a Guest Agent and check Faction
    print("\nChecking Guest Agent Faction/Stats...")
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/auth/guest")
    if resp.status_code == 200:
        api_key = resp.json()["api_key"]
        headers = {"X-API-KEY": api_key}
        
        agent_resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
        agent = agent_resp.json()
        print(f"Agent Name: {agent['name']}")
        print(f"Faction ID: {agent.get('faction_id', 'MISSING')}")
        
        per_resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
        per = per_resp.json()
        current_faction = per['content']['agent_status'].get('faction_id')
        print(f"Initial Faction: {current_faction}")

        # 5. Test Faction Change
        print("\nTesting Faction Change Intent...")
        new_faction = 2 if current_faction != 2 else 1
        intent_resp = requests.post(f"{BASE_URL}/api/intent", headers=headers, json={
            "action_type": "CHANGE_FACTION",
            "data": {"new_faction_id": new_faction}
        })
        if intent_resp.status_code == 200:
            print(f"SUCCESS: Faction change intent submitted for tick {intent_resp.json()['scheduled_tick']}")
            print("Wait for crunch to process (manual check or wait for next tick)...")
        else:
            print(f"FAILURE: Faction change submission failed: {intent_resp.status_code}")

    else:
        print("FAILURE: Guest login failed.")

    # 4. (Manual/Log Check) Feral Aggression & Signal Noise
    print("\nManual Verification Recommended:")
    print("1. Check backend logs for 'suffering Signal Noise' messages.")
    print("2. Check backend logs for Feral agents attacking player agents.")
    print("3. Verify Feral-Scrapper-New agents have randomized 'is_aggressive' in DB.")

if __name__ == "__main__":
    test_hazards()
