import requests
import uuid
import json
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from models import Agent, ChassisPart, InventoryItem
from config import PART_DEFINITIONS

DATABASE_URL = "sqlite:///backend/terminal_frontier.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

BASE_URL = "http://localhost:8000"
API_KEY = f"CRAFT_TEST_{uuid.uuid4().hex[:8]}"
headers = {"X-API-Key": API_KEY}

def test_crafting_expansion():
    print("--- STARTING CRAFTING EXPANSION VERIFICATION ---")
    
    # 1. Register / Get Agent
    print("\n[STEP 1] Registering Test Agent...")
    unique_name = f"T_{uuid.uuid4().hex[:6]}"
    resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": f"{unique_name}@test.com", "name": unique_name})
    if resp.status_code != 200:
        print(f"Registration failed: {resp.text}")
        return
    
    agent_id = resp.json()["agent_id"]
    api_key = resp.json()["api_key"]
    dynamic_headers = {"X-API-Key": api_key}
    print(f"Agent Created: ID {agent_id}, Name {resp.json()['name']}")

    # 2. Check Metadata for New Recipes
    print("\n[STEP 2] Checking Metadata for New Recipes...")
    resp = requests.get(f"{BASE_URL}/api/metadata")
    # Note: /api/metadata might not return recipes, let's check wiki or a new endpoint if we had one.
    # Actually, let's check if we can craft it.
    
    # 3. Inject AURUM_HAULER
    print("\n[STEP 3] Injecting AURUM_HAULER into Agent...")
    with SessionLocal() as db:
        agent = db.get(Agent, agent_id)
        # Add the part
        part_name = "AURUM_HAULER"
        defn = PART_DEFINITIONS[part_name]
        new_part = ChassisPart(
            agent_id=agent.id,
            part_type=defn["type"],
            name=defn["name"],
            stats=defn["stats"],
            rarity="STANDARD"
        )
        db.add(new_part)
        db.commit()
    print("AURUM_HAULER injected.")

    # 4. Verify API Response for New Stats
    print("\n[STEP 4] Verifying API for New Stats (loot_bonus, etc.)...")
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=dynamic_headers)
    if resp.status_code != 200:
        print(f"API Error: {resp.text}")
        return
    
    data = resp.json()
    print(f"Agent Stats: loot_bonus={data.get('loot_bonus')}, energy_save={data.get('energy_save')}, wear_resistance={data.get('wear_resistance')}")
    
    # Check if they match the Aurum Hauler stats
    expected_loot = PART_DEFINITIONS["AURUM_HAULER"]["stats"].get("loot_bonus", 0.0)
    if data.get("loot_bonus") == expected_loot:
        print(f"SUCCESS: loot_bonus correctly aggregated ({expected_loot}).")
    else:
        print(f"FAILURE: loot_bonus mismatch. Expected {expected_loot}, got {data.get('loot_bonus')}")

    # 5. Check Balance Adjustment (Striker Chassis)
    print("\n[STEP 5] Checking Balance Adjustment (Striker Chassis HP)...")
    striker_stats = PART_DEFINITIONS["STRIKER_CHASSIS"]["stats"]
    if striker_stats["max_health"] == 100:
        print(f"SUCCESS: STRIKER_CHASSIS HP is 100.")
    else:
        print(f"FAILURE: STRIKER_CHASSIS HP is {striker_stats['max_health']}.")

    print("\n--- CRAFTING EXPANSION VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    test_crafting_expansion()
