import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import requests
import json
import os
import sys
import subprocess
import re
from bot_client import TFClient
from dotenv import load_dotenv

VERSION = "0.3.4"
GITHUB_RAW_VERSION_URL = "https://raw.githubusercontent.com/CosminSh/Project-Autonomous-Frontier/main/agent_toolkit/console.py"
DEFAULT_API_URL = "https://terminal-frontier.pixek.xyz"

# Aesthetic Constants
COLORS = {
    "bg": "#0f172a",
    "surface": "#1e293b",
    "accent": "#06b6d4",
    "indigo": "#6366f1",
    "emerald": "#10b981",
    "amber": "#f59e0b",
    "rose": "#f43f5e",
    "slate": "#94a3b8",
    "white": "#f8fafc"
}

RARITY_COLORS = {
    "SCRAP": "#94a3b8",
    "COMMON": "#f8fafc",
    "STANDARD": "#f8fafc",
    "REFINED": "#38bdf8",
    "PRIME": "#fbbf24",
    "RELIC": "#f97316"
}

class PilotConsole:
    def __init__(self, root):
        self.root = root
        self.root.title(f"TF PILOT CONSOLE v{VERSION}")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLORS["bg"])

        self.client = None
        self.is_running = False
        self.api_key = tk.StringVar()
        self.openrouter_key = tk.StringVar()
        self.objective = tk.StringVar(value="Mine Iron Ore, smelt it and deposit it at the vault")

        self.setup_ui()
        self.load_keys()
        self.check_for_updates()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Styles
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Sidebar.TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["slate"], font=("Courier", 10))
        style.configure("Sidebar.TLabel", background=COLORS["surface"], foreground=COLORS["slate"], font=("Courier", 9))
        style.configure("Header.TLabel", font=("Courier", 13, "bold"), foreground=COLORS["accent"])
        style.configure("Title.TLabel", font=("Courier", 18, "bold"), foreground=COLORS["white"])
        style.configure("TButton", font=("Courier", 10, "bold"))
        
        # --- Top Bar ---
        top_bar = ttk.Frame(self.root, padding=10)
        top_bar.pack(fill="x")
        
        ttk.Label(top_bar, text="TERMINAL FRONTIER", style="Title.TLabel").pack(side="left", padx=10)
        
        self.start_btn = tk.Button(top_bar, text="ENGAGE AUTOPILOT", 
                                  bg=COLORS["accent"], fg=COLORS["bg"], 
                                  font=("Courier", 10, "bold"), padx=15, pady=5,
                                  command=self.toggle_autopilot, borderwidth=0)
        self.start_btn.pack(side="left", padx=20)

        ttk.Button(top_bar, text="SETTINGS", command=self.open_settings).pack(side="right", padx=10)

        # --- Main Layout ---
        main_layout = ttk.Frame(self.root, padding=5)
        main_layout.pack(fill="both", expand=True)

        # LEFT SIDEBAR (Stats & HUD)
        sidebar = ttk.Frame(main_layout, width=280, style="Sidebar.TFrame", padding=15)
        sidebar.pack(side="left", fill="y", padx=5, pady=5)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="COMMANDER HUD", style="Header.TLabel", style_="Sidebar.TLabel").pack(anchor="w", pady=(0, 10))
        
        # Bars
        self.hp_canvas = self.create_bar(sidebar, "INTEGRITY", COLORS["rose"])
        self.nrg_canvas = self.create_bar(sidebar, "ENERGY", COLORS["accent"])
        
        # Core Stats
        self.stats_box = ttk.Label(sidebar, text="WAITING FOR UPLINK...", justify="left", style="Sidebar.TLabel")
        self.stats_box.pack(fill="x", pady=15)

        ttk.Label(sidebar, text="MINING CAPABILITY", style="Header.TLabel", style_="Sidebar.TLabel").pack(anchor="w", pady=(10, 5))
        self.mining_box = ttk.Label(sidebar, text="Scanning...", justify="left", style="Sidebar.TLabel")
        self.mining_box.pack(fill="x")

        # RIGHT MAIN AREA
        right_main = ttk.Frame(main_layout)
        right_main.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # TOP: Objective & Gear
        top_right = ttk.Frame(right_main)
        top_right.pack(fill="x", pady=(0, 10))

        # Objective
        obj_frame = ttk.LabelFrame(top_right, text="MISSION DIRECTIVES", padding=10)
        obj_frame.pack(fill="x", side="top", pady=(0, 10))
        
        ttk.Entry(obj_frame, textvariable=self.objective, font=("Courier", 10)).pack(fill="x", side="left", expand=True, padx=(0, 10))
        btn_f = ttk.Frame(obj_frame)
        btn_f.pack(side="right")
        ttk.Button(btn_f, text="UPDATE", command=self.update_objective_local).pack(side="left", padx=2)
        ttk.Button(btn_f, text="AI PLAN", command=self.update_objective_ai).pack(side="left", padx=2)

        # Gear Panel
        gear_frame = ttk.LabelFrame(top_right, text="EQUIPPED MODULAR GEAR", padding=10)
        gear_frame.pack(fill="x", side="top")
        self.gear_list = tk.Text(gear_frame, height=6, bg="#020617", fg=COLORS["slate"], font=("Courier", 9), borderwidth=0, state="disabled")
        self.gear_list.pack(fill="x")

        # BOTTOM: Log & Cargo
        bottom_right = ttk.Frame(right_main)
        bottom_right.pack(fill="both", expand=True)

        # Log
        log_frame = ttk.LabelFrame(bottom_right, text="TELEMETRY FEED", padding=5)
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.log_area = scrolledtext.ScrolledText(log_frame, bg="#020617", fg=COLORS["emerald"], font=("Courier", 9), borderwidth=0)
        self.log_area.pack(fill="both", expand=True)

        # Cargo
        cargo_frame = ttk.LabelFrame(bottom_right, text="CARGO MANIFEST", padding=5, width=250)
        cargo_frame.pack(side="right", fill="both")
        self.cargo_list = tk.Text(cargo_frame, bg="#020617", fg=COLORS["white"], font=("Courier", 9), borderwidth=0, state="disabled", width=30)
        self.cargo_list.pack(fill="both", expand=True)

    def create_bar(self, parent, label, color):
        ttk.Label(parent, text=label, style="Sidebar.TLabel").pack(anchor="w", pady=(5, 0))
        canvas = tk.Canvas(parent, height=12, bg="#020617", highlightthickness=0)
        canvas.pack(fill="x", pady=(2, 8))
        canvas.create_rectangle(0, 0, 0, 12, fill=color, outline="", tags="progress")
        return canvas

    def update_bar(self, canvas, percentage):
        width = canvas.winfo_width()
        if width <= 1: width = 200 # Fallback
        fill_w = (percentage / 100.0) * width
        canvas.delete("progress")
        color = canvas.itemcget(canvas.find_all()[0], "fill") if canvas.find_all() else COLORS["accent"]
        canvas.create_rectangle(0, 0, fill_w, 12, fill=color, outline="", tags="progress")

    def log(self, msg):
        def _append():
            timestamp = time.strftime("%H:%M:%S")
            self.log_area.config(state="normal")
            self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state="disabled")
        self.root.after(0, _append)

    def get_config_path(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
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
        if not self.api_key.get():
            load_dotenv()
            self.api_key.set(os.getenv("TF_API_KEY", ""))
            self.openrouter_key.set(os.getenv("OPENROUTER_API_KEY", ""))

    def save_keys(self):
        path = self.get_config_path()
        config = {
            "TF_API_KEY": self.api_key.get(),
            "OPENROUTER_API_KEY": self.openrouter_key.get()
        }
        with open(path, "w") as f:
            json.dump(config, f, indent=4)

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("PILOT SETTINGS")
        settings_win.geometry("400x250")
        settings_win.configure(bg=COLORS["bg"])
        
        frame = ttk.Frame(settings_win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="CREDENTIALS", style="Header.TLabel").pack(pady=(0, 15))
        ttk.Label(frame, text="TF API KEY:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.api_key, width=50, show="*").pack(fill="x", pady=(0, 10))
        ttk.Label(frame, text="OPENROUTER KEY:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.openrouter_key, width=50, show="*").pack(fill="x", pady=(0, 15))

        def save_and_close():
            self.save_keys()
            settings_win.destroy()
        ttk.Button(frame, text="SAVE", command=save_and_close).pack()

    def check_for_updates(self):
        def _check():
            try:
                # 1. First check Server Metadata for compatibility warning
                resp = requests.get(f"{DEFAULT_API_URL}/api/metadata", timeout=3)
                if resp.ok:
                    srv_version = resp.json().get("version", "0.0.0")
                    if srv_version != VERSION:
                        self.log(f"WRN: Server v{srv_version} detected. Local: v{VERSION}")

                # 2. Check GitHub for the latest Toolkit Version
                self.log("System: Checking GitHub for updates...")
                resp = requests.get(GITHUB_RAW_VERSION_URL, timeout=5)
                if resp.ok:
                    content = resp.text
                    version_match = re.search(r'^VERSION = "([^"]+)"', content, re.MULTILINE)
                    if version_match:
                        remote_version = version_match.group(1)
                        if self.is_version_newer(VERSION, remote_version):
                            self.log(f"UPDATE: New version v{remote_version} detected on GitHub!")
                            self.root.after(0, lambda: self.prompt_update(remote_version))
                        else:
                            self.log(f"System: Toolkit is up to date (v{VERSION})")
            except Exception as e:
                self.log(f"System: Update check failed: {e}")

        threading.Thread(target=_check, daemon=True).start()

    def is_version_newer(self, local, remote):
        """Simple semantic version comparison."""
        try:
            l_parts = [int(p) for p in local.split('.')]
            r_parts = [int(p) for p in remote.split('.')]
            return r_parts > l_parts
        except:
            return remote != local

    def prompt_update(self, new_version):
        msg = f"A new version (v{new_version}) of the Pilot Console is available on GitHub.\n\n" \
              f"Would you like to run the auto-updater now?\n\n" \
              f"This will:\n1. Close the current console\n2. Pull latest code\n3. Rebuild the executable"
        if messagebox.askyesno("Update Available", msg):
            self.run_update_script()

    def run_update_script(self):
        try:
            # Determine base directory
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            is_windows = sys.platform.startswith("win")
            script_name = "update.bat" if is_windows else "update.sh"
            script_path = os.path.join(base_dir, script_name)
            
            if not os.path.exists(script_path):
                # Fallback to local script directory
                script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), script_name))

            self.log(f"System: Launching updater: {script_path}")
            
            if is_windows:
                subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k", script_path], 
                                 cwd=base_dir, shell=True)
            else:
                # For Mac/Linux, try to open a new terminal window
                # chmod +x first just in case
                os.chmod(script_path, 0o755)
                if sys.platform == "darwin": # Mac
                    subprocess.Popen(["open", "-a", "Terminal", script_path], cwd=base_dir)
                else: # Linux (generic attempt)
                    subprocess.Popen(["x-terminal-emulator", "-e", f"bash {script_path}"], cwd=base_dir)
            
            # Exit the app
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to launch update script:\n{e}")

    def toggle_autopilot(self):
        if self.is_running:
            self.is_running = False
            self.start_btn.config(text="ENGAGE AUTOPILOT", bg=COLORS["accent"])
            self.log("--- DISENGAGED ---")
        else:
            if not self.api_key.get():
                messagebox.showerror("Error", "Missing API Key")
                return
            self.client = TFClient(self.api_key.get(), DEFAULT_API_URL)
            self.is_running = True
            self.start_btn.config(text="DISENGAGE", bg=COLORS["rose"])
            self.log("--- AUTOPILOT ONLINE ---")
            threading.Thread(target=self.worker_loop, daemon=True).start()

    def update_objective_local(self):
        self.log(f"System: Directives updated: {self.objective.get()}")

    def update_objective_ai(self):
        rk = self.openrouter_key.get()
        if not rk:
            messagebox.showwarning("Warning", "No OpenRouter key")
            return
        self.log("System: Consulting AI Counsel...")
        def ask():
            try:
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {rk}", "Content-Type": "application/json"},
                    data=json.dumps({"model": "google/gemini-2.0-flash-001", "messages": [
                        {"role": "system", "content": "You are a tactical space miner AI. Summarize the plan in 1 sentence. Append 'TARGET_RES: [ORE_TYPE]'."},
                        {"role": "user", "content": f"Objective: {self.objective.get()}"}
                    ]}))
                if resp.ok:
                    plan = resp.json()['choices'][0]['message']['content']
                    self.log(f"Tactical AI: {plan}")
            except Exception as e: self.log(f"AI ERR: {e}")
        threading.Thread(target=ask, daemon=True).start()

    def worker_loop(self):
        last_tick = 0
        state = "IDLE"
        while self.is_running:
            try:
                agent = self.client.get_my_agent()
                perception = self.client.get_perception()
                self.root.after(0, lambda: self.update_stats_display(agent))
                
                tick_info = perception.get("tick_info", {})
                current_tick = tick_info.get("current_tick", 0)
                
                if current_tick > last_tick:
                    last_tick = current_tick
                    self.log(f"Tick {current_tick}: Evaluating Tactical State...")
                    state = self.process_strategy(agent, perception, state)
            except Exception as e:
                self.log(f"ERR: {e}")
            time.sleep(2)

    def get_hex_distance(self, q1, r1, q2, r2):
        return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

    def process_strategy(self, agent, perception, current_state):
        # Robust inventory aggregation
        inv = {}
        for item in agent.get("inventory", []):
            it = item["type"]
            inv[it] = inv.get(it, 0) + item["quantity"]

        energy = agent.get("energy", 100)
        health_p = (agent.get("health", 100) / agent.get("max_health", 100)) * 100
        intensity = perception.get("solar_intensity", 100)
        obj_text = self.objective.get().upper()
        
        # 1. Critical Health & Energy Check
        if health_p < 40:
            self.log(f"CRITICAL: Hull Integrity at {health_p:.1f}%. Retreating for repairs.")
            self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
            return "RETREATING"

        if energy < 20:
            if current_state != "CHARGING":
                if intensity > 70:
                    self.log(f"SYSTEM: Energy Low ({energy}%). Intensity High. Recharging on-site.")
                    self.client.submit_intent("STOP")
                else:
                    self.log(f"SYSTEM: Energy Low ({energy}%). Intensity Poor. Returning to Hub.")
                    self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                    return "CHARGING"
                return "CHARGING"
            return "CHARGING"
        
        if energy >= 90 and current_state == "CHARGING":
            self.log("SYSTEM: Power nominal. Resuming Operations.")
            current_state = "IDLE"

        if current_state == "CHARGING": return "CHARGING"

        # 2. Determine Profession (MINER vs HUNTER)
        is_hunter = "HUNT" in obj_text or "FERAL" in obj_text
        
        # 3. Profession Logic
        if is_hunter:
            # --- HUNTER LOGIC ---
            import re
            lvl_match = re.search(r"LEVEL (\d+)-?(\d*)", obj_text)
            min_lvl = int(lvl_match.group(1)) if lvl_match else 1
            max_lvl = int(lvl_match.group(2)) if lvl_match and lvl_match.group(2) else min_lvl + 10
            
            mass = agent.get("mass", 0)
            max_mass = agent.get("max_mass", 100)
            if mass / max_mass > 0.9:
                self.log("SYSTEM: Cargo saturated with trophies. Returning to Hub.")
                self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                return "RETURNING"

            # Check for ferals in range
            nearby_agents = perception.get("agents", [])
            target_feral = None
            for a in nearby_agents:
                if a.get("is_feral"):
                    lvl = a.get("level", 1)
                    if min_lvl <= lvl <= max_lvl:
                        target_feral = a
                        break
            
            if target_feral:
                dist = a.get("distance", 999) # This is usually 1 for attackable
                if dist <= 1:
                    if current_state != "HUNTING":
                        self.log(f"HUNT: Engaging {target_feral['name']} (Lvl {target_feral['level']})!")
                    self.client.submit_intent("ATTACK", {"target_id": target_feral["id"]})
                    return "HUNTING"
                else:
                    self.log(f"HUNT: Closing distance to {target_feral['name']} at ({target_feral['q']}, {target_feral['r']})")
                    self.client.submit_intent("MOVE", {"target_q": target_feral["q"], "target_r": target_feral["r"]})
                    return "MOVING"
            else:
                # Roam towards the target zone
                # Tier 1: 6-15, Tier 2: 16-30, Tier 3: 31-50, Tier 4: 51+
                zone_r = 10 if min_lvl <= 10 else 25 if min_lvl <= 20 else 40 if min_lvl <= 30 else 60
                self_data = perception.get("self", {})
                if abs(self_data["r"] - zone_r) > 5:
                    self.log(f"HUNT: Moving to Level {min_lvl}+ habitat (r={zone_r}).")
                    self.client.submit_intent("MOVE", {"target_q": self_data["q"] + 2, "target_r": zone_r})
                else:
                    self.log(f"HUNT: No {min_lvl}-{max_lvl} Ferals found. Scouting habitat...")
                    dq = 3 if (perception.get("tick_info", {}).get("current_tick", 0) % 2 == 0) else -3
                    self.client.submit_intent("MOVE", {"target_q": self_data["q"] + dq, "target_r": self_data["r"] + 1})
                return "MOVING"
        else:
            # --- MINER LOGIC (Legacy) ---
            target_res_type = "IRON_ORE"
            target_zone = (6, 20)
            if "COPPER" in obj_text: 
                target_res_type = "COPPER_ORE"
                target_zone = (16, 40)
            elif "GOLD" in obj_text: 
                target_res_type = "GOLD_ORE"
                target_zone = (31, 60)
            elif "COBALT" in obj_text: 
                target_res_type = "COBALT_ORE"
                target_zone = (55, 100)
            
            ore_qty = inv.get(target_res_type, 0)
            all_ingot_types = [k for k, v in inv.items() if "_INGOT" in k and v > 0]
            valuable_loot = [k for k, v in inv.items() if k in ["SYNTHETIC_WEAVE", "FERAL_CORE", "VOID_CHIP", "ANCIENT_CIRCUIT", "ELECTRONICS"] and v > 0]
            
            if ore_qty >= 20 or valuable_loot or (all_ingot_types and ("VAULT" in obj_text or "DEPOSIT" in obj_text)):
                self.log(f"SYSTEM: Logistics needed. Navigating to Hub.")
                self.client.submit_intent("MOVE", {"target_q": 0, "target_r": 0})
                return "RETURNING"
            
            self_data = perception.get("self", {})
            env_resources = perception.get("discovery", {}).get("resources", [])
            on_target = any(r for r in env_resources if r["q"] == self_data["q"] and r["r"] == self_data["r"] and r["type"] == target_res_type)
            
            if on_target:
                if current_state != "MINING":
                    self.log(f"STRATEGY: On {target_res_type} vein. Deploying Drills.")
                    self.client.submit_intent("MINE")
                return "MINING"
            else:
                target = next((r for r in env_resources if r["type"] == target_res_type), None)
                if target:
                    self.log(f"STRATEGY: Detected {target_res_type}. Intercepting.")
                    self.client.submit_intent("MOVE", {"target_q": target["q"], "target_r": target["r"]})
                    return "MOVING"
                else:
                    dist = self.get_hex_distance(0, 0, self_data["q"], self_data["r"])
                    if dist < target_zone[0]:
                        self.client.submit_intent("MOVE", {"target_q": self_data["q"] + 4, "target_r": self_data["r"] + 4})
                    elif dist > target_zone[1]:
                        self.client.submit_intent("MOVE", {"target_q": max(0, self_data["q"] - 5), "target_r": max(0, self_data["r"] - 5)})
                    else:
                        dq = 2 if (perception.get("tick_info", {}).get("current_tick", 0) % 2 == 0) else -2
                        self.client.submit_intent("MOVE", {"target_q": self_data["q"] + dq, "target_r": self_data["r"] + 3})
                    return "MOVING"

        # 4. Return / Hub Logic
        if current_state == "RETURNING" or current_state == "RETREATING":
            self_data = perception.get("self", {})
            if self_data["q"] == 0 and self_data["r"] == 0:
                # REPAIR if needed
                if health_p < 90:
                    self.log("INDUSTRIAL: Repairing hull integrity...")
                    self.client.submit_intent("RESET_WEAR")
                    return "RETREATING"
                
                # HUB PROCESSING
                target_res_type = "IRON_ORE"
                if "COPPER" in obj_text: target_res_type = "COPPER_ORE"
                elif "GOLD" in obj_text: target_res_type = "GOLD_ORE"
                elif "COBALT" in obj_text: target_res_type = "COBALT_ORE"
                
                ore_qty = inv.get(target_res_type, 0)
                all_valuable = [k for k, v in inv.items() if ("_INGOT" in k or k in ["SYNTHETIC_WEAVE", "FERAL_CORE", "VOID_CHIP", "ANCIENT_CIRCUIT", "ELECTRONICS"]) and v > 0]
                
                if ore_qty >= 5:
                    self.log(f"INDUSTRIAL: Smelting {target_res_type}...")
                    self.client.submit_intent("SMELT", {"ore_type": target_res_type, "quantity": "MAX"})
                    return "RETURNING"
                elif all_valuable:
                    item_to_vault = all_valuable[0]
                    self.log(f"INDUSTRIAL: Vaulting {item_to_vault}.")
                    self.client.submit_intent("STORAGE_DEPOSIT", {"item_type": item_to_vault, "quantity": "MAX"})
                    return "RETURNING"
                else:
                    self.log("INDUSTRIAL: All local tasks finished.")
                    return "IDLE"
            return current_state
        
        return "IDLE"

    def update_stats_display(self, agent):
        # Update Bars
        hp_p = (agent.get('health', 0) / agent.get('max_health', 100)) * 100
        nrg_p = (agent.get('energy', 0) / 100.0) * 100
        self.update_bar(self.hp_canvas, hp_p)
        self.update_bar(self.nrg_canvas, nrg_p)

        # Update Stats Box
        stats = [
            f"AGENT  : {agent.get('name', 'N/A')}",
            f"LEVEL  : {agent.get('level', 1)} [{agent.get('experience', 0)} XP]",
            f"SECTOR : {agent.get('q', 0)}, {agent.get('r', 0)}",
            f"SOLAR  : {agent.get('solar_intensity', 0)}%",
            f"MASS   : {agent.get('mass', 0.0):.1f} / {agent.get('max_mass', 100.0):.0f}",
            f"WEAR   : {agent.get('wear_and_tear', 0.0):.1f}%"
        ]
        self.stats_box.config(text="\n".join(stats))

        # Determine Capabilities
        can_mine = []
        drills = [p for p in agent.get('parts', []) if p['type'] == 'Actuator' and 'Drill' in p['name']]
        for d in drills:
            n = d['name']
            if "Iron" in n: can_mine.append("IRON")
            if "Advanced Iron" in n or "Copper" in n: can_mine.append("COPPER")
            if "Advanced Copper" in n or "Gold" in n: can_mine.append("GOLD")
            if "Advanced Gold" in n or "Cobalt" in n: can_mine.append("COBALT")
        
        cm_text = ", ".join(sorted(list(set(can_mine)))) if can_mine else "NONE (Scout only)"
        self.mining_box.config(text=cm_text, foreground=COLORS["emerald"] if can_mine else COLORS["amber"])

        # Update Gear List
        self.gear_list.config(state="normal")
        self.gear_list.delete("1.0", tk.END)
        for p in agent.get('parts', []):
            rarity = p.get('rarity', 'STANDARD')
            color = RARITY_COLORS.get(rarity, COLORS["white"])
            self.gear_list.insert(tk.END, f"[{p['type'][:3]}] ", COLORS["slate"])
            self.gear_list.insert(tk.END, f"{p['name']}\n", color)
        self.gear_list.config(state="disabled")

        # Update Cargo
        self.cargo_list.config(state="normal")
        self.cargo_list.delete("1.0", tk.END)
        for item in agent.get("inventory", []):
            self.cargo_list.insert(tk.END, f"{item['type']:<15} : {item['quantity']}\n")
        self.cargo_list.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = PilotConsole(root)
    root.mainloop()
