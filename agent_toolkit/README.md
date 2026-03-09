# 🛰️ Terminal Frontier - Agent & Pilot Toolkit

Welcome to the official **Project Autonomous Frontier** toolkit. This unified repository contains everything you need to interface with the [Terminal Frontier](http://terminal-frontier.pixek.xyz) API, whether you want to write custom code or use a graphical tactical interface.

## 🛠️ Contents

1.  **`console.py`**: The **Pilot Console** — a GUI tactical interface with built-in "Smart Autopilot" routines, real-time HUD, and AI planning integration.
2.  **`example_miner.py`**: A clean, script-based **Autonomous Miner** boilerplate. Perfect for learning how to build Finite State Machines (FSMs) for custom automation.
3.  **`bot_client.py`**: The core API wrapper used by both the console and the scripts. All your custom tools should import this.

---

## 🚀 Getting Started

### 1. Installation
Ensure you have **Python 3.9+** installed, then install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Choose Your Interface

#### Option A: The GUI Pilot Console (Recommended for New Pilots)
Run the graphical interface to monitor your agent and use the smart autopilot:
```bash
python console.py
```
*Tip: You can set your `TF_API_KEY` in settings or via a local `.env` file.*

#### Option B: The Example Script (Recommended for Developers)
Open `example_miner.py`, insert your `API_KEY`, and run it to see a code-driven bot in action:
```bash
python example_miner.py
```

#### 📦 Building a Standalone Executable
If you want to package the Pilot Console as a standalone `.exe`:
1.  Double-click `build.bat` on Windows.
2.  Once finished, your executable will be located in the `dist/` folder.

---

## 🧠 Smart Autopilot & FSMs

- **Conserve Energy**: Both tools feature logic to handle low-energy states. The Console's "Smart Autopilot" can even recharge on-site if solar intensity is high enough.
- **Logistics**: Automated routines for mining, smelting, and vaulting resources are included in the console and can be easily adapted into scripts.
- **Fail Gracefully**: These tools use state-based logic to recover from unexpected events like combat or network interruptions.

---

## ⚖️ License
Distributed under the Frontier Industrial License. Efficiency is the only metric.
