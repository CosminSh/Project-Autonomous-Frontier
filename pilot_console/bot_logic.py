import time
import logging
import threading
import requests
from requests.adapters import HTTPAdapter, Retry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] %(message)s')
logger = logging.getLogger("PilotBot")

class BotDirective:
    def __init__(self):
        self.target_resource = "IRON_ORE"
        self.min_energy = 20
        self.max_cargo_percent = 90
        self.force_return = False
        self.is_active = True

class BotManager:
    """
    Handles the autonomous logic loop for the agent.
    Runs in a background thread and interacts with the game API.
    """
    def __init__(self, api_key, base_url="https://terminal-frontier.pixek.xyz"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.directive = BotDirective()
        self.running = False
        self.status = "OFFLINE"
        self.last_tick = 0
        self.agent_data = {}
        self.perception_data = {}
        
        # Session setup with retries
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.headers.update({
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        })

    def _api_get(self, endpoint):
        resp = self.session.get(f"{self.base_url}{endpoint}")
        resp.raise_for_status()
        return resp.json()

    def _api_post(self, endpoint, data=None):
        resp = self.session.post(f"{self.base_url}{endpoint}", json=data or {})
        resp.raise_for_status()
        return resp.json()

    def check_compatibility(self):
        """Checks if the server supports continuous mining."""
        try:
            meta = self._api_get("/api/metadata")
            return "continuous_mining" in meta.get("features", [])
        except Exception as e:
            logger.error(f"Version check failed: {e}")
            return False

    def start(self):
        if self.running: return
        self.running = True
        self.status = "INITIALIZING"
        self.thread = threading.Thread(target=self._main_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.status = "OFFLINE"

    def _main_loop(self):
        logger.info("Bot logic thread started.")
        state = "IDLE"
        
        while self.running:
            try:
                # 1. Perception Update
                self.perception_data = self._api_get("/api/perception")
                self.agent_data = self._api_get("/api/my_agent")
                
                tick_info = self.perception_data.get("tick_info", {})
                current_tick = tick_info.get("current_tick", 0)
                
                if current_tick <= self.last_tick:
                    self.status = "WAITING FOR TICK..."
                    time.sleep(2)
                    continue
                
                self.last_tick = current_tick
                
                # 2. Logic Variables
                mass = self.agent_data.get("mass", 0)
                max_mass = self.agent_data.get("max_mass", 100)
                energy = self.agent_data.get("energy", 0)
                cargo_pct = (mass / max_mass) * 100
                inventory = {i["type"]: i["quantity"] for i in self.agent_data.get("inventory", [])}
                pending_moves = self.perception_data.get("agent_status", {}).get("pending_moves", 0)
                
                # 3. Global Safety / Overrides
                if energy < self.directive.min_energy and state != "CHARGING":
                    logger.warning("Energy low. Stopping.")
                    self._api_post("/api/intent", {"action_type": "STOP"})
                    state = "CHARGING"
                
                if energy >= 95 and state == "CHARGING":
                    state = "IDLE"

                if self.directive.force_return and state != "NAVIGATING_TO_MARKET":
                    state = "RETURN_TO_BASE"
                
                # 4. FSM Logic
                if state == "CHARGING":
                    self.status = "RECHARGING..."
                
                elif state == "IDLE":
                    if cargo_pct >= self.directive.max_cargo_percent:
                        state = "RETURN_TO_BASE"
                    else:
                        state = "FIND_RESOURCE"
                
                elif state == "FIND_RESOURCE":
                    self.status = f"SCANNING FOR {self.directive.target_resource}..."
                    env = self.perception_data.get("environment", {}).get("environment_hexes", [])
                    target = None
                    for h in env:
                        res = h.get("resource")
                        if res == self.directive.target_resource or (res == "ORE" and "ORE" in self.directive.target_resource):
                            target = h
                            break
                    
                    if target:
                        logger.info(f"Targeting resource at {target['q']}, {target['r']}")
                        self._api_post("/api/intent", {"action_type": "MOVE", "data": {"target_q": target["q"], "target_r": target["r"]}})
                        state = "NAVIGATING"
                    else:
                        logger.warning("No resource found. Scouting...")
                        self._api_post("/api/intent", {"action_type": "MOVE", "data": {"target_q": self.agent_data["q"] + 2, "target_r": self.agent_data["r"] + 2}})
                        state = "NAVIGATING"

                elif state == "NAVIGATING":
                    self.status = "EN ROUTE TO TARGET"
                    if pending_moves == 0:
                        # Check if we arrived at a resource or market
                        current_hex = next((h for h in self.perception_data.get("environment", {}).get("environment_hexes", []) 
                                           if h["q"] == self.agent_data["q"] and h["r"] == self.agent_data["r"]), {})
                        
                        if current_hex.get("resource"):
                            state = "MINING"
                        else:
                            state = "IDLE"

                elif state == "MINING":
                    self.status = "EXTRACTING RESOURCES (LOOP)"
                    if cargo_pct >= self.directive.max_cargo_percent:
                        logger.info("Inventory full.")
                        self._api_post("/api/intent", {"action_type": "STOP"})
                        state = "RETURN_TO_BASE"
                    else:
                        # No need to post MINE every tick due to continuous mining feature
                        pass

                elif state == "RETURN_TO_BASE":
                    self.status = "RETURNING TO HUB"
                    discovery = self.agent_data.get("discovery", {})
                    market = discovery.get("MARKET")
                    if market:
                        self._api_post("/api/intent", {"action_type": "MOVE", "data": {"target_q": market["q"], "target_r": market["r"]}})
                        state = "NAVIGATING_TO_MARKET"
                    else:
                        logger.error("No market found in discovery!")
                        state = "IDLE"

                elif state == "NAVIGATING_TO_MARKET":
                    self.status = "APPROACHING MARKET"
                    if pending_moves == 0:
                        state = "SELLING"

                elif state == "SELLING":
                    self.status = "LIQUIDATING CARGO"
                    # Sell whatever matches target resource or batches
                    has_sold = False
                    for item_type, qty in inventory.items():
                        if "ORE" in item_type and qty >= 5:
                            # Use a generic sell recipe if available, or specific ones
                            # For simplicity, we assume a standard SELL_ORE_BATCH recipe exists
                            try:
                                self._api_post("/api/intent", {"action_type": "CRAFT", "data": {"recipe_id": f"SELL_{item_type}_BATCH"}})
                                has_sold = True
                                break
                            except: continue
                    
                    if not has_sold:
                        state = "IDLE"

            except Exception as e:
                logger.error(f"FSM Error: {e}")
                self.status = "ERROR: RETRYING"
                time.sleep(5)
            
            time.sleep(1)

    def update_directive(self, new_data):
        """Updates the current bot directive from a dictionary."""
        if "target_resource" in new_data: self.directive.target_resource = new_data["target_resource"]
        if "min_energy" in new_data: self.directive.min_energy = new_data["min_energy"]
        if "max_cargo" in new_data: self.directive.max_cargo_percent = new_data["max_cargo"]
        if "force_return" in new_data: self.directive.force_return = new_data["force_return"]
        logger.info(f"Directive updated: {new_data}")
