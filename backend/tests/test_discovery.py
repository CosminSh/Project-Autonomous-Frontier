import os
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "dummy_key1"
headers = {"X-API-KEY": API_KEY}
r = requests.get(f"{BASE_URL}/api/perception", headers=headers)
print("Perception Discovery:")
print(r.json().get("content", {}).get("discovery", {}))

r2 = requests.get(f"{BASE_URL}/api/my_agent", headers=headers)
print("\nMy Agent Discovery:")
print(r2.json().get("discovery", {}))
