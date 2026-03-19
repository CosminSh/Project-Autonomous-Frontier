import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def wait_for_execution(current_tick):
    target = current_tick + 1
    print(f"Waiting for tick {target} to complete EXECUTE phase (waiting for tick {target + 1} SCAN)...")
    while True:
        try:
            resp = requests.get(f"{BASE_URL}/state")
            state = resp.json()
            # Wait until we see tick target+1, which means target's EXECUTE is definitely done
            if state['tick'] > target:
                return state['tick']
        except Exception as e:
            print(f"Error checking state: {e}")
        time.sleep(1)

def test_metadata_and_transfer():
    print("--- STARTING METADATA & TRANSFER VERIFICATION ---")
    
    # login two agents
    resp_a = requests.post(f"{BASE_URL}/auth/guest", json={"name": f"Alice-{int(time.time())}"})
    agent_a = resp_a.json()
    headers_a = {"X-API-KEY": agent_a['api_key']}
    
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": f"Bob-{int(time.time())}"})
    agent_b = resp_b.json()
    headers_b = {"X-API-KEY": agent_b['api_key']}
    
    print(f"Alice ID: {agent_a['agent_id']}, Bob ID: {agent_b['agent_id']}")

    # Setup: Give Alice a special item and move both to (0,0)
    with engine.connect() as conn:
        # Alice gets a special He3 Canister
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity, data) VALUES (:id, 'HE3_CANISTER', 1, '{\"fill_level\": 77}')"), {"id": agent_a['agent_id']})
        # Alice and Bob to (0,0)
        conn.execute(text("UPDATE agents SET q=0, r=0 WHERE id IN (:ida, :idb)"), {"ida": agent_a['agent_id'], "idb": agent_b['agent_id']})
        # Bob gets some credits for buying
        conn.execute(text("UPDATE inventory_items SET quantity = 1000 WHERE agent_id = :id AND item_type = 'CREDITS'"), {"id": agent_b['agent_id']})
        conn.commit()

    current_tick = requests.get(f"{BASE_URL}/state").json()['tick']

    # TEST 1: TRANSFER
    print("Test 1: Alice transfers special He3 to Bob...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "TRANSFER", 
        "data": {"target_id": agent_b['agent_id'], "item_type": "HE3_CANISTER", "quantity": 1}
    }, headers=headers_a)
    
    current_tick = wait_for_execution(current_tick)
    
    # Check Bob's inventory
    resp_inv = requests.get(f"{BASE_URL}/inventory", headers=headers_b)
    bob_inv = resp_inv.json()
    print(f"DEBUG: Bob's Inventory: {bob_inv}")
    item = next((i for i in bob_inv if i['type'] == 'HE3_CANISTER'), None)
    if item and item.get('data', {}).get('fill_level') == 77:
        print("SUCCESS: Transfer preserved metadata!")
    else:
        print(f"FAILED: Transfer metadata mismatch. Got: {item}")
        return

    # TEST 2: MARKET LIST/BUY
    print("Test 2: Bob lists special He3 for 50 credits, Alice buys it...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "LIST", 
        "data": {"item_type": "HE3_CANISTER", "price": 50, "quantity": 1}
    }, headers=headers_b)
    
    current_tick = wait_for_execution(current_tick)
    
    print("Alice buying He3...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "BUY", 
        "data": {"item_type": "HE3_CANISTER", "max_price": 60}
    }, headers=headers_a)
    
    current_tick = wait_for_execution(current_tick)
    
    # Alice claims pickup
    print("Alice claiming pickups...")
    requests.post(f"{BASE_URL}/api/market/pickup", headers=headers_a)
    
    # Check Alice's inventory
    resp_inv = requests.get(f"{BASE_URL}/inventory", headers=headers_a)
    alice_inv = resp_inv.json()
    print(f"DEBUG: Alice's Inventory: {alice_inv}")
    item = next((i for i in alice_inv if i['type'] == 'HE3_CANISTER'), None)
    item_data = item.get('data') or {} if item else {}
    if item and item_data.get('fill_level') == 77:
        print("SUCCESS: Market trade preserved metadata!")
    else:
        print(f"FAILED: Market metadata mismatch. Got: {item.get('data') if item else 'None'}")
        return

    print("--- ALL TESTS PASSED ---")

if __name__ == "__main__":
    test_metadata_and_transfer()
