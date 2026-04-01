import requests
import json
import sys
import os
from pathlib import Path

# Load API Key from .env if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith("TF_API_KEY="):
                os.environ["TF_API_KEY"] = line.split("=")[1].strip()

API_KEY = os.getenv("TF_API_KEY", "YOUR_API_KEY")
BASE_URL = "https://terminal-frontier.pixek.xyz"

def fetch_logs():
    headers = {"X-API-KEY": API_KEY}
    url = f"{BASE_URL}/api/agent_logs"
    
    print(f"Connecting to {BASE_URL}...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logs = response.json()
        
        print(f"\nFound {len(logs)} entries for your agent.\n")
        print(f"{'TIMESTAMP':<25} | {'EVENT':<15} | {'DETAILS'}")
        print("-" * 100)
        
        # Filter for combat related logs first
        combat_events = ["COMBAT_HIT", "COMBAT_MISS", "COMBAT_STOPPED", "DEATH", "MINING_STOPPED"]
        
        for entry in logs:
            event = entry.get("event", "UNKNOWN")
            time = entry.get("time", "")[:19].replace("T", " ")
            details = json.dumps(entry.get("details", {}))
            
            # Highlight combat events
            prefix = ">>> " if event in combat_events else "    "
            print(f"{prefix}{time:<25} | {event:<15} | {details}")
            
    except Exception as e:
        print(f"Error fetching logs: {e}")

if __name__ == "__main__":
    if API_KEY == "YOUR_API_KEY":
        print("Please edit the script and set your API_KEY first.")
        sys.exit(1)
    fetch_logs()
