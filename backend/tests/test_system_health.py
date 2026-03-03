import requests
import time
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DB_PATH = "sqlite:///backend/verify.db"
engine = create_engine(DB_PATH)

def test_system_health():
    print("--- STARTING SYSTEM HEALTH ADVISORY VERIFICATION ---")
    
    # 1. Guest Login
    print("Logging in as TestAgent...")
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"name": "HealthTest", "email": "health@test.com"})
    agent_data = resp.json()
    api_key = agent_data['api_key']
    agent_id = agent_data['agent_id']
    headers = {"X-API-KEY": api_key}

    # 2. Artificially set high Wear & Tear in DB
    print(f"Set Wear & Tear to 100% for Agent {agent_id}...")
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET wear_and_tear = 100.0 WHERE id = :id"), {"id": agent_id})
        conn.commit()

    # 3. Fetch Perception and check for Advisories
    print("Fetching Perception...")
    resp = requests.get(f"{BASE_URL}/api/perception", headers=headers)
    mcp = resp.json()
    
    content = mcp.get("content", {})
    status = content.get("agent_status", {})
    advisories = content.get("system_advisories", [])
    
    print(f"Current Wear: {status.get('wear_and_tear')}%")
    
    found_warning = False
    for adv in advisories:
        if adv["type"] == "SYSTEM_DEGRADATION":
            print(f"ADVISORY FOUND: [{adv['severity']}] {adv['message']}")
            print(f"REQUIREMENTS: {adv['requirements']}")
            found_warning = True
            
    if found_warning:
        print("\n--- SYSTEM HEALTH ADVISORY VERIFIED SUCCESSFUL ---")
    else:
        print("\nFAILED: No System Health Advisory found in perception packet.")
        exit(1)

if __name__ == "__main__":
    try:
        test_system_health()
    except Exception as e:
        print(f"Verification Failed: {e}")
        exit(1)
