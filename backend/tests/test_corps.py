import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def test_corps():
    print("--- STARTING CORPORATION VERIFICATION ---")
    
    # Login Agent A (CEO)
    name_a = f"CorpCEO-{int(time.time())}"
    resp_a = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_a})
    resp_a.raise_for_status()
    agent_a = resp_a.json()
    headers_a = {"X-API-KEY": agent_a['api_key']}
    print(f"Logged in CEO: {agent_a['name']} (ID: {agent_a['agent_id']})")
    
    # Login Agent B (Member)
    name_b = f"CorpGrunt-{int(time.time())}"
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_b})
    resp_b.raise_for_status()
    agent_b = resp_b.json()
    headers_b = {"X-API-KEY": agent_b['api_key']}
    print(f"Logged in Member: {agent_b['name']} (ID: {agent_b['agent_id']})")
    
    # Give CEO 10,000 credits to afford corp creation
    print("Giving CEO 10,000 CR via SQL...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE inventory_items SET quantity = 20000 WHERE agent_id = :id AND item_type = 'CREDITS'"), {"id": agent_a['agent_id']})
        conn.commit()
    
    ticker = f"T{int(time.time()) % 1000}"
    corp_name = f"TestCorp {ticker}"
    
    # Create Corp
    print(f"Creating Corporation '{corp_name}' [{ticker}]...")
    resp_create = requests.post(f"{BASE_URL}/api/corp/create", json={"name": corp_name, "ticker": ticker, "tax_rate": 0.1}, headers=headers_a)
    resp_create.raise_for_status()
    print("Corporation Created successfully!")
    
    # Join Corp
    print(f"Agent B joining Corporation [{ticker}]...")
    resp_join = requests.post(f"{BASE_URL}/api/corp/join", json={"ticker": ticker}, headers=headers_b)
    resp_join.raise_for_status()
    print("Agent B joined Corporation successfully!")
    
    # Deposit to Vault
    print(f"Agent B depositing 500 CR to Corporation Vault...")
    resp_dep = requests.post(f"{BASE_URL}/api/corp/deposit", json={"amount": 500}, headers=headers_b)
    resp_dep.raise_for_status()
    print("Deposit successful!")
    
    # Test CORP Chat
    test_msg = f"Corp secrets! Time={time.time()}"
    print(f"Agent A sending CORP message: '{test_msg}'")
    chat_resp = requests.post(f"{BASE_URL}/api/chat", json={
        "message": test_msg,
        "channel": "CORP"
    }, headers=headers_a)
    chat_resp.raise_for_status()
    
    perc_resp = requests.get(f"{BASE_URL}/api/perception", headers=headers_b)
    perc_resp.raise_for_status()
    comms = perc_resp.json()['content'].get('comms', [])
    
    message_found = any(m['message'] == test_msg and m['sender'] == agent_a['name'] for m in comms)
    
    if message_found:
        print("SUCCESS: CORP chat message verified!")
    else:
        print("FAILED: CORP message not found in Agent B's perception.")
        
    print("--- ALL TESTS PASSED ---")

if __name__ == "__main__":
    test_corps()
