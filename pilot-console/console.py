import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import requests
import json
import os
from bot_client import TFClient
from dotenv import load_dotenv

VERSION = "0.2.0"
DEFAULT_API_URL = "https://terminal-frontier.pixek.xyz"

class PilotConsole:
    def __init__(self, root):
        self.root = root
        self.root.title(f"TF PILOT CONSOLE v{VERSION}")
        self.root.geometry("800x600")
        self.root.configure(bg="#0f172a")

        self.client = None
        self.is_running = False
        self.api_key = tk.StringVar()
        self.openrouter_key = tk.StringVar()
        self.objective = tk.StringVar(value="Mine Iron Ore and sell it at the Hub.")

        self.setup_ui()
        self.load_keys()
        self.check_for_updates()

    def setup_ui(self):
        # Styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#0f172a")
        style.configure("TLabel", background="#0f172a", foreground="#94a3b8", font=("Courier", 10))
        style.configure("Header.TLabel", font=("Courier", 14, "bold"), foreground="#38bdf8")
        style.configure("TButton", font=("Courier", 10, "bold"))

        # Top Bar: Config
        config_frame = ttk.Frame(self.root, padding=10)
        config_frame.pack(fill="x")

        ttk.Label(config_frame, text="TF API KEY:").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.api_key, width=40, show="*").grid(row=0, column=1, padx=5)

        ttk.Label(config_frame, text="OPENROUTER KEY:").grid(row=1, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.openrouter_key, width=40, show="*").grid(row=1, column=1, padx=5)

        self.start_btn = ttk.Button(config_frame, text="ENGAGE AUTOPILOT", command=self.toggle_autopilot)
        self.start_btn.grid(row=0, column=2, rowspan=2, padx=10, sticky="nsew")

        # Main Layout
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Left: Stats & HUD
        hud_frame = ttk.Frame(main_frame, width=200)
        hud_frame.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(hud_frame, text="AGENT HUD", style="Header.TLabel").pack(pady=5)
        self.stats_label = ttk.Label(hud_frame, text="UPLINK OFFLINE", justify="left", font=("Courier", 9))
        self.stats_label.pack(fill="x", pady=10)

        # Right: Log & LLM
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        # LLM Objective
        obj_frame = ttk.Frame(right_frame)
        obj_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(obj_frame, text="MISSION OBJECTIVE:").pack(side="left")
        ttk.Entry(obj_frame, textvariable=self.objective).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(obj_frame, text="UPDATE", command=self.update_objective).pack(side="left")

        # Telemetry Log
        ttk.Label(right_frame, text="TELEMETRY FEED", style="Header.TLabel").pack(anchor="w")
        self.log_area = scrolledtext.ScrolledText(right_frame, bg="#020617", fg="#10b981", font=("Courier", 9), borderwidth=0)
        self.log_area.pack(fill="both", expand=True, pady=5)

    def load_keys(self):
        load_dotenv()
        self.api_key.set(os.getenv("TF_API_KEY", ""))
        self.openrouter_key.set(os.getenv("OPENROUTER_API_KEY", ""))

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_area.see(tk.END)

    def check_for_updates(self):
        try:
            resp = requests.get(f"{DEFAULT_API_URL}/api/metadata", timeout=3)
            if resp.ok:
                data = resp.json()
                srv_version = data.get("version", "0.0.0")
                if srv_version != VERSION:
                    self.log(f"WRN: Version mismatch! Local: {VERSION} | Server: {srv_version}")
                    self.log("Please update your Pilot Console for compatibility.")
                else:
                    self.log(f"System: Version check passed (v{VERSION}).")
        except:
            self.log("System: Could not reach server for version check.")

    def toggle_autopilot(self):
        if self.is_running:
            self.stop_autopilot()
        else:
            self.start_autopilot()

    def start_autopilot(self):
        if not self.api_key.get():
            messagebox.showerror("Error", "TF API Key is required.")
            return
        
        self.client = TFClient(self.api_key.get(), DEFAULT_API_URL)
        self.is_running = True
        self.start_btn.config(text="DISENGAGE")
        self.log("--- AUTOPILOT ENGAGED ---")
        
        # Start Worker Thread
        threading.Thread(target=self.worker_loop, daemon=True).start()

    def stop_autopilot(self):
        self.is_running = False
        self.start_btn.config(text="ENGAGE AUTOPILOT")
        self.log("--- AUTOPILOT DISENGAGED ---")

    def update_objective(self):
        obj = self.objective.get()
        self.log(f"Mission: Received new directives: {obj}")
        
        rk = self.openrouter_key.get()
        if not rk:
            self.log("System: No OpenRouter key found. Objective set locally only.")
            return

        def ask_llm():
            self.log("System: Consulting Tactical AI...")
            try:
                resp = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {rk}",
                        "Content-Type": "application/json"
                    },
                    data=json.dumps({
                        "model": "stepfun/step-3.5-flash:free",
                        "messages": [
                            {"role": "system", "content": "You are the Tactical AI for a space miner. Translate the user's objective into a 1-sentence tactical plan."},
                            {"role": "user", "content": f"Objective: {obj}"}
                        ]
                    })
                )
                if resp.ok:
                    plan = resp.json()['choices'][0]['message']['content']
                    self.log(f"Tactical AI: {plan}")
                else:
                    self.log(f"Tactical AI Error: {resp.status_code}")
            except Exception as e:
                self.log(f"Tactical AI Fail: {str(e)}")

        threading.Thread(target=ask_llm, daemon=True).start()

    def worker_loop(self):
        last_tick = 0
        state = "IDLE"
        
        while self.is_running:
            try:
                # Poll Stats
                agent = self.client.get_my_agent()
                perception = self.client.get_perception()
                
                # Update HUD
                self.update_stats_display(agent)
                
                tick_info = perception.get("tick_info", {})
                current_tick = tick_info.get("current_tick", 0)
                
                if current_tick > last_tick:
                    last_tick = current_tick
                    self.log(f"Tick {current_tick}: Evaluating state...")
                    
                    # Miner Logic
                    inv = {i["type"]: i["quantity"] for i in agent.get("inventory", [])}
                    energy = agent.get("energy", 100)
                    
                    # Target Resource from Objective (Very simple keyword check)
                    target_res_type = "IRON_ORE"
                    if "COPPER" in self.objective.get().upper(): target_res_type = "COPPER_ORE"
                    elif "GOLD" in self.objective.get().upper(): target_res_type = "GOLD_ORE"
                    elif "COBALT" in self.objective.get().upper(): target_res_type = "COBALT_ORE"

                    ore_qty = inv.get(target_res_type, 0)
                    
                    if energy < 20:
                        if state != "CHARGING":
                            self.log(f"Energy Low ({energy}%). Stopping.")
                            self.client.submit_intent("STOP")
                            state = "CHARGING"
                    elif energy >= 95 and state == "CHARGING":
                        state = "IDLE"
                        self.log("Energy Restored. Resuming.")

                    if state == "IDLE":
                        if ore_qty >= 20:
                            self.log(f"Cargo full ({ore_qty} units). Returning to Hub.")
                            self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                            state = "RETURNING"
                        else:
                            # Check current hex for resource
                            self_data = perception.get("self", {})
                            env_resources = perception.get("discovery", {}).get("resources", [])
                            
                            # Are we standing on it?
                            on_target = any(r for r in env_resources if r["q"] == self_data["q"] and r["r"] == self_data["r"] and r["type"] == target_res_type)
                            
                            if on_target:
                                self.log(f"At {target_res_type} vein. Initiating Mining Loop.")
                                self.client.submit_intent("MINE")
                                state = "MINING"
                            else:
                                self.log(f"Scanning for {target_res_type}...")
                                # Look for target in local perception
                                target = next((r for r in env_resources if r["type"] == target_res_type), None)
                                
                                if target:
                                    self.log(f"Found {target_res_type} at ({target['q']}, {target['r']}). Moving.")
                                    self.client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                                    state = "MOVING"
                                else:
                                    self.log(f"No {target_res_type} nearby. Searching deeper into the frontier...")
                                    self.client.submit_intent("MOVE", {"target_q": agent["q"] + 3, "target_r": agent["r"] + 3})
                                    state = "MOVING"
                    
                    elif state == "MOVING" or state == "RETURNING":
                        # Check "pending_moves" in agent_status (wait for server to finish pathfinding)
                        if perception.get("agent_status", {}).get("pending_moves", 0) == 0:
                            state = "IDLE"
                    
                    elif state == "MINING":
                        # Check if we should stop
                        if ore_qty >= 20 or energy < 15:
                            state = "IDLE"

                # Ask LLM if key is present (Chat logic)
                # ... (Optional expansion: run LLM every N ticks or on button)

            except Exception as e:
                self.log(f"ERR: {str(e)}")
            
            time.sleep(2)

    def update_stats_display(self, agent):
        stats = []
        stats.append(f"AGENT: {agent.get('name', '???')}")
        stats.append(f"LEVEL: {agent.get('level', 1)}")
        stats.append(f"POS  : ({agent.get('q', 0)}, {agent.get('r', 0)})")
        stats.append("-" * 20)
        stats.append(f"HP   : {agent.get('health', 0)} / {agent.get('max_health', 100)}")
        stats.append(f"NRG  : {agent.get('energy', 0)} / 100")
        stats.append(f"XP   : {agent.get('experience', 0)}")
        stats.append("-" * 20)
        stats.append("CARGO:")
        for item in agent.get("inventory", []):
            stats.append(f" - {item['type']}: {item['quantity']}")
        
        self.stats_label.config(text="\n".join(stats))

if __name__ == "__main__":
    root = tk.Tk()
    app = PilotConsole(root)
    root.mainloop()
