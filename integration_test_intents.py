import requests
import time
import uuid
import json

BASE_URL = "http://localhost:8000"

def log_test(name, success, detail=""):
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} | {name} {f'({detail})' if detail else ''}")
    return success

class IntentTester:
    def __init__(self, name_prefix="IntentBot"):
        self.name = f"{name_prefix}_{uuid.uuid4().hex[:4]}"
        self.email = f"{self.name.lower()}@test.local"
        self.token = None
        self.agent_id = None
        self.headers = {}

    def login(self):
        resp = requests.post(f"{BASE_URL}/auth/guest", json={"email": self.email, "name": self.name})
        if resp.ok:
            data = resp.json()
            self.token = data['api_key']
            self.agent_id = data['agent_id']
            self.headers = {"X-API-KEY": self.token}
            print(f"Logged in as {self.name} (ID: {self.agent_id})")
            return True
        return False

    def get_current_tick(self):
        resp = requests.get(f"{BASE_URL}/api/debug/heartbeat")
        if resp.ok:
            return resp.json()["tick"]
        return 0

    def wait_for_tick(self, target_tick=None, timeout=60):
        start_tick = self.get_current_tick()
        if target_tick is None:
            target_tick = start_tick + 1
        
        print(f"Waiting for tick {target_tick} (current: {start_tick})...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            curr = self.get_current_tick()
            if curr >= target_tick:
                return curr
            time.sleep(1)
        raise TimeoutError("Timed out waiting for tick")

    def submit_intent(self, action, data=None):
        resp = requests.post(f"{BASE_URL}/api/intent", 
                            json={"action_type": action, "data": data or {}}, 
                            headers=self.headers)
        return resp.ok, resp.text

    def teleport(self, q, r):
        resp = requests.post(f"{BASE_URL}/api/debug/teleport", json={"agent_id": self.agent_id, "q": q, "r": r})
        return resp.ok

    def add_item(self, item_type, qty):
        resp = requests.post(f"{BASE_URL}/api/debug/add_item", json={"agent_id": self.agent_id, "item_type": item_type, "quantity": qty})
        return resp.ok

    def equip(self, part_name):
        resp = requests.post(f"{BASE_URL}/api/debug/equip", json={"agent_id": self.agent_id, "part_name": part_name})
        return resp.ok

    def test_move(self):
        print("\n--- Testing MOVE Intent ---")
        self.teleport(0, 0)
        ok, msg = self.submit_intent("MOVE", {"target_q": 3, "target_r": 3})
        if not ok: return log_test("Intent: MOVE Submit", False, msg)
        
        # Schedule response tells us which tick it was scheduled for
        import json
        scheduled_tick = json.loads(msg)["tick"]
        
        # We MUST wait for the tick AFTER the scheduled one to ensure processing is done
        self.wait_for_tick(scheduled_tick + 1)
        # For long paths, we might need to wait even longer, but 1 step is enough to see progress
        agent = requests.get(f"{BASE_URL}/api/my_agent", headers=self.headers).json()
        success = (agent["q"] != 0 or agent["r"] != 0)
        return log_test("Intent: MOVE Progressed", success, f"New Pos: {agent['q']}, {agent['r']}")

    def test_mine(self):
        print("\n--- Testing MINE Intent ---")
        # (0, 7) is a verified ASTEROID
        self.teleport(0, 7)
        self.equip("DRILL_IRON_BASIC")
        ok, msg = self.submit_intent("MINE")
        if not ok: return log_test("Intent: MINE Submit", False, msg)
        
        scheduled_tick = json.loads(msg)["tick"]
        self.wait_for_tick(scheduled_tick + 1)
        
        agent = requests.get(f"{BASE_URL}/api/my_agent", headers=self.headers).json()
        has_ore = any("_ORE" in i["type"] for i in agent["inventory"])
        return log_test("Intent: MINE Processed", has_ore, f"Inventory: {[i['type'] for i in agent['inventory']]}")

    def test_smelt(self):
        print("\n--- Testing SMELT Intent ---")
        self.add_item("IRON_ORE", 10)
        self.teleport(0, 0) 
        ok, msg = self.submit_intent("SMELT", {"ore_type": "IRON_ORE", "quantity": 5})
        if not ok: return log_test("Intent: SMELT Submit", False, msg)
        
        scheduled_tick = json.loads(msg)["tick"]
        self.wait_for_tick(scheduled_tick + 1)
        
        agent = requests.get(f"{BASE_URL}/api/my_agent", headers=self.headers).json()
        has_ingot = any("IRON_INGOT" in i["type"] for i in agent["inventory"])
        return log_test("Intent: SMELT Processed", has_ingot, f"Inventory: {[i['type'] for i in agent['inventory']]}")

def run_intent_tests():
    tester = IntentTester()
    if not tester.login(): return
    
    tester.test_move()
    tester.test_mine()
    tester.test_smelt()

if __name__ == "__main__":
    run_intent_tests()
