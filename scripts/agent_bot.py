import requests
import time
import random

# CONFIGURATION
API_BASE = "http://localhost:8001/api" # Use 8001 for Demo, 8080 for Production
API_KEY = "YOUR_API_KEY_HERE"

def run_agent_loop():
    print(f"--- AGENT UPLINK STARTED ---")
    headers = {"X-API-KEY": API_KEY}
    
    while True:
        try:
            # 1. Perception Step
            print("\n[Perception] Scanning surrounding hexes...")
            resp = requests.get(f"{API_BASE}/perception", headers=headers)
            if resp.status_code != 200:
                print(f"Error: {resp.status_code} - {resp.text}")
                break
                
            data = resp.json()
            status = data['content']['agent_status']
            env = data['content']['environment']
            
            print(f"Status: HP {status['structure']} | NRG {status['capacitor']} | Pos: {status['location']}")
            
            # 2. Decision Logic (Simple Random Move)
            q, r = status['location']['q'], status['location']['r']
            target_q = q + random.choice([-1, 0, 1])
            target_r = r + random.choice([-1, 0, 1])
            
            print(f"[Decision] Moving to ({target_q}, {target_r})...")
            
            # 3. Intent Step
            action_data = {
                "action_type": "MOVE",
                "data": {"target_q": target_q, "target_r": target_r}
            }
            submit_resp = requests.post(f"{API_BASE}/intent", json=action_data, headers=headers)
            print(f"[Intent] Result: {submit_resp.json()['status']}")
            
            # 4. Wait for Tick
            print("[System] Waiting for next network tick...")
            time.sleep(5)
            
            # 5. Feedback Step
            log_resp = requests.get(f"{API_BASE}/agent_logs", headers=headers)
            logs = log_resp.json()
            if logs:
                last_log = logs[0]
                print(f"[Feedback] Last Action: {last_log['event']} at {last_log['time']}")

        except Exception as e:
            print(f"Uplink Error: {e}")
            break

if __name__ == "__main__":
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please set your API_KEY from the dashboard!")
    else:
        run_agent_loop()
