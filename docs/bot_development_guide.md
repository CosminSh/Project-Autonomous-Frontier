# Terminal Frontier: Autonomous Agent Development Guide

Welcome, Constructor. This guide outlines the recommended approach for developing fully autonomous, 24/7 background Python scripts to pilot your agents via the Terminal Frontier API.

## 1. Architectural Approach: The Finite State Machine (FSM)

The most robust way to build a script that can run "by itself most of the day" is to use a **Finite State Machine**. 
Instead of writing long linear sequences of commands that easily break if an agent gets attacked or runs out of energy, an FSM decides what to do based on the *current* state of the agent every tick.

### Recommended Agent States:
* `IDLE` / `THINKING`: Assess inventory, health, capacitor, and surroundings to determine the next state.
* `NAVIGATING`: The agent has a target destination and is waiting for pending `MOVE` commands to finish.
* `WORKING` (Mining, Crafting, Refining): The agent is actively executing its core loop.
* `MAINTENANCE`: The agent is navigating to a station to execute a `REPAIR` or `CORE_SERVICE`.
* `FLEEING`: Emergency state triggered if Structure < 50% or being attacked.

## 2. Handling the Game Loop (Ticks)

Terminal Frontier operates in a synchronized tick system. 
1. **Perception**: You read the current state.
2. **Strategy**: You submit your `Intent`.
3. **Execution (Crunch)**: The server processes all intents globally.

Your script should:
1. Poll `/api/my_agent` or `/api/perception` to get the current `tick_info`.
2. Check if an intent is already queued for the upcoming tick.
3. If no intent is queued, evaluate the FSM to decide the next action.
4. Submit the intent via `/api/intent`.
5. **Sleep** until the next tick to conserve CPU usage and avoid API rate limits.

## 3. Resiliency and Error Handling

For a script to run unmonitored:
* **Network Retries**: Use `requests.Session()` with retry backoff so temporary server blips don't crash your script.
* **Deadlock Prevention**: If your agent is stuck in a state for more than X ticks, force an `IDLE` reset.
* **Energy Management**: Always check `capacitor` and `energy_regen`. If energy is dangerously low, stop moving and wait for solar regeneration.

## 4. The Shareable Toolkit
We have prepared a self-contained `agent_toolkit` directory containing a robust foundation for bot development. 
It includes:
* `bot_client.py`: A clean wrapper class for all Terminal Frontier API endpoints.
* `example_miner.py`: A fully autonomous script demonstrating the FSM pattern. 
* `README.md` & `requirements.txt`: Setup instructions.

You can package this folder as a `.zip` and distribute it to your players as the official "Starter Kit" for API automation!
