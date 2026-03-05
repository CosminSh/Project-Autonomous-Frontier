import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

from models import Base

def wait_for_next_tick(current_tick):
    target = current_tick + 2
    print(f"Waiting for tick {target} to ensure intent was fully crunched...")
    while True:
        resp = requests.get(f"{BASE_URL}/state")
        state = resp.json()
        if state['tick'] >= target:
            print(f"Server reached tick {state['tick']}, proceeding.")
            return state['tick']
        time.sleep(1)

def test_market_pickups():
    print("--- STARTING MARKET PICKUP VERIFICATION ---")
    Base.metadata.create_all(engine)
    
    # Get initial tick
    current_tick = requests.get(f"{BASE_URL}/state").json()['tick']
    
    # 1. Login Agent A (Seller)
    name_a = f"Seller-{int(time.time())}"
    resp_a = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_a})
    resp_a.raise_for_status()
    agent_a = resp_a.json()
    headers_a = {"X-API-KEY": agent_a['api_key']}
    print(f"Logged in Seller: {agent_a['name']} (ID: {agent_a['agent_id']})")
    
    # 2. Login Agent B (Buyer)
    name_b = f"Buyer-{int(time.time())}"
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_b})
    resp_b.raise_for_status()
    agent_b = resp_b.json()
    headers_b = {"X-API-KEY": agent_b['api_key']}
    print(f"Logged in Buyer: {agent_b['name']} (ID: {agent_b['agent_id']})")
    
    # 3. Setup Inventories
    print("Setting up inventories and moving buyer to market...")
    with engine.connect() as conn:
        # Give Seller 5 IRON_ORE
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'IRON_ORE', 5)"), {"id": agent_a['agent_id']})
        # Give Buyer 5000 CREDITS
        conn.execute(text("UPDATE inventory_items SET quantity = 5000 WHERE agent_id = :id AND item_type = 'CREDITS'"), {"id": agent_b['agent_id']})
        
        # Ensure a MARKET station exists at (0,0) for the buyer to claim from
        conn.execute(text("UPDATE world_hexes SET is_station=1, station_type='MARKET' WHERE q=0 AND r=0"))
        
        # Move both to (0,0) just in case
        conn.execute(text("UPDATE agents SET q=0, r=0 WHERE id IN (:ida, :idb)"), {"ida": agent_a['agent_id'], "idb": agent_b['agent_id']})
        conn.commit()
    
    # 4. Seller Lists Item
    print("Seller listing 5 IRON_ORE for 10 Credits each...")
    list_payload = {"action_type": "LIST", "data": {"item_type": "IRON_ORE", "price": 10, "quantity": 5}}
    resp_list = requests.post(f"{BASE_URL}/api/intent", json=list_payload, headers=headers_a)
    resp_list.raise_for_status()
    
    current_tick = wait_for_next_tick(current_tick)
    
    # 5. Buyer Buys Item
    print("Buyer purchasing 1 IRON_ORE...")
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "BUY", "data": {"item_type": "IRON_ORE", "max_price": 15}}, headers=headers_b)
        
    current_tick = wait_for_next_tick(current_tick)
    
    # 6. Check Pickups Endpoint
    print("Checking Buyer's pending pickups...")
    resp_pickups = requests.get(f"{BASE_URL}/api/market/pickups", headers=headers_b)
    resp_pickups.raise_for_status()
    pickups = resp_pickups.json()
    print(f"Pickups found: {pickups}")
    
    if not any(p['item'] == 'IRON_ORE' and p['qty'] == 1 for p in pickups):
        print("FAILED: Buyer does not have 1 IRON_ORE in pending pickups.")
        return
        
    # 7. Check Seller Credits
    print("Checking Seller's Credits...")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT quantity FROM inventory_items WHERE agent_id = :id AND item_type = 'CREDITS'"), {"id": agent_a['agent_id']}).fetchone()
        if res and res[0] >= 10:
            print(f"SUCCESS: Seller instantly received credits. Total Credits: {res[0]}")
        else:
            print(f"FAILED: Seller did not receive credits.")
            return

    # 8. Buyer Claims Pickups
    print("Buyer claiming pickups...")
    resp_claim = requests.post(f"{BASE_URL}/api/market/pickup", headers=headers_b)
    resp_claim.raise_for_status()
    print(f"Claim response: {resp_claim.json()}")
    
    # 9. Verify Buyer Inventory
    print("Verifying Buyer Inventory...")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT quantity FROM inventory_items WHERE agent_id = :id AND item_type = 'IRON_ORE'"), {"id": agent_b['agent_id']}).fetchone()
        if res and res[0] >= 1:
            print("SUCCESS: Buyer successfully claimed IRON_ORE into inventory.")
        else:
            print("FAILED: Buyer did not receive IRON_ORE in inventory.")
            
    print("--- ALL TESTS PASSED ---")

if __name__ == "__main__":
    test_market_pickups()
