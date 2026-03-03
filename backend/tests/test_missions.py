import asyncio
import os
import sys
import requests
import time

from sqlalchemy import select, text
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
WAIT_TIME = 25 


def test_missions():
    import requests
    from sqlalchemy import create_engine, text
    DB_PATH = "sqlite:///./terminal_frontier.db"
    if not os.path.exists("./terminal_frontier.db"):
        print("Required terminal_frontier.db not found. Run backend first.")
        return
        
    engine = create_engine(DB_PATH)
    
    print("--- STARTING MISSIONS VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as guest...")
    resp = requests.post(f"{BASE_URL}/auth/guest", json={})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return
        
    auth_data = resp.json()
    api_key = auth_data['api_key']
    agent_id = auth_data['agent_id']
    headers = {"X-API-KEY": api_key}
    print(f"Logged in as {auth_data['name']} (Agent ID: {agent_id})")

    # 2. Wait for a tick to let the heartbeat generate missions
    print(f"Waiting {WAIT_TIME}s for Phase Cycle (so heartbeat generates missions)...")
    time.sleep(WAIT_TIME)

    # 3. Check Missions
    resp = requests.get(f"{BASE_URL}/api/missions", headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch missions: {resp.text}")
        return
        
    missions = resp.json()
    print(f"Fetched {len(missions)} daily missions.")
    if len(missions) == 0:
        print("FAILED: No missions generated.")
        return
        
    turn_in = next((m for m in missions if m['type'] == 'TURN_IN'), None)
    if not turn_in:
        print("No TURN_IN mission found. Ensure they are generated randomly.")
        return
        
    print(f"Found TURN_IN mission. Need {turn_in['target_amount']} of {turn_in['item_type']}. Reward: {turn_in['reward_credits']} CR.")
    
    # 4. Inject items into DB for the agent
    print(f"\nAdding {turn_in['target_amount']} {turn_in['item_type']} to inventory via SQL...")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO inventory_items (agent_id, item_type, quantity) VALUES (:id, :type, :qty)"), 
                     {"id": agent_id, "type": turn_in['item_type'], "qty": turn_in['target_amount']})
        conn.commit()
        
    # 5. Turn In
    print(f"Turning in {turn_in['target_amount']} {turn_in['item_type']}...")
    turn_in_resp = requests.post(f"{BASE_URL}/api/missions/turn_in", json={
        "mission_id": turn_in['id'],
        "quantity": turn_in['target_amount']
    }, headers=headers)
    
    if turn_in_resp.status_code == 200:
        res_data = turn_in_resp.json()
        print(f"Turn In Response: {res_data['message']}")
        if res_data['is_completed']:
            print("SUCCESS: Mission marked as completed!")
    else:
        print(f"Failed to turn in: {turn_in_resp.text}")
        return
        
    # 6. Verify Credits Received
    perc_resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    inv = perc_resp.json()['content']['agent_status']['inventory']
    credits_item = next((i for i in inv if i['type'] == 'CREDITS'), None)
    credits_qty = credits_item['quantity'] if credits_item else 0
    print(f"Agent Credits Check: {credits_qty}")
    if credits_qty >= turn_in['reward_credits']:
         print("SUCCESS: Credits granted!")
    else:
         print("FAILED: Expected credits not granted.")


if __name__ == "__main__":
    test_missions()
