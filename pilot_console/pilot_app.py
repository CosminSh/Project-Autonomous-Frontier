import tkinter as tk
import customtkinter as ctk
import threading
import queue
import time
from bot_logic import BotManager
from llm_bridge import LLMBridge

# Sets the appearance of the app
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PilotConsoleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Terminal Frontier | PILOT CONSOLE v0.2.0")
        self.geometry("1000x700")

        self.bot = None
        self.llm = None
        self.log_queue = queue.Queue()
        self.base_url = "https://terminal-frontier.pixek.xyz"

        # Grid layout 1x2 (Sidebar + Main)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_sidebar()
        self._create_main_content()
        self._show_login()

    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="PILOT CONSOLE", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=20)

        self.status_indicator = ctk.CTkLabel(self.sidebar, text="● OFFLINE", text_color="gray", font=ctk.CTkFont(size=12))
        self.status_indicator.pack(pady=5)

        self.btn_dashboard = ctk.CTkButton(self.sidebar, text="DASHBOARD", command=self._show_dashboard)
        self.btn_dashboard.pack(pady=10, padx=20)

        self.btn_chat = ctk.CTkButton(self.sidebar, text="TACTICAL CHAT", command=self._show_chat)
        self.btn_chat.pack(pady=10, padx=20)

        self.btn_logs = ctk.CTkButton(self.sidebar, text="SYSTEM LOGS", command=self._show_logs)
        self.btn_logs.pack(pady=10, padx=20)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar, text="Appearance:", anchor="w")
        self.appearance_mode_label.pack(side="bottom", padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.pack(side="bottom", padx=20, pady=(0, 20))
        self.appearance_mode_optionemenu.set("Dark")

    def _create_main_content(self):
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Login View
        self.login_frame = ctk.CTkFrame(self.main_container)
        self.login_label = ctk.CTkLabel(self.login_frame, text="AUTHENTICATION REQUIRED", font=ctk.CTkFont(size=16, weight="bold"))
        self.login_label.pack(pady=20)

        self.entry_api_key = ctk.CTkEntry(self.login_frame, placeholder_text="Game API Key", width=300)
        self.entry_api_key.pack(pady=10)

        self.entry_openrouter_key = ctk.CTkEntry(self.login_frame, placeholder_text="OpenRouter API Key (for LLM Chat)", width=300, show="*")
        self.entry_openrouter_key.pack(pady=10)

        self.btn_login = ctk.CTkButton(self.login_frame, text="INITIALIZE LINK", command=self._initialize_system)
        self.btn_login.pack(pady=20)

        self.version_check_label = ctk.CTkLabel(self.login_frame, text="Checking server compatibility...", font=ctk.CTkFont(size=10))
        self.version_check_label.pack(pady=10)

        # Dashboard View
        self.dashboard_frame = ctk.CTkScrollableFrame(self.main_container)
        self._setup_dashboard_widgets()

        # Chat View
        self.chat_frame = ctk.CTkFrame(self.main_container)
        self._setup_chat_widgets()

        # Logs View
        self.logs_frame = ctk.CTkFrame(self.main_container)
        self.logs_text = ctk.CTkTextbox(self.logs_frame, width=600, height=400)
        self.logs_text.pack(expand=True, fill="both", padx=10, pady=10)

    def _setup_dashboard_widgets(self):
        # Stat Cards
        self.stats_container = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        self.stats_container.pack(fill="x", pady=10)
        
        self.card_hp = self._create_stat_card(self.stats_container, "STRUCTURE", "100/100")
        self.card_energy = self._create_stat_card(self.stats_container, "CAPACITOR", "100%")
        self.card_cargo = self._create_stat_card(self.stats_container, "CARGO", "0.0/50.0")
        
        # Directive Display
        self.directive_frame = ctk.CTkFrame(self.dashboard_frame)
        self.directive_frame.pack(fill="x", pady=20, padx=10)
        self.directive_title = ctk.CTkLabel(self.directive_frame, text="ACTIVE DIRECTIVE", font=ctk.CTkFont(size=12, weight="bold"))
        self.directive_title.pack(pady=5)
        self.directive_text = ctk.CTkLabel(self.directive_frame, text="Target: IRON_ORE | Min Energy: 20% | Max Cargo: 90%", font=ctk.CTkFont(size=11))
        self.directive_text.pack(pady=5)

    def _create_stat_card(self, parent, title, value):
        card = ctk.CTkFrame(parent, width=150, height=100)
        card.pack(side="left", padx=10, expand=True)
        t_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"))
        t_label.pack(pady=(10, 0))
        v_label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=18, weight="bold"), text_color="#38bdf8")
        v_label.pack(pady=(0, 10))
        return v_label

    def _setup_chat_widgets(self):
        self.chat_history = ctk.CTkTextbox(self.chat_frame, state="disabled", height=400)
        self.chat_history.pack(expand=True, fill="both", padx=10, pady=(10, 0))
        
        self.chat_input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.chat_input_frame.pack(fill="x", padx=10, pady=10)
        
        self.entry_chat = ctk.CTkEntry(self.chat_input_frame, placeholder_text="Enter tactical command (e.g. 'Go mine gold and return home when 80% full')")
        self.entry_chat.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_chat.bind("<Return>", lambda e: self._send_chat())
        
        self.btn_send = ctk.CTkButton(self.chat_input_frame, text="SEND", width=80, command=self._send_chat)
        self.btn_send.pack(side="right")

    def _show_login(self):
        self.login_frame.grid(row=0, column=0, sticky="nsew")
        self.dashboard_frame.grid_forget()
        self.chat_frame.grid_forget()
        self.logs_frame.grid_forget()
        # Trigger compatibility check
        threading.Thread(target=self._check_version, daemon=True).start()

    def _check_version(self):
        try:
            resp = requests.get(f"{self.base_url}/api/metadata", timeout=5)
            if resp.ok:
                data = resp.json()
                if "continuous_mining" in data.get("features", []):
                    self.version_check_label.configure(text="Server compatible: v" + data.get("version", "???"), text_color="green")
                else:
                    self.version_check_label.configure(text="Server uses legacy mining logic. Some features may fail.", text_color="orange")
            else:
                self.version_check_label.configure(text="Could not reach server metadata.", text_color="red")
        except:
            self.version_check_label.configure(text="Connection error during check.", text_color="red")

    def _initialize_system(self):
        api_key = self.entry_api_key.get()
        llm_key = self.entry_openrouter_key.get()
        
        if len(api_key) < 10:
            self.version_check_label.configure(text="Invalid Game API Key", text_color="red")
            return

        self.bot = BotManager(api_key, self.base_url)
        if llm_key:
            self.llm = LLMBridge(llm_key)
        
        self.bot.start()
        self._show_dashboard()
        self.after(1000, self._update_loop)

    def _show_dashboard(self):
        if not self.bot: return
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self.login_frame.grid_forget()
        self.chat_frame.grid_forget()
        self.logs_frame.grid_forget()

    def _show_chat(self):
        if not self.bot: return
        self.chat_frame.grid(row=0, column=0, sticky="nsew")
        self.dashboard_frame.grid_forget()
        self.login_frame.grid_forget()
        self.logs_frame.grid_forget()

    def _show_logs(self):
        if not self.bot: return
        self.logs_frame.grid(row=0, column=0, sticky="nsew")
        self.dashboard_frame.grid_forget()
        self.chat_frame.grid_forget()
        self.login_frame.grid_forget()

    def _send_chat(self):
        cmd = self.entry_chat.get()
        if not cmd or not self.llm: return
        
        self.entry_chat.delete(0, tk.END)
        self._add_chat_msg("USER", cmd)
        
        # Process in thread to not freeze UI
        threading.Thread(target=self._process_llm, args=(cmd,), daemon=True).start()

    def _process_llm(self, text):
        self._add_chat_msg("TACTICAL", "Processing command...")
        result = self.llm.process_command(text, self.bot.directive)
        
        if "error" in result:
            self._add_chat_msg("ERROR", result["explanation"])
        else:
            self.bot.update_directive(result)
            self._add_chat_msg("TACTICAL", result["explanation"])

    def _add_chat_msg(self, sender, text):
        self.chat_history.configure(state="normal")
        self.chat_history.insert("end", f"[{sender}] {text}\n\n")
        self.chat_history.configure(state="disabled")
        self.chat_history.see("end")

    def _update_loop(self):
        if not self.bot or not self.bot.running: return
        
        # Update dashboard
        agent = self.bot.agent_data
        if agent:
            hp = f"{agent.get('health', 0)}/{agent.get('max_health', 100)}"
            energy = f"{agent.get('energy', 0)}%"
            cargo = f"{agent.get('mass', 0):.1f}/{agent.get('max_mass', 50):.1f}"
            
            self.card_hp.configure(text=hp)
            self.card_energy.configure(text=energy)
            self.card_cargo.configure(text=cargo)
            
            d = self.bot.directive
            self.directive_text.configure(text=f"Target: {d.target_resource} | Min Energy: {d.min_energy}% | Max Cargo: {d.max_cargo_percent}%")
            
            status_text = f"● {self.bot.status}"
            status_color = "green" if "EXTRACTING" in self.bot.status or "EN ROUTE" in self.bot.status else "orange"
            self.status_indicator.configure(text=status_text, text_color=status_color)

        # Update logs
        # Since BotManager currently just logs to console, 
        # for real GUI logs we would need to capture it. 
        # For now, let's just add a placeholder or simple poll.
        
        self.after(1000, self._update_loop)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

if __name__ == "__main__":
    app = PilotConsoleApp()
    app.mainloop()
