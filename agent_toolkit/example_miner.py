"""
Terminal Frontier: Autonomous Mining FSM (Finite State Machine)
Version 0.3.0 - Professional Miner Workflow
"""
import time
import logging
import sys
import requests
from bot_client import TFClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

# ---- CONFIGURATION ----
API_KEY = "YOUR-API-KEY-HERE"
BASE_URL = "http://localhost:8000" 
TARGET_RESOURCE = "IRON_ORE"
RECHARGE_THRESHOLD = 20
# -----------------------

ITEM_WEIGHTS = {
    "IRON_ORE": 2.0, "COPPER_ORE": 2.0, "GOLD_ORE": 3.0, "COBALT_ORE": 4.0,
    "IRON_INGOT": 5.0, "COPPER_INGOT": 5.0, "GOLD_INGOT": 7.0, "COBALT_INGOT": 10.0,
    "SCRAP_METAL": 1.0, "ELECTRONICS": 0.5, "CREDITS": 0.0
}

def calculate_mass(agent):
    """Calculates current cargo mass from inventory."""
    total = 0
    for item in agent.get("inventory", []):
        w = ITEM_WEIGHTS.get(item["type"], 1.0) # Default 1.0 for unknown parts
        total += item["quantity"] * w
    return total

def find_nearest_resource(perception, res_type):
    """Finds the closest hex with the target resource."""
    resources = perception.get("resources", [])
    best = None
    best_dist = 999
    for r in resources:
        if r.get("type") == res_type:
            if r["distance"] < best_dist:
                best = r
                best_dist = r["distance"]
    return best

def main():
    if API_KEY == "YOUR-API-KEY-HERE":
        logging.error("Please configure your API_KEY in example_miner.py")
        sys.exit(1)

    client = TFClient(API_KEY, BASE_URL)
    
    try:
        agent_data = client.get_my_agent()
        logging.info(f"Connected as {agent_data['name']} (Agent #{agent_data['id']})")
    except Exception as e:
        logging.error(f"Failed to connect: {e}")
        sys.exit(1)
    
    state = "IDLE"
    last_tick = 0
    
    while True:
        try:
            # 1. Update Perception
            perception = client.get_perception()
            current_tick = perception.get("tick_info", {}).get("current_tick", 0)
            
            if current_tick <= last_tick:
                time.sleep(0.5)
                continue
            last_tick = current_tick
            
            # 2. Update Self
            agent = client.get_my_agent()
            energy = agent.get("energy", 0)
            mass = calculate_mass(agent)
            max_mass = agent.get("max_mass", 100.0)
            load_pct = (mass / max_mass) * 100
            
            inv = {item["type"]: item["quantity"] for item in agent.inventory}
            ore_qty = inv.get(TARGET_RESOURCE, 0)
            ingot_type = TARGET_RESOURCE.replace("_ORE", "_INGOT")
            ingot_qty = inv.get(ingot_type, 0)
            
            pending = perception.get("agent_status", {}).get("pending_moves", 0)
            discovery = perception.get("discovery", {})
            
            logging.info(f"[Tick {current_tick}] {state} | Energy: {energy}% | Load: {load_pct:.1f}% | Ore: {ore_qty} | Pos: ({agent['q']},{agent['r']})")

            # 3. Energy Safety
            if energy < RECHARGE_THRESHOLD and state != "CHARGING":
                logging.warning("Low energy! Halting for recharge.")
                client.submit_intent("STOP")
                state = "CHARGING"
                continue
                
            if energy >= 95 and state == "CHARGING":
                logging.info("Fully charged.")
                state = "IDLE"

            if state == "CHARGING": continue

            # 4. State Machine
            if state == "IDLE":
                if load_pct > 85: # Cargo mostly full
                    if ore_qty > 0: state = "FIND_SMELTER"
                    else: state = "FIND_MARKET" # Full of something else or ingots?
                elif ingot_qty > 10: # Have enough ingots to bother vaulting
                    state = "FIND_MARKET"
                else:
                    state = "FIND_ORE"

            elif state == "FIND_ORE":
                target = find_nearest_resource(perception, TARGET_RESOURCE)
                if target:
                    logging.info(f"Navigating to {TARGET_RESOURCE} at ({target['q']}, {target['r']})")
                    client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                    state = "NAVIGATING_TO_ORE"
                else:
                    # Check discovery for a known location? For now, scout.
                    logging.info("Target resource not in sensor range. Scouting...")
                    client.submit_intent("MOVE", {"target_q": agent["q"] + 8, "target_r": agent["r"] + 2})
                    state = "NAVIGATING_TO_ORE"

            elif state == "NAVIGATING_TO_ORE":
                if pending == 0: state = "MINING"

            elif state == "MINING":
                if load_pct > 95:
                    logging.info("Cargo capacity reached.")
                    client.submit_intent("STOP")
                    state = "FIND_SMELTER"
                else:
                    logging.info(f"Extracting {TARGET_RESOURCE}...")
                    client.submit_intent("MINE")

            elif state == "FIND_SMELTER":
                dest = discovery.get("SMELTER")
                if dest:
                    client.submit_intent("MOVE", {"target_q": dest["q"], "target_r": dest["r"]})
                    state = "NAVIGATING_TO_SMELTER"
                else:
                    logging.error("No Smelter in discovery database!")
                    state = "IDLE"

            elif state == "NAVIGATING_TO_SMELTER":
                if pending == 0: state = "SMELTING"

            elif state == "SMELTING":
                if ore_qty >= 5: # Smelting ratio is usually 5:1
                    logging.info(f"Processing {ore_qty} ore into ingots...")
                    client.submit_intent("SMELT", {"ore_type": TARGET_RESOURCE, "quantity": "MAX"})
                else:
                    logging.info("Smelting complete.")
                    state = "FIND_MARKET"

            elif state == "FIND_MARKET":
                # Market stations also handle VAULT/STORAGE
                dest = discovery.get("MARKET") or discovery.get("STATION_HUB")
                if dest:
                    client.submit_intent("MOVE", {"target_q": dest["q"], "target_r": dest["r"]})
                    state = "NAVIGATING_TO_MARKET"
                else:
                    logging.error("No Hub/Market in discovery!")
                    state = "IDLE"

            elif state == "NAVIGATING_TO_MARKET":
                if pending == 0: state = "DEPOSIT"

            elif state == "DEPOSIT":
                if ingot_qty > 0 or ore_qty > 0:
                    logging.info("Depositing refined goods to Vault...")
                    # Priority: Vault ingots first
                    if ingot_qty > 0:
                        client.submit_intent("STORAGE_DEPOSIT", {"item_type": ingot_type, "quantity": "MAX"})
                    elif ore_qty > 0:
                        client.submit_intent("STORAGE_DEPOSIT", {"item_type": TARGET_RESOURCE, "quantity": "MAX"})
                else:
                    logging.info("Vaulting complete. Cycle finished.")
                    state = "IDLE"

        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(2)
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()
