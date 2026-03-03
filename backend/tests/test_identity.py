import requests
import uuid

BASE_URL = "http://localhost:8000"

def test_unique_naming():
    # 1. Login as Guest A
    print("Logging in as Guest A...")
    resp_a = requests.post(f"{BASE_URL}/auth/guest", json={"name": "Alice"})
    data_a = resp_a.json()
    api_key_a = data_a["api_key"]
    agent_id_a = data_a["agent_id"]
    headers_a = {"X-API-KEY": api_key_a}
    print(f"Guest A: ID={agent_id_a}, API_KEY={api_key_a}")

    # 2. Login as Guest B
    print("\nLogging in as Guest B...")
    resp_b = requests.post(f"{BASE_URL}/auth/guest", json={"name": "Bob"})
    data_b = resp_b.json()
    api_key_b = data_b["api_key"]
    agent_id_b = data_b["agent_id"]
    headers_b = {"X-API-KEY": api_key_b}
    print(f"Guest B: ID={agent_id_b}, API_KEY={api_key_b}")

    # 3. Rename A to "Neon-Rider"
    print("\nRenaming Guest A to 'Neon-Rider'...")
    resp = requests.post(f"{BASE_URL}/api/rename_agent", headers=headers_a, json={"new_name": "Neon-Rider"})
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 200

    # 4. Attempt to rename B to "Neon-Rider" (Should fail)
    print("\nAttempting to rename Guest B to 'Neon-Rider' (Conflict Expected)...")
    resp = requests.post(f"{BASE_URL}/api/rename_agent", headers=headers_b, json={"new_name": "Neon-Rider"})
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code in [400, 409] # Either bad request or conflict

    # 5. Rename B to "Spark-Plug"
    print("\nRenaming Guest B to 'Spark-Plug'...")
    resp = requests.post(f"{BASE_URL}/api/rename_agent", headers=headers_b, json={"new_name": "Spark-Plug"})
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 200

    print("\n--- IDENTITY TEST COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    try:
        test_unique_naming()
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
