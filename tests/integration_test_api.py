import os
import requests
import uuid
import time

BASE_URL = os.getenv("TF_BASE_URL", "http://localhost:8000")

def log_test(name, success, detail=""):
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} | {name} {f'({detail})' if detail else ''}")
    return success

class APITester:
    def __init__(self, name_prefix="TestAgent"):
        self.name = f"{name_prefix}_{uuid.uuid4().hex[:4]}"
        self.email = f"{self.name.lower()}@test.local"
        self.token = None
        self.agent_id = None
        self.headers = {}

    def login(self):
        try:
            resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": self.email, "name": self.name})
            if resp.ok:
                data = resp.json()
                self.token = data['api_key']
                self.agent_id = data['agent_id']
                self.headers = {"X-API-KEY": self.token}
                return log_test("Auth: Guest Login", True, f"ID: {self.agent_id}")
            else:
                return log_test("Auth: Guest Login", False, resp.text)
        except Exception as e:
            return log_test("Auth: Guest Login", False, str(e))

    def test_meta(self):
        success = True
        # Rename
        new_name = f"Renamed_{uuid.uuid4().hex[:4]}"
        resp = requests.post(f"{BASE_URL}/api/rename_agent", json={"new_name": new_name}, headers=self.headers)
        success &= log_test("Meta: Rename Agent", resp.ok, resp.text if not resp.ok else f"New name: {new_name}")
        
        # Claim Daily
        resp = requests.post(f"{BASE_URL}/api/claim_daily", headers=self.headers)
        # Might fail if already claimed, which is fine for a test loop if we know the state
        success &= log_test("Meta: Claim Daily", resp.ok or "Already claimed" in resp.text, resp.text)
        
        # My Agent
        resp = requests.get(f"{BASE_URL}/api/my_agent", headers=self.headers)
        success &= log_test("Meta: Get My Agent", resp.ok)
        
        # Agent Logs
        resp = requests.get(f"{BASE_URL}/api/agent_logs", headers=self.headers)
        success &= log_test("Meta: Get Agent Logs", resp.ok)
        
        return success

    def test_world(self):
        success = True
        # Global Stats
        resp = requests.get(f"{BASE_URL}/api/global_stats")
        success &= log_test("World: Global Stats", resp.ok)
        
        # Leaderboards
        resp = requests.get(f"{BASE_URL}/api/leaderboards")
        success &= log_test("World: Leaderboards", resp.ok)
        
        # State
        resp = requests.get(f"{BASE_URL}/state")
        success &= log_test("World: Public State", resp.ok)
        
        # Perception
        resp = requests.get(f"{BASE_URL}/api/perception", headers=self.headers)
        success &= log_test("World: Perception", resp.ok)
        
        return success

    def test_social(self):
        success = True
        # Chat
        resp = requests.post(f"{BASE_URL}/api/chat", json={"message": "Test Message"}, headers=self.headers)
        success &= log_test("Social: Send Chat", resp.ok)
        
        # Get Chat
        resp = requests.get(f"{BASE_URL}/api/chat", headers=self.headers)
        success &= log_test("Social: Get Chat", resp.ok)
        
        return success

    def test_economy(self):
        success = True
        # Market
        resp = requests.get(f"{BASE_URL}/api/market", headers=self.headers)
        success &= log_test("Economy: Market Info", resp.ok)
        
        # Storage Info
        resp = requests.get(f"{BASE_URL}/api/storage/info", headers=self.headers)
        success &= log_test("Economy: Storage Info", resp.ok)
        
        return success

    def test_contracts(self):
        success = True
        # Available Contracts
        resp = requests.get(f"{BASE_URL}/api/contracts/available", headers=self.headers)
        success &= log_test("Contracts: List Available", resp.ok)
        
        # My Contracts
        resp = requests.get(f"{BASE_URL}/api/contracts/my_contracts", headers=self.headers)
        success &= log_test("Contracts: List My Contracts", resp.ok)
        
        return success

    def test_wiki(self):
        success = True
        # Manual
        resp = requests.get(f"{BASE_URL}/api/wiki/manual", headers=self.headers)
        success &= log_test("Wiki: Get Manual", resp.ok)
        
        # Commands
        resp = requests.get(f"{BASE_URL}/api/wiki/commands", headers=self.headers)
        success &= log_test("Wiki: Get Commands", resp.ok)
        
        return success

def run_all_api_tests():
    print(f"=== Starting API Integration Tests at {BASE_URL} ===")
    tester = APITester()
    if not tester.login():
        return
    
    tester.test_meta()
    tester.test_world()
    tester.test_social()
    tester.test_economy()
    tester.test_contracts()
    tester.test_wiki()
    
    print("=== API Integration Tests Complete ===")

if __name__ == "__main__":
    run_all_api_tests()
