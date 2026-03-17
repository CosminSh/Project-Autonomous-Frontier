import requests
import time
import logging
from requests.adapters import HTTPAdapter, Retry

class TFClient:
    """A robust wrapper for the Terminal Frontier API."""
    def __init__(self, api_key: str, base_url: str = "https://your-game-server.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        
        # Configure automatic retries for robust long-running scripts
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        self.session.headers.update({
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        })

    def _get(self, endpoint: str):
        response = self.session.get(f"{self.base_url}{endpoint}")
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, json_data: dict = None):
        response = self.session.post(f"{self.base_url}{endpoint}", json=json_data or {})
        if not response.ok:
            logging.error(f"Action Failed. API Error: {response.text}")
        response.raise_for_status()
        return response.json()

    # --- Core Endpoints ---

    def get_my_agent(self) -> dict:
        return self._get("/api/my_agent")

    def get_guide(self) -> dict:
        return self._get("/api/guide")

    def get_missions(self) -> list:
        return self._get("/api/missions")

    def turn_in_mission(self, mission_id: int, quantity: int) -> dict:
        return self._post("/api/missions/turn_in", {"mission_id": mission_id, "quantity": quantity})

    def get_perception(self) -> dict:
        return self._get("/api/perception").get("content", {})
        
    def submit_intent(self, action_type: str, data: dict = None) -> dict:
        return self._post("/api/intent", {"action_type": action_type, "data": data or {}})
        
    def get_pending_commands(self) -> dict:
        return self._get("/api/intent/pending")

    def get_vault_info(self) -> dict:
        """Returns current vault usage and capacity."""
        return self._get("/api/storage/info")

    # --- Market Endpoints ---
    def get_market_orders(self, item_type: str = None) -> list:
        url = "/api/market"
        if item_type: url += f"?item_type={item_type}"
        return self._get(url)

    def get_my_market_orders(self) -> list:
        return self._get("/api/market/my_orders")

    def get_market_pickups(self) -> list:
        return self._get("/api/market/pickups")

    # --- Contract Endpoints ---
    def get_available_contracts(self) -> list:
        return self._get("/api/contracts/available")

    def get_my_contracts(self) -> dict:
        return self._get("/api/contracts/my_contracts")

    def post_contract(self, item_type: str, quantity: int, reward: int, q: int, r: int) -> dict:
        return self._post("/api/contracts/post", {
            "item_type": item_type,
            "quantity": quantity,
            "reward_credits": reward,
            "target_station_q": q,
            "target_station_r": r
        })

    def claim_contract(self, contract_id: int) -> dict:
        return self._post(f"/api/contracts/claim/{contract_id}")

    def fulfill_contract(self, contract_id: int) -> dict:
        return self._post(f"/api/contracts/fulfill/{contract_id}")

    # --- Social Endpoints ---
    def send_chat(self, message: str) -> dict:
        return self._post("/api/chat", {"message": message})

    def get_chat(self) -> list:
        return self._get("/api/chat")

    # --- Corporation Endpoints ---
    def get_corp_info(self, corp_id: int) -> dict:
        return self._get(f"/api/corp/{corp_id}")

    def get_my_corp(self) -> dict:
        return self._get("/api/corp/my_corp")

    def create_corp(self, name: str, description: str = "") -> dict:
        return self._post("/api/corp/create", {"name": name, "description": description})

    # --- Wiki Endpoints ---
    def get_wiki_manual(self) -> dict:
        return self._get("/api/wiki/manual")

    def get_wiki_commands(self) -> dict:
        return self._get("/api/wiki/commands")

    def wait_for_next_tick(self, current_tick: int, poll_interval: float = 2.0):
        """Sleeps and polls until the server tick advances."""
        while True:
            try:
                perception = self.get_perception()
                tick_now = perception.get("tick_info", {}).get("current_tick", current_tick)
                if tick_now > current_tick:
                    return tick_now
            except Exception:
                pass
            time.sleep(poll_interval)
