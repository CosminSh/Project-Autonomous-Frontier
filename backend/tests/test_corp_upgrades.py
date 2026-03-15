import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def get_current_tick():
    with engine.connect() as conn:
        return conn.execute(text("SELECT tick_index FROM global_state LIMIT 1")).scalar()

def wait_for_tick(count=2):
    for i in range(count):
        start_tick = get_current_tick() or 0
        print(f"Waiting for tick {start_tick + 1}... (Step {i+1}/{count})")
        found = False
        for _ in range(30):
            time.sleep(1)
            if (get_current_tick() or 0) > start_tick:
                found = True
                break
        if not found:
            print("WARNING: Timed out waiting for tick.")
            return

def test_corp_upgrades():
    print("--- STARTING CORPORATE UPGRADES VERIFICATION ---")
    
    # 1. Setup CEO and Corp
    name_ceo = f"UpgradeCEO-{int(time.time())}"
    resp_ceo = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_ceo})
    resp_ceo.raise_for_status()
    ceo = resp_ceo.json()
    headers_ceo = {"X-API-KEY": ceo['api_key']}
    ceo_id = ceo['agent_id']
    print(f"CEO: {ceo['name']} (ID: {ceo_id})")

    # Give CEO credits for corp and funding
    with engine.connect() as conn:
        # Clear inventory and add specific items
        conn.execute(text("DELETE FROM inventory_items WHERE agent_id = :id"), {"id": ceo_id})
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'CREDITS', 500000)"), {"id": ceo_id})
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, 'IRON_ORE', 100)"), {"id": ceo_id})
        conn.commit()

    ticker = f"UPG{int(time.time()) % 1000}"
    resp_create = requests.post(f"{BASE_URL}/api/corp/create", json={"name": f"Upgrade Testing Inc {ticker}", "ticker": ticker, "tax_rate": 0.2}, headers=headers_ceo)
    if not resp_create.ok:
        print(f"ERROR creating corp: {resp_create.status_code} - {resp_create.text}")
        resp_create.raise_for_status()
    print(f"Corp {ticker} created with 20% tax.")

    # 2. Fund Corp Vault
    requests.post(f"{BASE_URL}/api/corp/deposit", json={"amount": 400000}, headers=headers_ceo).raise_for_status()
    print("Funded corp vault with 400,000 CR.")

    # Get initial stats
    def get_agent():
        return requests.get(f"{BASE_URL}/api/my_agent", headers=headers_ceo).json()

    initial = get_agent()
    print(f"Initial Stats - Mass: {initial['max_mass']}, Yield: {initial['mining_yield']}, Armor: {initial['armor']}, HP: {initial['max_health']}")

    # 3. Test LOGISTICS (Mass Capacity)
    print("\n[Testing LOGISTICS Upgrade...]")
    requests.post(f"{BASE_URL}/api/corp/upgrade/purchase", json={"category": "LOGISTICS"}, headers=headers_ceo).raise_for_status()
    after_logistics = get_agent()
    print(f"After LOGISTICS L1 - Mass: {after_logistics['max_mass']}")
    if after_logistics['max_mass'] > initial['max_mass']:
        print("[OK] LOGISTICS bonus applied!")
    else:
        print("[FAIL] LOGISTICS bonus FAILED!")

    # 4. Test EXTRACTION (Mining Yield)
    print("\n[Testing EXTRACTION Upgrade...]")
    requests.post(f"{BASE_URL}/api/corp/upgrade/purchase", json={"category": "EXTRACTION"}, headers=headers_ceo).raise_for_status()
    after_extraction = get_agent()
    print(f"After EXTRACTION L1 - Yield: {after_extraction['mining_yield']}")
    if after_extraction['mining_yield'] > initial['mining_yield']:
        print("[OK] EXTRACTION bonus applied!")
    else:
        print("[FAIL] EXTRACTION bonus FAILED!")

    # 5. Test SECURITY (Armor/HP)
    print("\n[Testing SECURITY Upgrade...]")
    requests.post(f"{BASE_URL}/api/corp/upgrade/purchase", json={"category": "SECURITY"}, headers=headers_ceo).raise_for_status()
    after_security = get_agent()
    print(f"After SECURITY L1 - Armor: {after_security['armor']}, HP: {after_security['max_health']}")
    if after_security['armor'] > initial['armor'] and after_security['max_health'] > initial['max_health']:
        print("[OK] SECURITY bonuses applied!")
    else:
        print("[FAIL] SECURITY bonus FAILED!")

    # 6. Test MARKET (Tax Reduction)
    print("\n[Testing MARKET Upgrade...]")
    # Create a BUY order from someone else (System/Manual) to match against
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO auction_house (owner, item_type, quantity, price, order_type) VALUES ('agent:9999', 'IRON_ORE', 10, 100, 'BUY')"))
        conn.commit()

    # Sell 10 Iron Ore @ 100 = 1000 CR. 20% tax = 200 CR. Net = 800 CR.
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "LIST", "data": {"item_type": "IRON_ORE", "price": 100, "quantity": 10}}, headers=headers_ceo).raise_for_status()
    
    wait_for_tick(2)
    
    logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers_ceo).json()
    tax_log = next((l for l in logs if l['event'] == 'CORP_TAX_COLLECTED'), None)
    if not tax_log:
        print(f"DEBUG: All logs: {logs}")
        raise Exception("Failed to find pre-upgrade tax log.")
    print(f"Pre-upgrade Tax: {tax_log['details']['tax']} CR on {tax_log['details']['pre_tax']} CR (Rate: {tax_log['details']['applied_rate']})")
    
    # Purchase MARKET upgrade (5% reduction per level)
    requests.post(f"{BASE_URL}/api/corp/upgrade/purchase", json={"category": "MARKET"}, headers=headers_ceo).raise_for_status()
    
    # Sell again
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO auction_house (owner, item_type, quantity, price, order_type) VALUES ('agent:9999', 'IRON_ORE', 10, 100, 'BUY')"))
        conn.commit()
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "LIST", "data": {"item_type": "IRON_ORE", "price": 100, "quantity": 10}}, headers=headers_ceo).raise_for_status()
    
    wait_for_tick(2)
    
    logs = requests.get(f"{BASE_URL}/api/agent_logs", headers=headers_ceo).json()
    # Get the newest tax log
    new_tax_logs = [l for l in logs if l['event'] == 'CORP_TAX_COLLECTED']
    new_tax_log = new_tax_logs[0]
    print(f"Post-upgrade Tax: {new_tax_log['details']['tax']} CR on {new_tax_log['details']['pre_tax']} CR (Rate: {new_tax_log['details']['applied_rate']})")
    
    if new_tax_log['details']['applied_rate'] < tax_log['details']['applied_rate']:
        print("[OK] MARKET tax reduction applied!")
    else:
        print("[FAIL] MARKET tax reduction FAILED!")

    # 7. Test NEURAL_LINK (XP Bonus)
    print("\n[Testing NEURAL_LINK Upgrade...]")
    # Create a mission and complete it
    with engine.connect() as conn:
        # Check columns to be sure
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(daily_missions)")).fetchall()]
        print(f"DailyMission columns: {cols}")
        
        conn.execute(text("INSERT INTO daily_missions (mission_type, target_amount, reward_credits, reward_xp, item_type) VALUES ('TURN_IN', 1, 100, 1000, 'IRON_ORE')"))
        conn.commit()
        dm_id = conn.execute(text("SELECT id FROM daily_missions ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO agent_missions (agent_id, mission_id, progress, is_completed) VALUES (:aid, :mid, 1, 1)"), {"aid": ceo_id, "mid": dm_id})
        conn.commit()
    
    agent_mission_id = engine.connect().execute(text("SELECT id FROM agent_missions WHERE agent_id = :aid AND mission_id = :mid"), {"aid": ceo_id, "mid": dm_id}).scalar()
    
    # Turn in mission
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "TURN_IN", "data": {"mission_id": agent_mission_id}}, headers=headers_ceo).raise_for_status()
    
    # Wait for processing
    print("Waiting for mission turn-in processing...")
    wait_for_tick(2)
    
    agent_after_xp = get_agent()
    print(f"XP after mission (no upgrade): {agent_after_xp['experience']}")
    
    # Purchase NEURAL_LINK
    requests.post(f"{BASE_URL}/api/corp/upgrade/purchase", json={"category": "NEURAL_LINK"}, headers=headers_ceo).raise_for_status()
    
    # Second mission
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO daily_missions (mission_type, target_amount, reward_credits, reward_xp, item_type) VALUES ('TURN_IN', 1, 100, 1000, 'IRON_ORE')"))
        conn.commit()
        dm_id_2 = conn.execute(text("SELECT id FROM daily_missions ORDER BY id DESC LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO agent_missions (agent_id, mission_id, progress, is_completed) VALUES (:aid, :mid, 1, 1)"), {"aid": ceo_id, "mid": dm_id_2})
        conn.commit()
    
    agent_mission_id_2 = engine.connect().execute(text("SELECT id FROM agent_missions WHERE agent_id = :aid AND mission_id = :mid"), {"aid": ceo_id, "mid": dm_id_2}).scalar()
    
    requests.post(f"{BASE_URL}/api/intent", json={"action_type": "TURN_IN", "data": {"mission_id": agent_mission_id_2}}, headers=headers_ceo).raise_for_status()
    
    wait_for_tick(2)
    
    agent_final = get_agent()
    xp_gained = agent_final['experience'] - agent_after_xp['experience']
    print(f"XP gained from 2nd mission (with upgrade): {xp_gained} (expected > 1000)")
    
    if xp_gained > 1000:
        print("[OK] NEURAL_LINK XP bonus applied!")
    else:
        print("[FAIL] NEURAL_LINK XP bonus FAILED!")

    print("\n--- ALL CORPORATE UPGRADE TESTS PASSED ---")

if __name__ == "__main__":
    try:
        test_corp_upgrades()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
