import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///terminal_frontier.db"
engine = create_engine(DB_PATH)

def test_squad_chat():
    print("--- STARTING SQUAD CHAT VERIFICATION ---")
    
    # Login Agent A
    name_a = f"SquadA-{int(time.time())}"
    resp_a = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_a})
    resp_a.raise_for_status()
    agent_a = resp_a.json()
    headers_a = {"X-API-KEY": agent_a['api_key']}
    print(f"Logged in Sender A: {agent_a['name']} (ID: {agent_a['agent_id']})")
    
    # Login Agent B
    name_b = f"SquadB-{int(time.time())}"
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": name_b})
    resp_b.raise_for_status()
    agent_b = resp_b.json()
    headers_b = {"X-API-KEY": agent_b['api_key']}
    print(f"Logged in Receiver B: {agent_b['name']} (ID: {agent_b['agent_id']})")
    
    # Put both in the same squad
    squad_id = 999
    print(f"Putting both agents in Squad {squad_id} and moving Agent B far away...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET squad_id = :sq WHERE id IN (:id1, :id2)"), {"sq": squad_id, "id1": agent_a['agent_id'], "id2": agent_b['agent_id']})
        # Move agent B far away so LOCAL chat wouldn't reach
        conn.execute(text("UPDATE agents SET q = 100, r = 100 WHERE id = :id"), {"id": agent_b['agent_id']})
        conn.commit()
    
    # Agent A sends SQUAD chat message
    test_msg = f"Squad secret! Time={time.time()}"
    print(f"Agent A sending SQUAD message: '{test_msg}'")
    chat_resp = requests.post(f"{BASE_URL}/api/chat", json={
        "message": test_msg,
        "channel": "SQUAD"
    }, headers=headers_a)
    chat_resp.raise_for_status()
    print("Agent A sent SQUAD message successfully.")
    
    # Agent B reads perception packet
    print("Agent B checking perception...")
    perc_resp = requests.get(f"{BASE_URL}/api/perception", headers=headers_b)
    perc_resp.raise_for_status()
    data = perc_resp.json()
    
    comms = data['content'].get('comms', [])
    print(f"Agent B received {len(comms)} comms messages in perception.")
    
    message_found = any(m['message'] == test_msg and m['sender'] == agent_a['name'] for m in comms)
    
    if message_found:
        print("SUCCESS: SQUAD chat message verified!")
    else:
        print("FAILED: Message not found in Agent B's perception.")
        print(f"Comms dump: {comms}")

if __name__ == "__main__":
    test_squad_chat()
