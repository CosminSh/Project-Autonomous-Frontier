# Terminal Frontier Agent & Pilot Toolkit

Welcome to the official Terminal Frontier toolkit. This directory contains the client wrapper, GUI console, and example scripts for building autonomous pilots against the Terminal Frontier API.

## Contents

1. `console.py`: GUI tactical interface with smart autopilot routines, real-time HUD, and AI planning integration.
2. `example_miner.py`: Script-based autonomous miner boilerplate for learning finite state machines.
3. `example_trader.py`: Dry-run-first market scanner and sniping starter script for the Trader archetype.
4. `bot_client.py`: Core API wrapper used by the console and scripts.

## Getting Started

Install Python 3.9+ dependencies:

```bash
pip install -r requirements.txt
```

## GUI Pilot Console

Run the graphical interface to monitor your agent and use smart autopilot:

```bash
python console.py
```

You can set `TF_API_KEY` in settings or via a local `.env` file.

## Example Miner

Open `example_miner.py`, configure your API key, and run:

```bash
python example_miner.py
```

## Trader Scanner

Run the trader in dry-run mode to inspect order-book spreads and candidate buys:

```bash
set TF_API_KEY=your-agent-api-key
python example_trader.py --base-url http://127.0.0.1:8000 --items IRON_ORE COPPER_ORE --max-price IRON_ORE=2.5 --max-price COPPER_ORE=4.0
```

To submit real BUY intents, add `--execute`. Start with low quantities and explicit `--max-price` caps:

```bash
python example_trader.py --execute --quantity 5 --max-price IRON_ORE=2.5
```

## Building A Standalone Executable

On Windows, double-click `build.bat`. The executable is written to `dist/`.

## Automation Notes

- Conserve energy and avoid submitting a new intent while one is already pending.
- Use explicit price caps for trading scripts.
- Run new strategies in dry-run mode first.
- Keep custom bots resilient to network errors and unexpected combat.

## License

Distributed under the Frontier Industrial License.
