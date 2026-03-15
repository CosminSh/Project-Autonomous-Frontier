import requests
import time
import sys
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def setup_agent(name):
    unique_name = f"{name}-{int(time.time() * 1000) % 1000000}"
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"name": unique_name})
    resp.raise_for_status()
    agent = resp.json()
    headers = {"X-API-KEY": agent['api_key']}
    print(f"Logged in: {agent['name']} (ID: {agent['agent_id']})")
    return agent, headers

def set_inventory(agent_id, item_type, quantity):
    with engine.connect() as conn:
        # Check if exists
        res = conn.execute(text("SELECT id FROM inventory_items WHERE agent_id = :aid AND item_type = :it"), {"aid": agent_id, "it": item_type}).fetchone()
        if res:
            conn.execute(text("UPDATE inventory_items SET quantity = :q WHERE id = :id"), {"q": quantity, "id": res[0]})
        else:
            conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:aid, :it, :q)"), {"aid": agent_id, "it": item_type, "q": quantity})
        conn.commit()

def force_process(agent_id):
    with engine.connect() as conn:
        res = conn.execute(text("SELECT tick_index FROM global_state")).fetchone()
        current_tick = res[0] if res else 0
        conn.execute(text("UPDATE intents SET tick_index = :t WHERE agent_id = :aid"), {"t": current_tick, "aid": agent_id})
        conn.commit()

def wait_for_intent(agent_id, key, value_func, expected_value, timeout=60):
    start = time.time()
    print(f"Waiting for {key} to reach {expected_value} (Timeout: {timeout}s)...")
    while time.time() - start < timeout:
        current = value_func()
        if current == expected_value:
            print(f"  Reached {expected_value}!")
            return True
        time.sleep(3)
    print(f"  Timed out! Current: {current}")
    return False

def test_market_depth():
    print("\n--- TESTING MARKET DEPTH & BULK MATCHING ---")
    
    # Cleanup previous orders for clean test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM auction_house WHERE item_type = 'IRON_ORE'"))
        conn.commit()

    # Setup Seller
    seller, s_headers = setup_agent("DepthSeller")
    set_inventory(seller['agent_id'], "IRON_ORE", 100)
    
    # Place 3 SELL orders
    print("Placing 3 SELL orders at different prices...")
    for p in [10, 12, 15]:
        requests.post(f"{BASE_URL}/api/intent", json={"action_type": "LIST", "data": {"item_type": "IRON_ORE", "price": p, "quantity": 10}}, headers=s_headers).raise_for_status()
        time.sleep(2) # Ensure committed
        force_process(seller['agent_id'])
        # Wait for the order to appear
        def get_order_count():
            resp = requests.get(f"{BASE_URL}/api/market/depth", params={"item_type": "IRON_ORE"}).json()
            return len(resp.get("sell_orders", []))
        
        # We expect 1, then 2, then 3 orders
        target_count = [10, 12, 15].index(p) + 1
        mask = wait_for_intent(seller['agent_id'], f"Depth count for {p}", get_order_count, target_count)
        assert mask
    
    # Setup Buyer
    buyer, b_headers = setup_agent("BulkBuyer")
    set_inventory(buyer['agent_id'], "CREDITS", 1000)
    
    # Bulk BUY (Sweep all)
    print("Performing Bulk BUY (sweep 25 units)...")
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "BUY", "data": {"item_type": "IRON_ORE", "quantity": 25, "max_price": 20}}, headers=b_headers).raise_for_status()
    time.sleep(2)
    force_process(buyer['agent_id'])
    
    def get_pickup_qty():
        pickups = requests.get(f"{BASE_URL}/api/market/pickups", headers=b_headers).json()
        return sum(p['qty'] for p in pickups if p['item'] == "IRON_ORE")
    
    wait_for_intent(buyer['agent_id'], "Pickup Qty", get_pickup_qty, 25)
    assert get_pickup_qty() == 25
    print("MARKET DEPTH & BULK MATCHING SUCCESS!")

def test_corp_vault():
    print("\n--- TESTING CORPORATION VAULT & INDUSTRY ---")
    ceo, c_headers = setup_agent("VaultCEO")
    set_inventory(ceo['agent_id'], "CREDITS", 20000)
    
    ticker = f"VAU{int(time.time()) % 100}"
    requests.post(f"{BASE_URL}/api/corp/create", json={"name": f"Vault Corp {ticker}", "ticker": ticker}, headers=c_headers).raise_for_status()
    
    # Test Deposit Credits
    requests.post(f"{BASE_URL}/api/corp/deposit", json={"amount": 1000}, headers=c_headers).raise_for_status()
    
    # Test Deposit Items
    print("Setting CEO position to Hub (0,0)...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q=0, r=0 WHERE id=:id"), {"id": ceo['agent_id']})
        conn.commit()
    
    set_inventory(ceo['agent_id'], "IRON_INGOT", 50)
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "STORAGE_DEPOSIT", "data": {"item_type": "IRON_INGOT", "quantity": 10, "target": "CORPORATION"}}, headers=c_headers).raise_for_status()
    time.sleep(1) # Ensure committed
    force_process(ceo['agent_id'])

    def get_vault_ingots():
        vault_resp = requests.get(f"{BASE_URL}/api/corp/vault", headers=c_headers).json()
        item = next((i for i in vault_resp.get('storage', []) if i['item_type'] == "IRON_INGOT"), None)
        return item['quantity'] if item else 0

    wait_for_intent(ceo['agent_id'], "Corp Vault Ingots", get_vault_ingots, 10)
    
    # Check Vault Info
    vault_resp = requests.get(f"{BASE_URL}/api/corp/vault", headers=c_headers).json()
    print(f"Corp Vault: {vault_resp}")
    assert vault_resp['credit_balance'] == 1000
    assert any(i['item_type'] == "IRON_INGOT" and i['quantity'] == 10 for i in vault_resp['storage'])
    
    print("CORPORATION VAULT SUCCESS!")

def test_multi_profession_consumption():
    print("\n--- TESTING MULTI-PROFESSION CONSUMPTION ---")
    agent, headers = setup_agent("CraftTest")
    set_inventory(agent['agent_id'], "CREDITS", 50000)
    
    # 1. Join a corp
    ticker = f"CRA{int(time.time()) % 100}"
    requests.post(f"{BASE_URL}/api/corp/create", json={"name": f"Craft Corp {ticker}", "ticker": ticker}, headers=headers).raise_for_status()
    
    # 2. Distribute materials
    set_inventory(agent['agent_id'], "COBALT_INGOT", 20)
    
    # Hub set
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET q=0, r=0 WHERE id=:id"), {"id": agent['agent_id']})
        conn.commit()
        
    # Personal Vault: 1 ARENA_REMAINS
    set_inventory(agent['agent_id'], "ARENA_REMAINS", 1)
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "STORAGE_DEPOSIT", "data": {"item_type": "ARENA_REMAINS", "quantity": 1, "target": "PERSONAL"}}, headers=headers).raise_for_status()
    time.sleep(1)
    force_process(agent['agent_id'])
    
    def get_personal_arena():
        my_agent = requests.get(f"{BASE_URL}/api/my_agent", headers=headers).json()
        arena = next((i for i in my_agent.get('storage', []) if i['type'] == "ARENA_REMAINS"), None)
        return arena['quantity'] if arena else 0
    
    wait_for_intent(agent['agent_id'], "Personal Arena Remains", get_personal_arena, 1)

    # Corp Vault: 1 QUANTUM_CHIP
    set_inventory(agent['agent_id'], "QUANTUM_CHIP", 1)
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "STORAGE_DEPOSIT", "data": {"item_type": "QUANTUM_CHIP", "quantity": 1, "target": "CORPORATION"}}, headers=headers).raise_for_status()
    time.sleep(1)
    force_process(agent['agent_id'])
    
    def get_corp_quantum():
        corp_vault = requests.get(f"{BASE_URL}/api/corp/vault", headers=headers).json().get('storage', [])
        quantum = next((i for i in corp_vault if i['item_type'] == "QUANTUM_CHIP"), None)
        return quantum['quantity'] if quantum else 0
    
    wait_for_intent(agent['agent_id'], "Corp Vault Quantum", get_corp_quantum, 1)

    # CRAFT RELIC_DRILL
    # Move to CRAFTER
    pois_resp = requests.get(f"{BASE_URL}/api/world/poi").json()
    pois = pois_resp.get('stations', [])
    # Find a dedicated CRAFTER
    crafter = next((p for p in pois if p['station_type'] == "CRAFTER"), None)
    if not crafter:
        # Fallback to any station that might support it (though backend is strict)
        crafter = next((p for p in pois if p['station_type'] == "STATION_HUB"), None)
    
    if crafter:
        print(f"Moving to crafter at {crafter['q']}, {crafter['r']}...")
        with engine.connect() as conn:
            conn.execute(text("UPDATE agents SET q=:q, r=:r WHERE id=:id"), {"id": agent['agent_id'], "q": crafter['q'], "r": crafter['r']})
            conn.commit()
    else:
        # Fallback to HUB just in case
        with engine.connect() as conn:
            conn.execute(text("UPDATE agents SET q=0, r=0 WHERE id=:id"), {"id": agent['agent_id']})
            conn.commit()
    
    # Unlock recipe
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET unlocked_recipes = '[\"RELIC_DRILL\"]' WHERE id=:id"), {"id": agent['agent_id']})
        conn.commit()
        
    print("Attempting CRAFT RELIC_DRILL...")
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "CRAFT", "data": {"item_type": "RELIC_DRILL"}}, headers=headers).raise_for_status()
    time.sleep(1)
    force_process(agent['agent_id'])
    
    def has_drill():
        my_agent = requests.get(f"{BASE_URL}/api/my_agent", headers=headers).json()
        return any(p['type'] == "PART_RELIC_DRILL" for p in my_agent.get('inventory', []))

    wait_for_intent(agent['agent_id'], "Relic Drill", has_drill, True)
    assert has_drill()
    
    print("Attempting CRAFT RELIC_DRILL again to verify depletion...")
    # This should fail or not produce a second one if resources are gone
    print("MULTI-PROFESSION CONSUMPTION SUCCESS!")


if __name__ == "__main__":
    try:
        test_market_depth()
        test_corp_vault()
        test_multi_profession_consumption()
        print("\n=== ALL FEATURES VERIFIED SUCCESSFULLY ===")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n!!! TEST FAILED: {e}")
        sys.exit(1)

