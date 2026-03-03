import requests
import time

BASE_URL = "http://localhost:8000"

def test_comms():
    print("--- STARTING COMMS VERIFICATION ---")
    
    # Login Agent A
    resp_a = requests.post(f"{BASE_URL}/auth/guest")
    resp_a.raise_for_status()
    agent_a = resp_a.json()
    headers_a = {"X-API-KEY": agent_a['api_key']}
    print(f"Logged in Sender A: {agent_a['name']} (ID: {agent_a['agent_id']})")
    
    # Login Agent B
    b_name = f"Receiver-B-{int(time.time())}"
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": b_name})
    resp_b.raise_for_status()
    agent_b = resp_b.json()
    headers_b = {"X-API-KEY": agent_b['api_key']}
    print(f"Logged in Receiver B: {agent_b['name']} (ID: {agent_b['agent_id']})")
    
    # Agent A sends LOCAL chat message
    test_msg = f"Hello from Agent A! Time={time.time()}"
    print(f"Agent A sending LOCAL message: '{test_msg}'")
    chat_resp = requests.post(f"{BASE_URL}/api/chat", json={
        "message": test_msg,
        "channel": "LOCAL"
    }, headers=headers_a)
    chat_resp.raise_for_status()
    print("Agent A sent message successfully.")
    
    # Agent B reads perception packet
    print("Agent B checking perception...")
    perc_resp = requests.get(f"{BASE_URL}/api/perception", headers=headers_b)
    perc_resp.raise_for_status()
    data = perc_resp.json()
    
    comms = data['content'].get('comms', [])
    print(f"Agent B received {len(comms)} comms messages in perception.")
    
    message_found = any(m['message'] == test_msg and m['sender'] == agent_a['name'] for m in comms)
    
    if message_found:
        print("SUCCESS: LOCAL chat message verified!")
    else:
        print("FAILED: Message not found in Agent B's perception.")
        print(f"Comms dump: {comms}")

if __name__ == "__main__":
    test_comms()
