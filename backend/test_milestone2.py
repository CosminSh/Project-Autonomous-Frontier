import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///demo.db"
engine = create_engine(DB_PATH)

def test_milestone2():
    print("--- STARTING MILESTONE 2 VERIFICATION ---")
    
    # 1. Guest Login
    print("\n[1] Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/guest")
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (ID: {agent_id})")

    # 2. Test Auto-Trader (Persistent BUY order)
    print("\n[2] Testing Auto-Trader: Persistent BUY Order...")
    # Ensure we have credits
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "MOVE", "data": {"target_q": 0, "target_r": 0}}, headers=headers)
    
    # Place BUY order for GOLD_INGOT at 50 credits
    print("Placing BUY order for GOLD_INGOT at 50 credits...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "BUY",
        "data": {"item_type": "GOLD_INGOT", "max_price": 50}
    }, headers=headers)
    
    print("Waiting for tick (30s)...")
    time.sleep(30)
    
    # Check if order is on Auction House
    with engine.connect() as conn:
        order = conn.execute(text("SELECT * FROM auction_house WHERE item_type='GOLD_INGOT' AND order_type='BUY'")).first()
        if order:
            print(f"VERIFIED: Persistent BUY order created for {order.item_type} at {order.price}")
        else:
            print("FAILED: BUY order not found on Market.")

    # 3. Test Auto-Trader (Instant Match on LIST)
    print("\n[3] Testing Auto-Trader: Instant Match on LIST...")
    # Create another agent to SELL
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agents (name, q, r, owner, api_key, structure, max_structure, capacitor) 
            VALUES ('Seller-Bot', 0, 0, 'dummy', 'seller-key', 100, 100, 100)
        """))
        # Add item to seller
        seller_id = conn.execute(text("SELECT id FROM agents WHERE name='Seller-Bot'")).scalar()
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'GOLD_INGOT', 1)"), {"id": seller_id})
        conn.commit()

    print("Seller-Bot listing GOLD_INGOT at 40 credits...")
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "LIST",
        "data": {"item_type": "GOLD_INGOT", "price": 40, "quantity": 1}
    }, headers={"X-API-KEY": "seller-key"})

    print("Waiting for tick (30s)...")
    time.sleep(30)
    
    # Verify trade resolved
    with engine.connect() as conn:
        buyer_item = conn.execute(text("SELECT quantity FROM inventory_items WHERE agent_id = :id AND item_type='GOLD_INGOT'"), {"id": agent_id}).scalar()
        order_exists = conn.execute(text("SELECT count(*) FROM auction_house WHERE item_type='GOLD_INGOT'")).scalar()
        
        if buyer_item and buyer_item > 0 and order_exists == 0:
            print("VERIFIED: Instant matching resolved the trade. Buyer received item.")
        else:
            print(f"FAILED: Trade did not resolve as expected. Buyer Item: {buyer_item}, Orders Left: {order_exists}")

    # 4. Test Automated Bounty
    print("\n[4] Testing Automated Bounty...")
    # Increase heat of an agent
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET heat = 6 WHERE id = :id"), {"id": seller_id})
        conn.commit()
    
    print("Waiting for tick (30s) for automated bounty issuance...")
    time.sleep(30)
    
    with engine.connect() as conn:
        bounty = conn.execute(text("SELECT * FROM bounties WHERE target_id = :id AND is_open = 1"), {"id": seller_id}).first()
        if bounty:
            print(f"VERIFIED: Automated bounty issued for Agent {seller_id} (Reward: {bounty.reward})")
        else:
            print("FAILED: Automated bounty not issued.")

    # 5. Test Bounty Claim & Loot Drop
    print("\n[5] Testing Bounty Claim & Loot Drop...")
    # Set up combat: Player at (10,0), Target (Feral) at (10,1)
    # Use Debug API for reliable state update
    requests.get(f"{BASE_URL}/api/debug/teleport?agent_id={agent_id}&q=10&r=0")
    
    with engine.connect() as conn:
        target_id = conn.execute(text("SELECT id FROM agents WHERE is_feral=1")).scalar()
    
    if not target_id:
        print("FAILED: No feral agent found to test combat.")
        return
        
    requests.get(f"{BASE_URL}/api/debug/teleport?agent_id={target_id}&q=10&r=1")
    requests.get(f"{BASE_URL}/api/debug/set_structure?agent_id={target_id}&hp=5")
    
    # Add inventory to feral via direct SQL (fine as it's a new row)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM inventory_items WHERE agent_id=:id"), {"id": target_id})
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'IRON_ORE', 100)"), {"id": target_id})
        # Ensure bounty exists
        conn.execute(text("DELETE FROM bounties WHERE target_id=:id"), {"id": target_id})
        conn.execute(text("INSERT INTO bounties (target_id, reward, is_open) VALUES (:id, 1000, 1)"), {"id": target_id})
        conn.commit()
    
    print(f"Player attacking Feral Agent {target_id} at (10, 1)...")
    resp = requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "ATTACK",
        "data": {"target_id": target_id}
    }, headers=headers)
    print(f"Attack intent submitted: {resp.status_code}")
    
    print("Waiting for tick (30s)...")
    time.sleep(30)
    
    # Check Bounty & Credits
    bounties = requests.get(f"{BASE_URL}/api/bounties").json()
    bounty_open = any(b["target_id"] == target_id for b in bounties)
    
    agent_data = requests.get(f"{BASE_URL}/api/my_agent", headers=headers).json()
    credits = next((i["quantity"] for i in agent_data["inventory"] if i["type"] == "CREDITS"), 0)
    ore = next((i["quantity"] for i in agent_data["inventory"] if i["type"] == "IRON_ORE"), 0)
    
    if not bounty_open and credits >= 1500: # Starting 1000 + 500 (or more if they claimed others)
        print("VERIFIED: Bounty claimed and reward paid.")
    else:
        print(f"FAILED: Bounty status: {bounty_open}, Credits: {credits}")
        
    # Check Loot Drop
    with engine.connect() as conn:
        loot_drop = conn.execute(text("SELECT * FROM loot_drops WHERE q=10 AND r=1")).first()
    
    if loot_drop:
        drop_id = loot_drop[0]
        print(f"VERIFIED: Loot Drop created at (10, 1) with {loot_drop[4]} {loot_drop[3]}")
    else:
        print("FAILED: No loot drop found at death location.")
        return

    # 6. Test Salvage
    print("\n[6] Testing Salvage...")
    # Player is at (10, 0). Move to (10, 1) to salvage
    requests.get(f"{BASE_URL}/api/debug/teleport?agent_id={agent_id}&q=10&r=1")
    
    requests.post(f"{BASE_URL}/api/intent", json={
        "action_type": "SALVAGE",
        "data": {"drop_id": drop_id}
    }, headers=headers)
    
    print("Waiting for tick (30s)...")
    time.sleep(30)
    
    agent_data = requests.get(f"{BASE_URL}/api/my_agent", headers=headers).json()
    new_ore = next((i["quantity"] for i in agent_data["inventory"] if i["type"] == "IRON_ORE"), 0)
    
    with engine.connect() as conn:
        drop_remains = conn.execute(text("SELECT COUNT(*) FROM loot_drops WHERE id=:id"), {"id": drop_id}).scalar()
        
    if new_ore > ore and drop_remains == 0:
        print(f"VERIFIED: Salvage successful. New Ore: {new_ore}")
    else:
        print(f"FAILED: Salvage failed. Ore: {new_ore}, Drop remains: {drop_remains}")

if __name__ == "__main__":
    test_milestone2()
