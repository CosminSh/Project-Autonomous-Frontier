# Terminal Frontier Agent Toolkit

Welcome to the official Agent automation toolkit! 
These scripts provide a robust foundation for programming your agents to operate continuously in the Terminal Frontier universe using Python.

## Files included:
1. `bot_client.py`: A clean wrapper class around the Terminal Frontier HTTP API. It handles authentication, retries, and intent submission seamlessly.
2. `example_miner.py`: A fully functional example of an active agent. It uses a **Finite State Machine** (FSM) architecture to loop indefinitely—finding ore, traveling to it, mining until full, returning to a market, selling, and repeating (as well as handling low battery incidents).

## Installation

1. Make sure you have Python 3.8+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Getting Started

1. Log in to the Terminal Frontier web interface to register an agent and acquire your **API Key** from the sidebar.
2. Open `example_miner.py` and replace `YOUR-API-KEY-HERE` with your actual token.
3. If running against a live server, update `BASE_URL` to point to the correct domain instead of `localhost`.
4. Run the bot!
   ```bash
   python example_miner.py
   ```

## Development Advice
- **Respect the Ticks**: The game updates in synchronized intervals (ticks). Polling the server aggressively in a `while True` loop without `time.sleep()` will result in IP bans/rate-limits. The example miner demonstrates how to safely wait for the tick to advance.
- **Fail Gracefully**: Networks are unstable, and game conditions change. If your agent is attacked or you run out of energy, your intended script sequence might fail. Using explicit "States" (like `IDLE`, `CHARGING`, `MINING`) helps your agent recover dynamically.
