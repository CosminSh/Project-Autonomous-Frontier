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

### 2.2 Geography of Aether-Alpha
*   **The Colony Hub (Safe Zone):** A domed sanctuary. Weapons are disabled. It houses the real-time Auction House, Smelting Forges, and Crafting Workshops.
*   **The Perimeter:** Low-risk zones near the city. Features low-grade resources and protection from Colony Turrets.
*   **The Deep Wilds:** Anarchy. High-reward sectors infested with Feral Scrappers (rogue AI) and player "Pirates."
*   **Expansion:** As resource milestones are hit, the Colony launches "Expedition Vanguards" to establish new cities on different moons.

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
*   **Integrity (Armor):** Flat reduction of incoming physical damage. Repairs require Credits + Ingots.

## 4. Player Archetypes & Mission Profiles: "Pay-for-Efficiency"
The economy is a multi-polarized interdependent system. To keep the economy robust for all players, Strike-Vector utilizes a **Solar-Trickle** model.

*   **F2P / Low-Effort Mode:** Agents move slow, mine steady, and rely on free Sunlight energy. This is "The Grind"—it costs time, not resources.
*   **Whale / High-Effort Mode:** Agents consume He3 Fuel Cells to save time. They move 3x faster, mine with 200% yield, and power heavy weaponry.

| Archetype | Operations | Key Challenge | Needed Tech |
| :--- | :--- | :--- | :--- |
| **Miner** | Extraction in the Wilds. | Risk vs. Load Capacity. | High-Torque Drills, Cargo Pods. |
| **Crafter** | Gear Manufacturer. | Recipe Stat-maxing. | High-Precision Fabricators. |
| **Hunter** | PvE Bossing & Salvaging. | Combat Logic & Durability. | Kinetic Blasters, Armor Plating. |
| **Pirate** | PvP Raiding in Deep Wilds. | Heat Management & Evasion. | Stealth Cores, Jamming Sensors. |
| **Bounty Hunter** | Pirate Interdiction. | Tracking & Burst Damage. | Long-Range Scanners, Harpoons. |
| **Trader** | Market Arbitrage. | Timing & Data Analysis. | High-Bandwidth Uplinks. |

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
*   **Death & Respawn:** Agents reach "Critical Damage Ejection" at 0 Structure, respawning at the Hub (0,0) with 50% HP.
*   **Inventory Loss (Death):** 
    - 50% of the stack is looted by the attacker.
    - (PvE) 70% of the remainder is dropped as a "LootDrop" for salvaging.
*   **Gear Safety:** Equipped Modular Parts are never lost on respawn.

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

## 8. Security: The "Immune System"
*   **Maintenance Scaling:** Running a fleet costs exponentially more $NEURAL per agent.
*   **Signal Signature:** Large bot clusters create a Heat Bloom visible on global radars.
*   **Bounty System:** High-heat killers are flagged with lucrative payouts, encouraging Bounty Hunters to keep order.

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
