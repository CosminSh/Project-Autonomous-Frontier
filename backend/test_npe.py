import requests
import time

BASE_URL = "http://localhost:8000"

def get_guest_token(name="NPETester"):
    res = requests.post(f"{BASE_URL}/auth/guest", json={"display_name": name})
    res.raise_for_status()
    return res.json()["api_key"]

def test_daily_claim(token):
    print("Testing Daily Claim...")
    headers = {"X-API-KEY": token}
    res = requests.post(f"{BASE_URL}/api/claim_daily", headers=headers)
    res.raise_for_status()
    print("Claim successful!")

    # Verify cooldown
    res2 = requests.post(f"{BASE_URL}/api/claim_daily", headers=headers)
    assert res2.status_code == 400
    print("Cooldown verified.")

def get_agent_data(token):
    headers = {"X-API-KEY": token}
    res = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    res.raise_for_status()
    return res.json()

def test_bound_items_market(token, agent_data):
    print("Testing bound items on market...")
    headers = {"X-API-KEY": token}

    # Attempt to list FIELD_REPAIR_KIT (bound)
    intent = {
        "action": "LIST",
        "data": {
            "item_type": "FIELD_REPAIR_KIT",
            "price": 100,
            "quantity": 1
        }
    }
    requests.post(f"{BASE_URL}/api/intent", headers=headers, json=intent)

    # Let heartbeat process
    time.sleep(2)

    # Verify item was not listed (still in inventory, no audit log success, or check market)
    agent_updated = get_agent_data(token)
    kits = [i for i in agent_updated.get("inventory", []) if i["type"] == "FIELD_REPAIR_KIT"]
    
    # We started with 2 + 1 from daily = 3 kits. They should all still be there.
    assert len(kits) > 0
    assert kits[0]["quantity"] == 3
    print("Market LIST rejected successfully.")

def test_mission_tiers(token, agent_data):
    print("Testing Mission Tiers...")
    headers = {"X-API-KEY": token}
    res = requests.get(f"{BASE_URL}/api/missions", headers=headers)
    res.raise_for_status()
    missions = res.json()
    
    # NPETester is newly created = Level 1
    # Only Tier 1 missions should be visible (min_level 1, max_level 2)
    for m in missions:
        # We can't see max_level from the API response directly but we can verify the rewards/targets
        # Tier 1 targets: Hunt 1 Feral (200CR), Buy 1 Market (100CR), Turn int 10 Ore (100CR) / 5 Ingot (150CR)
        valid_rewards = [100, 150, 200]
        assert m["reward_credits"] in valid_rewards, f"Found high level mission: {m}"
    
    print("Mission tiers validated for Level 1.")


if __name__ == "__main__":
    t = get_guest_token()
    a = get_agent_data(t)
    
    # Verify starter package
    kits = [i for i in a.get("inventory", []) if i["type"] == "FIELD_REPAIR_KIT"]
    print("Found kits in inventory:", kits)
    assert kits and kits[0]["quantity"] >= 2
    print("Starter package verified.")

    test_daily_claim(t)
    test_bound_items_market(t, a)
    test_mission_tiers(t, a)

    print("ALL NPE TESTS PASSED.")
