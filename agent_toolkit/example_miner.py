"""
Terminal Frontier: Autonomous Mining FSM (Finite State Machine)
This script demonstrates how to write a bot that can run unmonitored all day.
"""
import time
import logging
import sys
import requests
from bot_client import TFClient

# Configure logging to see what the bot is doing
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

# ---- CONFIGURATION ----
API_KEY = "YOUR-API-KEY-HERE"
BASE_URL = "http://localhost:8000" # Change to production URL when deploying
# -----------------------

def find_nearest_ore(hexes):
    """Parses perception hexes to find the closest hex with ORE."""
    # Assuming hexes are sorted by distance by the server API
    for h in hexes:
        if h.get("resource") in ["ORE", "IRON_ORE"]:
            return h
    return None

def main():
    if API_KEY == "YOUR-API-KEY-HERE":
        logging.error("Please configure your API_KEY in example_miner.py")
        sys.exit(1)

    client = TFClient(API_KEY, BASE_URL)
    agent = client.get_my_agent()
    logging.info(f"Connected as {agent['name']} (Agent #{agent['id']})")
    
    state = "IDLE"
    last_tick = 0
    
    while True:
        try:
            # 1. Update World View
            perception = client.get_perception()
            agent = client.get_my_agent()
            
            tick_info = perception.get("tick_info", {})
            current_tick = tick_info.get("current_tick", 0)
            
            # Prevent double-processing the same tick
            if current_tick <= last_tick:
                time.sleep(1)
                continue
                
            last_tick = current_tick
            
            # Read variables
            inv = {item["type"]: item["quantity"] for item in agent["inventory"]}
            ore_qty = inv.get("IRON_ORE", 0)
            pending = perception.get("agent_status", {}).get("pending_moves", 0)
            cap = agent["capacitor"]
            
            logging.info(f"[Tick {current_tick}] State: {state} | Energy: {cap}% | Ore: {ore_qty} | Pending: {pending}")

            # 2. Safety Interruption (Event-driven transitions)
            if cap < 15 and state != "CHARGING":
                logging.warning("Energy critical! Halting operations to recharge.")
                client.submit_intent("STOP")
                state = "CHARGING"
                
            if agent["capacitor"] == 100 and state == "CHARGING":
                logging.info("Batteries full. Resuming.")
                state = "IDLE"

            # 3. State Machine Logic
            if state == "CHARGING":
                pass # Just wait for tick to advance

            elif state == "IDLE":
                if ore_qty >= 20:
                    state = "RETURN_TO_MARKET"
                else:
                    state = "FIND_ORE"

            elif state == "FIND_ORE":
                hexes = perception.get("environment", {}).get("environment_hexes", [])
                target = find_nearest_ore(hexes)
                if target:
                    logging.info(f"Targeting ore at Q:{target['q']} R:{target['r']}")
                    client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                    state = "NAVIGATING_TO_ORE"
                else:
                    logging.warning("No ore found in perception! Moving randomly to scout.")
                    client.submit_intent("MOVE", {"target_q": agent["q"] + 2, "target_r": agent["r"] + 2})
                    state = "NAVIGATING_TO_ORE"

            elif state == "NAVIGATING_TO_ORE":
                if pending == 0:
                    logging.info("Arrived at destination.")
                    state = "MINING"

            elif state == "MINING":
                if ore_qty >= 20: # Inventory getting full
                    logging.info("Cargo hold full. Returning to base.")
                    client.submit_intent("STOP") # Stop the looping mining
                    state = "RETURN_TO_MARKET"
                else:
                    logging.info("Mining loop active...")
                    # No need to submit MINE every tick as it's now a looping task!
                    # We just stay in the MINING state until we're full or interrupted.
                    pass

            elif state == "RETURN_TO_MARKET":
                discovery = client.get_my_agent().get("discovery", {})
                market = discovery.get("MARKET")
                if market:
                    client.submit_intent("MOVE", {"target_q": market["q"], "target_r": market["r"]})
                    state = "NAVIGATING_TO_MARKET"
                else:
                    logging.error("No market known! I am lost in space.")
                    state = "IDLE"

            elif state == "NAVIGATING_TO_MARKET":
                if pending == 0:
                    state = "SELLING"
                    
            elif state == "SELLING":
                if ore_qty > 0:
                    logging.info("Selling Ore...")
                    client.submit_intent("CRAFT", {"recipe_id": "SELL_IRON_ORE_BATCH"}) # Example recipe, adjust per server config
                else:
                    logging.info("Cargo emptied. Back to work.")
                    state = "IDLE"

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error: {e.response.text}")
            time.sleep(5) # Backoff on error
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(5)
            
        time.sleep(0.5) # Soft loop delay

if __name__ == "__main__":
    main()
