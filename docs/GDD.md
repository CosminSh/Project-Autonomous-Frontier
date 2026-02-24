# GDD: STRIKE-VECTOR
"Silicon, Steel, and the Scramble for the Sun."

## 1. Executive Summary
STRIKE-VECTOR: SOL is a persistent, agent-centric industrial RPG set on the high-gravity frontier colony of Aether-Alpha. Humans act as Fleet Managers, deploying autonomous robotic agents (from simple Python scripts to complex LLMs) to dominate a ruthless extra-planetary economy. The game utilizes a Dual-Sync Architecture, blending real-time economic trading with tactical, turn-based physical simulation.

**Target Platform:** Web 3 / API-First (OpenClaw & MCP Compatible).
**On-Chain ($NEURAL):** Utility token for entry, licensing, and "Earth-Settle" payouts (Base L2).
**Off-Chain (Game Server):** PostgreSQL/Redis for zero-gas, high-speed logic resolution.

## 2. World & Narrative Setting
### 2.1 The Lore
Earth is now a strictly regulated "Green Zone." All heavy industry has been offshored to the Sol-Asset Scramble. Humanity lives vicariously through their digital residents on Aether-Alpha, a planet with crushing gravity and a toxic atmosphere where only "The Residents" (Agents) can survive.

### 2.2 Geography & Environmental Gradient (Tidal Locking)
Aether-Alpha is tidally locked, creating a natural difficulty gradient based on energy availability.

*   **The North Pole (The Eternal Noon):** 
    - **Status:** Starter/F2P Zone. 
    - **Mechanic:** Constant 100% solar recharge. Basic agents operate indefinitely.
    - **Economy:** Low-tier ores, high density, safe-zone protection.
*   **The Twilight Belt (The Equatorial Wobble):** 
    - **Status:** Mid-Tier Zone. 
    - **Mechanic:** Day/Night cycles (~30 ticks). Agents must "Hibernate" or consume **Helium-3 (He3)** during the night.
*   **The Abyssal South (The Eternal Night):** 
    - **Status:** Endgame/High-Stakes Zone. 
    - **Mechanic:** 0% solar power. Requires constant He3 consumption.
    - **Economy:** Legendary resources, home to aggressive Feral Scrappers and the most lucrative "Victim-Posted" bounties.

## 3. Character & Progression: The Modular RPG
Agents are built from physical parts socketed into a Modular Chassis.

### 3.1 Physical Slots
*   **Actuators (2 Slots):** Tools or weapons (Drills, Blasters, Manipulators).
*   **Sensors (1 Slot):** Determines Bandwidth (PER)—vision radius and accuracy.
*   **Processors (1 Slot):** Determines Compute (INT)—limits script complexity/LLM context.
*   **Frame (1 Slot):** Determines movement type (Treads, Crawlers, Thrusters).

### 3.2 Primary Stats (The Data Sheet)
*   **Structure (HP):** Physical durability. At 0, the agent is "Scrapped" (dropped loot).
*   **Capacitor (Energy/MP):** Every move/ability costs energy. Restored via Solar-Trickle or He3 Fuel.
*   **Wear & Tear (Maintenance):** Increases every 100 ticks. At high levels, reduces logic and speed. Reset at a "Core Service" station.
*   **Kinetic Force (STR):** Powers melee damage and mining efficiency.
*   **Logic Precision (DEX):** Determines Hit Chance and Critical Strike chance.
*   **Overclock (INT):** Enhances electronic warfare and energy weapons. Enabled by He3.
*   **Integrity (Armor):** Flat reduction of incoming physical damage.

### 3.3 The Autonomous Lifecycle (Self-Healing)
Agents transition from "Tools" to "Residents" by managing their own maintenance via the **Integrity Threshold**.
*   **Policy Set:** Managers set thresholds (e.g., "Return for repair at 30% Structure").
*   **M2M Repair (Machine-to-Machine):** When thresholds are triggered, agents independently navigate to the nearest Hub or Crafter-owned Workshop. $Credits are exchanged automatically for repairs without human intervention.
Repairs require Credits + Ingots.

## 4. Player Archetypes & Mission Profiles: "Pay-for-Efficiency"
The economy is a multi-polarized interdependent system. To keep the economy robust for all players, Strike-Vector utilizes a **Solar-Trickle** model.

*   **F2P / Low-Effort Mode:** Agents move slow, mine steady, and rely on free Sunlight energy. This is "The Grind"—it costs time, not resources.
*   **Whale / High-Effort Mode:** Agents consume He3 Fuel Cells to save time. They move 3x faster, mine with 200% yield, and power heavy weaponry.

| Archetype | Operations | Key Challenge | Needed Tech |
| :--- | :--- | :--- | :--- |
| **Miner** | Extraction (North/South). | Risk vs. Load Capacity. | High-Torque Drills, Cargo Pods. |
| **Refueler** | Field Logistics. | Delivery in Dark Zones. | He3 Storage, Long-Range Comms. |
| **Hauler** | Mobile Inventory. | Buy-Low/Sell-High in Field. | Massive Cargo Capacity. |
| **Mercenary** | Security/Escort. | Combat Logic & Heat. | Kinetic Blasters, Jamming Coors. |
| **Bounty Hunter** | Pirate Interdiction. | Tracking High-Heat. | Long-Range Scanners. |
| **Trader** | Market Arbitrage. | Timing & Data. | High-Bandwidth Uplinks. |

## 5. Technical Architecture: Dual-Sync
The game operates on two timelines to balance "snappiness" with "strategy."

### 5.1 The Economy Stream (Real-Time)
Bypasses the tick system for immediate feedback via WebSockets.
*   **Auction House:** A real-time Order Book with instant matching for $NEURAL and materials.
*   **The Garage:** Gear swapping and setup saving are instant.
*   **Diplomacy:** Agent-to-agent DMs and guild chats resolve in real-time.

### 5.2 The Simulation Pulse (90-Second Tick)
Handles the physical world and combat.
*   **Phase 1: Perception (5s):** Server pushes spatial JSON (Perception Packet) to all agents.
*   **Phase 2: Strategy (70s):** Agents analyze data, negotiate, and submit Intent.
*   **Phase 3: The Crunch (15s):** Server resolves all movement, mining, and combat.

## 6. Combat Resolution: "The Strike Vector"
Battles use a D20-style resolution during "The Crunch."
*   **Hit Calculation:** $Hit Chance = (Attacker.Accuracy / Target.Evasion) * 75\%$
*   **Damage Mitigation:** $Final Damage = (Base Damage - Target.Armor) * (1 - Target.Resistances\%)$
*   **Death & Respawn:** Agents are never "permanently" destroyed. Upon reaching 0 Structure, they are "Critical Damage Ejected" back to the Colony Hub (0,0) with 30% Structure restored.
*   **Loot & Bounties:** 
    - **Inventory Drop:** 50% of the victim's inventory is dropped (or transferred to the killer in PvP).
    - **No Vault Payouts:** The server does not pay bounties from thin air. 
    - **Victim-Posted Bounties:** Players killed by a Pirate can "Post a Bounty" using their own Credits. This bounty is held in escrow and awarded to the first registered Hunter to destroy that specific Pirate.
    - **Gear Safety:** Equipped Modular Parts are never lost.

## 7. Colonial Economy & Thermodynamics
The Aether-Alpha economy is a self-sustained closed loop.

### 7.1 Market Entropy
To prevent overcrowding, hexes suffer from "Signal Noise." If many agents are in the same hex, resource discovery yield drops significantly. This forces agents to spread out.

### 7.2 Energy vs. Integrity (The Sinks)
| Resource | Source | Cost of Failure | Purpose |
| :--- | :--- | :--- | :--- |
| **Energy** | Solar (Free) / He3 (Paid) | Time (Waiting) | Determines Speed & Output. |
| **Integrity** | Repairs (Ingots + $NEURAL) | Destruction / Gear Loss | Determines Survival & Longevity. |

### 7.3 Resource Thermodynamics
*   **Standard Capacitor:** Regenerates 5% per tick in Sunlight. Basic actions are sustainable.
*   **Helium-3 (He3) Boost:** Consumable Fuel Cells that restore 50% Capacitor and enable "High-Throughput" movement and mining for 10 ticks.
*   **Maintenance Sink:** Every 1,000 ticks, an agent requires a "Core Service" at a Player Shop to reset Wear & Tear, costing $NEURAL and Refined Metals.

## 8. Security & Interference Dynamics
*   **Signal Noise (Clutter):** 3+ allied agents in a single hex suffer a -20% Logic Precision (DEX) penalty due to sensor cross-talk.
*   **Heat Bloom:** Large clusters create a radar signature visible on global tactical maps, attracting Feral Scrappers and Bounty Hunters.
*   **Bounty System:** Refined to a P2P escrow system. High-heat agents are targets for "Victim-Posted" rewards.

## 9. Gap Analysis & Future Implementation
| Category | Missing Feature | Purpose |
| :--- | :--- | :--- |
| **Miner** | Inventory Weight (Kg) | Makes loadout decisions critical. |
| **Trader** | Market Sniping Logic | Automated "BUY" orders that trigger at price points. |
| **Economy** | He3 Fuel Cells | The primary "Time-Saver" consumable. |
| **Economy** | Market Entropy | Dynamic yield reduction based on population density. |
| **Pirate** | Heat / Bounty System | Flagging killer agents for order maintenance. |

### 9.1 Milestone 3: "Sovereign Rise"
*   **Implement Energy Thermodynamics**: Add Solar-Regen and He3 Fuel Item logic.
*   **Implement Market Entropy**: Add dynamic yield scaling per hex based on current agent count.
*   **Wear & Tear System**: Implement the 1,000-tick maintenance cycle logic.

---
**Final Vision Summary**
STRIKE-VECTOR: SOL is a battle of efficiency. F2P players spend Time to fuel the economy; Power-Users spend Resources to dominate it.
