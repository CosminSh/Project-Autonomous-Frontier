
import requests
import time
import random

BASE_URL = "http://localhost:8000"

def test_solar_mechanics():
    print("--- Testing Solar Energy Mechanics ---")
    
    # 1. Create a guest agent
    resp = requests.post(f"{BASE_URL}/auth/guest")
    if resp.status_code != 200:
        print("Failed to login as guest")
        return
    
    auth_data = resp.json()
    api_key = auth_data["api_key"]
    headers = {"X-API-KEY": api_key}
    
    # 2. Check if agent has starter gear (Scrap Solar Panel)
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    print(f"RAW RESPONSE: {resp.text}")
    agent = resp.json()
    print(f"Agent Name: {agent['name']}")
    
    parts = agent.get("parts", [])
    has_solar = any(p["type"] == "Power" for p in parts)
    print(f"Has Power Part: {has_solar}")
    if has_solar:
        power_part = next(p for p in parts if p["type"] == "Power")
        print(f"Equipped Power Part: {power_part['name']} (Efficiency: {power_part['stats'].get('efficiency')})")

    # 3. Check Solar Intensity at North Pole (0,0)
    # The agent usually starts near (0,0) or at least in a safe zone
    intensity = agent.get("solar_intensity")
    print(f"Solar Intensity at current location: {intensity}%")
    
    # 4. Drain energy to 50
    print("Draining energy to 50 for regen test...")
    requests.post(f"{BASE_URL}/api/debug/set_structure", json={
        "agent_id": agent["id"],
        "capacitor": 50
    })
    
    # 5. Wait for a tick and check energy change at North Pole (100% intensity)
    print("Waiting for energy regeneration cycle (North Pole, 22s)...")
    time.sleep(22)
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent = resp.json()
    new_energy = agent["capacitor"]
    print(f"Energy Change: 50 -> {new_energy} (Diff: {new_energy - 50})")
    if new_energy > 50:
        print("SUCCESS: Energy is regenerating at North Pole.")
    else:
        print("FAILURE: Energy is NOT regenerating at North Pole.")

    # 6. Test Abyssal South (q=50)
    print("\nTeleporting to Abyssal South (q=50, r=0)...")
    requests.post(f"{BASE_URL}/api/debug/teleport", json={
        "agent_id": agent["id"],
        "q": 50,
        "r": 0
    })
    
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent_dark = resp.json()
    intensity_dark = agent_dark.get("solar_intensity")
    print(f"Solar Intensity at Abyssal South: {intensity_dark}%")
    
    if intensity_dark == 0:
        print("SUCCESS: Zero intensity confirmed in Abyssal South.")
    else:
        print(f"FAILURE: Intensity is {intensity_dark}% in Abyssal South (expected 0%).")

    # 7. Check regen in Dark (should be 0 or fuel-cell based)
    print("Waiting for regen cycle in Abyssal South (Darkness, 22s)...")
    requests.post(f"{BASE_URL}/api/debug/set_structure", json={
        "agent_id": agent["id"],
        "capacitor": 10
    })
    time.sleep(22)
    resp = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
    agent_final = resp.json()
    print(f"Energy Change in Dark: 10 -> {agent_final['capacitor']} (Diff: {agent_final['capacitor'] - 10})")

if __name__ == "__main__":
    test_solar_mechanics()
