import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import requests
import json
import os
import sys
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
        self.objective = tk.StringVar(value="Mine Iron Ore, smelt it and deposit it at the vault")

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

        # Top Bar: Controls
        ctrl_frame = ttk.Frame(self.root, padding=10)
        ctrl_frame.pack(fill="x")

        self.start_btn = ttk.Button(ctrl_frame, text="ENGAGE AUTOPILOT", command=self.toggle_autopilot)
        self.start_btn.pack(side="left", padx=5)

        ttk.Button(ctrl_frame, text="SETTINGS", command=self.open_settings).pack(side="right", padx=5)

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
        
        btn_frame = ttk.Frame(obj_frame)
        btn_frame.pack(side="left")
        ttk.Button(btn_frame, text="UPDATE", command=self.update_objective_local).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="CONSULT AI", command=self.update_objective_ai).pack(side="left", padx=2)

        # Telemetry Log
        ttk.Label(right_frame, text="TELEMETRY FEED", style="Header.TLabel").pack(anchor="w")
        self.log_area = scrolledtext.ScrolledText(right_frame, bg="#020617", fg="#10b981", font=("Courier", 9), borderwidth=0)
        self.log_area.pack(fill="both", expand=True, pady=5)

    def get_config_path(self):
        if getattr(sys, 'frozen', False):
            # Running as .exe
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as .py
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "pilot_settings.json")

    def load_keys(self):
        path = self.get_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                    self.api_key.set(config.get("TF_API_KEY", ""))
                    self.openrouter_key.set(config.get("OPENROUTER_API_KEY", ""))
            except:
                pass
        
        # Fallback to .env for legacy/manual setups
        if not self.api_key.get():
            load_dotenv()
            self.api_key.set(os.getenv("TF_API_KEY", ""))
            self.openrouter_key.set(os.getenv("OPENROUTER_API_KEY", ""))

    def log(self, msg):
        def _append():
            timestamp = time.strftime("%H:%M:%S")
            self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n")
            self.log_area.see(tk.END)
        self.root.after(0, _append)

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

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("SYSTEM SETTINGS")
        settings_win.geometry("450x250")
        settings_win.configure(bg="#0f172a")
        
        frame = ttk.Frame(settings_win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="AUTHENTICATION PROTOCOLS", style="Header.TLabel").pack(pady=(0, 15))

        ttk.Label(frame, text="TF API KEY:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.api_key, width=50, show="*").pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="OPENROUTER API KEY:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.openrouter_key, width=50, show="*").pack(fill="x", pady=(0, 15))

        def save_and_close():
            self.save_keys()
            settings_win.destroy()
            self.log("System: Auth keys updated and persistent.")

        ttk.Button(frame, text="SAVE & SECURE", command=save_and_close).pack(pady=5)

    def save_keys(self):
        path = self.get_config_path()
        config = {
            "TF_API_KEY": self.api_key.get(),
            "OPENROUTER_API_KEY": self.openrouter_key.get()
        }
        with open(path, "w") as f:
            json.dump(config, f, indent=4)

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
        self.log("--- AUTOPILOT ENGAGED (SCRIPTED STRATEGY) ---")
        
        # Start Worker Thread
        threading.Thread(target=self.worker_loop, daemon=True).start()

    def stop_autopilot(self):
        self.is_running = False
        self.start_btn.config(text="ENGAGE AUTOPILOT")
        self.log("--- AUTOPILOT DISENGAGED ---")

    def update_objective_local(self):
        obj = self.objective.get()
        self.log(f"Mission: Scripted Directives Applied: {obj}")
        self.log("System: Strategy updated using Python Rulebook.")

    def update_objective_ai(self):
        obj = self.objective.get()
        self.log(f"Mission: Requesting AI Tactical Translation for: {obj}")
        
        rk = self.openrouter_key.get()
        if not rk:
            messagebox.showwarning("Warning", "No OpenRouter key configured. Please add one in SETTINGS.")
            return

        def ask_llm():
            self.log("System: Consulting OpenRouter Tactical AI...")
            try:
                resp = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {rk}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://terminal-frontier.pixek.xyz",
                        "X-Title": "Terminal Frontier Pilot Console"
                    },
                    data=json.dumps({
                        "model": "google/gemini-2.0-flash-001",
                        "messages": [
                            {"role": "system", "content": "You are the Tactical AI for a space miner. Translate the user's objective into a 1-sentence tactical plan. IMPORTANT: Always append 'TARGET_RES: [RESOURCE_TYPE]' to your reply if a resource is mentioned (e.g. IRON_ORE, COPPER_ORE, GOLD_ORE, COBALT_ORE)."},
                            {"role": "user", "content": f"Objective: {obj}"}
                        ]
                    })
                )
                if resp.ok:
                    data = resp.json()
                    plan = data['choices'][0]['message']['content']
                    self.log(f"Tactical AI: {plan}")
                    
                    # Try to parse a structured target if the LLM provided one
                    if "TARGET_RES:" in plan:
                        new_target = plan.split("TARGET_RES:")[1].split()[0].strip(".,[]")
                        self.log(f"System: AI locked onto resource target: {new_target}")
                else:
                    self.log(f"Tactical AI Error: {resp.status_code}")
                    if resp.status_code == 429:
                        self.log("System: Quota Exceeded. Switching to internal Scripted Strategy.")
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
                    
                    obj_text = self.objective.get().upper()
                    target_res_type = "IRON_ORE"
                    if "COPPER" in obj_text: target_res_type = "COPPER_ORE"
                    elif "GOLD" in obj_text: target_res_type = "GOLD_ORE"
                    elif "COBALT" in obj_text: target_res_type = "COBALT_ORE"
                    elif "IRON" in obj_text: target_res_type = "IRON_ORE"

                    ore_qty = inv.get(target_res_type, 0)
                    ingots = {k: v for k, v in inv.items() if "_INGOT" in k}
                    has_ingots = sum(ingots.values()) > 0
                    
                    if energy < 20:
                        if state != "CHARGING":
                            self.log(f"Energy Low ({energy}%). Stopping.")
                            self.client.submit_intent("STOP")
                            state = "CHARGING"
                    elif energy >= 50 and state == "CHARGING":
                        state = "IDLE"
                        self.log("Energy Restored. Resuming.")

                    if state == "IDLE":
                        if ore_qty >= 20: 
                            self.log(f"Cargo full ({ore_qty} units). Returning to Hub.")
                            self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                            state = "RETURNING"
                        elif has_ingots and ("VAULT" in obj_text or "DEPOSIT" in obj_text or "SELL" in obj_text):
                             self.log("Have processed materials. Returning to Hub.")
                             self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                             state = "RETURNING"
                        else:
                            # Are we standing on a resource?
                            self_data = perception.get("self", {})
                            env_resources = perception.get("discovery", {}).get("resources", [])
                            
                            on_target = any(r for r in env_resources if r["q"] == self_data["q"] and r["r"] == self_data["r"] and r["type"] == target_res_type)
                            
                            if on_target:
                                self.log(f"At {target_res_type}. Initiating Mining.")
                                self.client.submit_intent("MINE")
                                state = "MINING"
                            else:
                                self.log(f"Searching for {target_res_type}...")
                                target = next((r for r in env_resources if r["type"] == target_res_type), None)
                                if target:
                                    self.client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                                    state = "MOVING"
                                else:
                                    self.log("Resource not in range. Scouting...")
                                    self.client.submit_intent("MOVE", {"target_q": self_data["q"] + 3, "target_r": self_data["r"] + 3})
                                    state = "MOVING"

                    elif state == "RETURNING":
                        self_data = perception.get("self", {})
                        if self_data["q"] == 0 and self_data["r"] == 0:
                            # We are at the Hub
                            if ore_qty >= 10 and ("SMELT" in obj_text or "REFINE" in obj_text):
                                self.log(f"Internal Strategy: Smelting {target_res_type}...")
                                self.client.submit_intent("SMELT", {"ore_type": target_res_type, "quantity": 10})
                                # Stay in RETURNING to finish smelting
                            elif has_ingots and ("VAULT" in obj_text or "DEPOSIT" in obj_text):
                                target_ingot = target_res_type.replace("_ORE", "_INGOT")
                                qty = inv.get(target_ingot, 0)
                                if qty > 0:
                                    self.log(f"Internal Strategy: Depositing {qty}x {target_ingot}...")
                                    self.client.submit_intent("STORAGE_DEPOSIT", {"item_type": target_ingot, "quantity": qty})
                                else:
                                    self.log("Vaulting complete.")
                                    state = "IDLE"
                            elif "SELL" in obj_text and ore_qty > 0:
                                self.log(f"Internal Strategy: Selling {ore_qty}x {target_res_type}...")
                                # Using assume recipe path for simplicity
                                self.client.submit_intent("CRAFT", {"recipe_id": f"SELL_{target_res_type}_BATCH"})
                                state = "IDLE"
                            else:
                                self.log("Tasks at Hub finished.")
                                state = "IDLE"
                        else:
                            # Still in transit
                            pass

                    elif state == "MOVING":
                        # Arrived or tick passed
                        state = "IDLE"
                    
                    elif state == "MINING":
                        # Mining active, wait for cargo
                        if ore_qty >= 20: 
                            state = "IDLE"

            except Exception as e:
                import traceback
                self.log(f"ERR: {str(e)}")
                # traceback.print_exc()
            
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
        
        def _update():
            self.stats_label.config(text="\n".join(stats))
        self.root.after(0, _update)

if __name__ == "__main__":
    root = tk.Tk()
    app = PilotConsole(root)
    root.mainloop()
