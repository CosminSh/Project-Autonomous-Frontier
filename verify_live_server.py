import requests
import json

LIVE_URL = "https://terminal-frontier.pixek.xyz"

def test_live_health():
    print(f"Checking Live Server: {LIVE_URL}")
    try:
        # 1. Health check
        r = requests.get(f"{LIVE_URL}/api/health")
        print(f"Health: {r.status_code} - {r.json()}")
        
        # 2. Wiki manual (newly added)
        r = requests.get(f"{LIVE_URL}/api/wiki/manual")
        print(f"Wiki Manual: {r.status_code}")
        if r.status_code == 200:
            print(f"Found {len(r.json())} manual sections.")
        else:
            print(f"Wiki Manual failed: {r.text}")

        # 3. Market Orders
        r = requests.get(f"{LIVE_URL}/api/market")
        print(f"Market Orders: {r.status_code}")
        if r.status_code == 200:
             print(f"Found {len(r.json())} market orders.")

        print("\n--- Live Server Basic Verification Complete ---")
    except Exception as e:
        print(f"Verification Error: {e}")

if __name__ == "__main__":
    test_live_health()
