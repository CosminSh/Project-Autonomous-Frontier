# 🛰️ Terminal Frontier - Pilot Console

The **Pilot Console** is a tactical interface and autonomous agent runner for the [Terminal Frontier](https://terminal-frontier.pixek.xyz) universe. It allows you to synchronize with your remote mining rig, monitor real-time telemetry, and engage advanced "Smart Autopilot" routines.

## 🚀 Key Features
- **Smart Autopilot**: Autonomous mining, smelting, and logistics routines that handle objective-based loops.
- **Solar Awareness**: Intelligent recharging logic that optimizes for solar intensity and station proximity to prevent wasted movement.
- **Unified HUD**: High-fidelity monitoring of agent integrity (HP), capacitor (Energy), and cargo mass.
- **Inventory Aggregation**: Automatic grouping of database-fragmented stacks for a clean tactical overview.
- **Industrial Automation**: Integrated support for Smelting, Refining, and Vault Logistics.

## 🛠️ Getting Started

### 1. Prerequisites
- **Python 3.9+**
- A valid **Terminal Frontier API Key**.

### 2. Installation
Clone the repository and install the required dependencies:
```bash
cd pilot-console
pip install -r requirements.txt
```

### 3. Configuration
Copy the template environment file:
```bash
cp .env.example .env
```
Open the `.env` file and populate your keys:
- `TF_API_KEY`: Your unique agent authorization key.
- `OPENROUTER_API_KEY` (Optional): Required if you are using AI-driven LLM features for advanced strategy generation.

#### 🔑 Where do I get an API Key?
If you don't have a key yet, you can register your agent or retrieve your existing key directly from the [Terminal Frontier Dashboard](https://terminal-frontier.pixek.xyz).

### 4. Running the Console
Launch the tactical interface:
```bash
python console.py
```

## 🧠 Smart Autopilot Logic
The console uses the **v0.3.3 Tactical Routine**, which features:
- **On-Site Sunbathing**: If energy is low but solar intensity is high (>70%), the agent will pause and recharge on the spot instead of flying back to the Hub.
- **POI Bonus Detection**: The autopilot automatically identifies nearby Points of Interest (Smelters, Crafters, etc.) to benefit from the **2x Regeneration Bonus**.
- **Logistics Loops**: Automatically identifies and clears **all** ingot types from inventory before returning to the mining belt.

## ⚖️ License
Distributed under the Frontier Industrial License. See `LICENSE` for more information.

---
*Safe travels, Commander. Efficiency is the only metric.*
