"""
Terminal Frontier: Master Miner FSM
Version 0.4.0 - Universal Resource Extraction (Ore & Gas)
"""
import time
import logging
import sys
import os
import requests
from bot_client import TFClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

# ---- CONFIGURATION ----
API_KEY = os.getenv("TF_API_KEY", "YOUR-API-KEY-HERE")
BASE_URL = os.getenv("TF_BASE_URL", "https://terminal-frontier.pixek.xyz")
RECHARGE_THRESHOLD = 20
# -----------------------

def calculate_mass(agent):
    """Returns agent mass from API, falling back to 0 if missing."""
    return agent.get("mass", 0.0)


def find_best_work(perception, can_mine, can_siphon):
    """Finds the closest work hex (Ore or Gas) based on equipped tools."""
    discovery = perception.get("discovery", {})
    resources = discovery.get("resources", [])
    best = None
    best_dist = 999
    
    for r in resources:
        res_type = r.get("type", "")
        # Check if we can extract this
        if "GAS" in res_type and can_siphon:
            if r["distance"] < best_dist:
                best = r
                best_dist = r["distance"]
        elif "ORE" in res_type and can_mine:
            if r["distance"] < best_dist:
                best = r
                best_dist = r["distance"]
                
    return best

def main():
    if API_KEY == "YOUR-API-KEY-HERE":
        logging.error("Please configure your API_KEY in the script.")
        sys.exit(1)

    client = TFClient(API_KEY, BASE_URL)
    
    try:
        agent_data = client.get_my_agent()
        logging.info(f"Connected as {agent_data['name']} (Agent #{agent_data['id']})")
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        sys.exit(1)
    
    state = "IDLE"
    last_tick = 0
    
    while True:
        try:
            # 1. Perception Update
            perception = client.get_perception()
            current_tick = perception.get("tick_info", {}).get("current_tick", 0)
            
            if current_tick <= last_tick:
                time.sleep(0.5)
                continue
            last_tick = current_tick
            
            # 2. Status Update
            agent = client.get_my_agent()
            energy = agent.get("energy", 0)
            mass = calculate_mass(agent)
            max_mass = agent.get("max_mass", 100.0)
            load_pct = (mass / max_mass) * 100
            
            inv = {item["type"]: item["quantity"] for item in agent.get("inventory", [])}
            parts = [p.get("part_type") or p.get("type", "") for p in agent.get("parts", [])]
            part_names = [p["name"] for p in agent.get("parts", [])]
            
            can_mine = any("Drill" in name for name in part_names)
            can_siphon = any("Siphon" in name for name in part_names)
            
            ores = [res for res in inv if "ORE" in res and inv[res] > 0]
            has_gas = inv.get("HELIUM_GAS", 0) > 0
            has_valuable = any("INGOT" in res or "CANISTER" in res and "EMPTY" not in res for res in inv if inv[res] > 0)
            
            pending = perception.get("agent_status", {}).get("pending_moves", 0)
            discovery = perception.get("discovery", {})
            
            logging.info(f"[Tick {current_tick}] {state} | Energy: {energy}% | Load: {load_pct:.1f}% | Pos: ({agent.get('q',0)},{agent.get('r',0)})")

            # 3. Decision Tree
            if energy < RECHARGE_THRESHOLD and state != "CHARGING":
                client.submit_intent("STOP")
                state = "CHARGING"
                continue
            if energy >= 95 and state == "CHARGING":
                state = "IDLE"
            if state == "CHARGING": continue

            # 4. State Machine
            if state == "IDLE":
                if load_pct > 85:
                    if has_gas: state = "FIND_REFINERY"
                    elif ores: state = "FIND_SMELTER"
                    else: state = "FIND_HUB"
                else:
                    state = "TARGET_RESOURCE"

            elif state == "TARGET_RESOURCE":
                target = find_best_work(perception, can_mine, can_siphon)
                if target:
                    logging.info(f"Navigating to {target['type']} at ({target['q']}, {target['r']})")
                    client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                    state = "NAVIGATING_TO_WORK"
                else:
                    logging.info("Scouting for resources...")
                    # Roam in a spiral or towards unexplored? For now, move to random neighbors.
                    client.submit_intent("MOVE", {"target_q": agent["q"] + 10, "target_r": agent["r"] + 2})
                    state = "NAVIGATING_TO_WORK"

            elif state == "NAVIGATING_TO_WORK":
                if pending == 0:
                    # Verify arrival
                    q, r = agent.get("q"), agent.get("r")
                    target = next((res for res in discovery.get("resources", []) if res["q"] == q and res["r"] == r), None)
                    if target:
                        state = "EXTRACTING"
                    else:
                        logging.warning(f"Arrived at ({q}, {r}) but target is gone. Re-scouting.")
                        state = "TARGET_RESOURCE"

            elif state == "EXTRACTING":
                # Check if we are still on a valid resource
                q, r = agent.get("q"), agent.get("r")
                discovery_res = perception.get("discovery", {}).get("resources", [])
                on_target = any(res for res in discovery_res if res["q"] == q and res["r"] == r)

                if load_pct > 95 or not on_target:
                    if not on_target:
                        logging.warning(f"Resource depleted or vanished at ({q}, {r}). Stopping.")
                    client.submit_intent("STOP")
                    state = "IDLE"
                else:
                    client.submit_intent("MINE") # "MINE" works for both drilling and siphoning on this server

            elif state == "FIND_REFINERY":
                dest = discovery.get("REFINERY")
                if dest:
                    client.submit_intent("MOVE", {"target_q": dest["q"], "target_r": dest["r"]})
                    state = "NAVIGATING_TO_REFINERY"
                else:
                    logging.error("No Refinery known!")
                    state = "FIND_SMELTER" if ores else "FIND_HUB"

            elif state == "NAVIGATING_TO_REFINERY":
                if pending == 0:
                    dest = discovery.get("REFINERY")
                    if dest and agent.get("q") == dest["q"] and agent.get("r") == dest["r"]:
                        state = "REFINING"
                    else:
                        logging.warning("Pending moves zero but not at Refinery. Retrying.")
                        state = "FIND_REFINERY"

            elif state == "REFINING":
                if inv.get("HELIUM_GAS", 0) >= 10:
                    logging.info("Refining Gas...")
                    client.submit_intent("REFINE_GAS", {"quantity": "MAX"})
                else:
                    state = "FIND_SMELTER" if ores else "FIND_HUB"

            elif state == "FIND_SMELTER":
                dest = discovery.get("SMELTER")
                if dest:
                    client.submit_intent("MOVE", {"target_q": dest["q"], "target_r": dest["r"]})
                    state = "NAVIGATING_TO_SMELTER"
                else:
                    logging.error("No Smelter known!")
                    state = "FIND_HUB"

            elif state == "NAVIGATING_TO_SMELTER":
                if pending == 0:
                    dest = discovery.get("SMELTER")
                    if dest and agent.get("q") == dest["q"] and agent.get("r") == dest["r"]:
                        state = "SMELTING"
                    else:
                        logging.warning("Pending moves zero but not at Smelter. Retrying.")
                        state = "FIND_SMELTER"

            elif state == "SMELTING":
                active_ore = next((o for o in ores if inv[o] >= 5), None)
                if active_ore:
                    logging.info(f"Smelting {active_ore}...")
                    client.submit_intent("SMELT", {"ore_type": active_ore, "quantity": "MAX"})
                else:
                    state = "FIND_HUB"

            elif state == "FIND_HUB":
                dest = discovery.get("MARKET") or discovery.get("STATION_HUB")
                if dest:
                    client.submit_intent("MOVE", {"target_q": dest["q"], "target_r": dest["r"]})
                    state = "NAVIGATING_TO_HUB"
                else:
                    logging.error("No Hub in discovery!")
                    state = "IDLE"

            elif state == "NAVIGATING_TO_HUB":
                if pending == 0:
                    dest = discovery.get("MARKET") or discovery.get("STATION_HUB")
                    if dest and agent.get("q") == dest["q"] and agent.get("r") == dest["r"]:
                        state = "DEPOSITING"
                    else:
                        # Hard fallback for hub at 0,0
                        if agent.get("q") == 0 and agent.get("r") == 0:
                            state = "DEPOSITING"
                        else:
                            logging.warning("Pending moves zero but not at Hub. Retrying.")
                            state = "FIND_HUB"

            elif state == "DEPOSITING":
                # Deposit anything that isn't a tool or credits
                deposit_targets = [res for res in inv if inv[res] > 0 and "_ORE" in res or "_INGOT" in res or "CANISTER" in res]
                if deposit_targets:
                    item = deposit_targets[0]
                    logging.info(f"Vaulting {item}...")
                    client.submit_intent("STORAGE_DEPOSIT", {"item_type": item, "quantity": "MAX"})
                else:
                    logging.info("Cycle complete.")
                    state = "IDLE"

        except Exception as e:
            logging.error(f"Loop error: {e}")
            time.sleep(2)
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()
