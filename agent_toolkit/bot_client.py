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

    def get_perception(self) -> dict:
        return self._get("/api/perception").get("content", {})
        
    def submit_intent(self, action_type: str, data: dict = None) -> dict:
        return self._post("/api/intent", {"action_type": action_type, "data": data or {}})
        
    def get_pending_commands(self) -> dict:
        return self._get("/api/intent/pending")

    def wait_for_next_tick(self, current_tick: int, poll_interval: float = 2.0):
        """Sleeps and polls until the server tick advances."""
        while True:
            # You could ping /state or /api/my_agent, but /state is lighter if public
            perception = self.get_perception()
            tick_now = perception.get("tick_info", {}).get("current_tick", current_tick)
            if tick_now > current_tick:
                return tick_now
            time.sleep(poll_interval)
