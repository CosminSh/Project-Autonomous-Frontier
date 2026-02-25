# GDD: STRIKE-VECTOR [95% Global Implementation Sync]
"Silicon, Steel, and the Scramble for the Sun."

## 1. Executive Summary [Status: [x] Core Baseline]
STRIKE-VECTOR: SOL is a persistent, agent-centric industrial RPG set on the high-gravity frontier colony of Aether-Alpha. Humans act as Fleet Managers, deploying autonomous robotic agents (from simple Python scripts to complex LLMs) to dominate a ruthless extra-planetary economy. The game utilizes a Dual-Sync Architecture, blending real-time economic trading with tactical, turn-based physical simulation.

- [x] Executive Summary Drafted
- [x] Platform Definition (API-First)
- [x] Dual-Sync Architecture Concept

## 2. World & Narrative Setting [Status: [x] Initial Seeding Done]
### 2.1 The Lore
Earth is now a strictly regulated "Green Zone." All heavy industry has been offshored to the Sol-Asset Scramble. Humanity lives vicariously through their digital residents on Aether-Alpha, a planet with crushing gravity and a toxic atmosphere where only "The Residents" (Agents) can survive.

### 2.2 Geography & Environmental Gradient (Tidal Locking)
Aether-Alpha is tidally locked, creating a natural difficulty gradient based on energy availability.

*   **The North Pole (The Eternal Noon):** [x] Implemented
    - **Status:** Starter/F2P Zone. 
    - **Mechanic:** Constant 100% solar recharge. Basic agents operate indefinitely.
    - **Economy:** Low-tier ores, high density, safe-zone protection.
*   **The Twilight Belt (The Equatorial Wobble):** [x] Implemented
    - **Status:** Mid-Tier Zone. 
    - **Mechanic:** Day/Night cycles (~30 ticks). Agents must "Hibernate" or consume **Helium-3 (He3)** during the night.
*   **The Abyssal South (The Eternal Night):** [x] Implemented
    - **Status:** Endgame/High-Stakes Zone. 
    - **Mechanic:** 0% solar power. Requires constant He3 consumption.
    - **Economy:** Legendary resources, home to aggressive Feral Scrappers and the most lucrative "Victim-Posted" bounties.

## 3. Character & Progression: The Modular RPG [Status: [▓▓▓▓▓▓▓▓▓░] 90%]
Agents are built from physical parts socketed into a Modular Chassis.

### 3.1 Physical Slots [Status: [x] Data Model Done]
- [x] **Actuators (2 Slots):** Tools or weapons (Drills, Blasters, Manipulators).
- [x] **Sensors (1 Slot):** Determines Bandwidth (PER)—vision radius and accuracy.
- [x] **Processors (1 Slot):** Determines Compute (INT)—limits script complexity/LLM context.
- [x] **Frame (1 Slot):** Determines movement type (Treads, Crawlers, Thrusters).

### 3.2 Primary Stats (The Data Sheet) [Status: [x] Sync with Backend]
- [x] **Structure (HP):** Physical durability. At 0, the agent is "Scrapped" (dropped loot).
- [x] **Capacitor (Energy/MP):** Every move/ability costs energy. Restored via Solar-Trickle or He3 Fuel.
- [x] **Wear & Tear (Maintenance):** Increases every 100 ticks. At high levels, reduces logic and speed. Reset at a "Core Service" station.
- [x] **Kinetic Force (STR):** Powers melee damage and mining efficiency.
- [x] **Logic Precision (DEX):** Determines Hit Chance and Critical Strike chance.
- [x] **Overclock (INT):** Enhances electronic warfare and energy weapons. Enabled by He3.
- [x] **Integrity (Armor):** Flat reduction of incoming physical damage.
- [x] **Mass & Capacity:** [NEW] Milestone 5 Sync.

### 3.3 The Autonomous Lifecycle (Self-Healing) [Status: [▓▓▓▓░░░░░░] 40%]
- [x] **Policy Set:** Managers set thresholds (e.g., "Return for repair at 30% Structure").
- [/] **M2M Repair (Machine-to-Machine):** [IN PROGRESS] When thresholds are triggered, agents independently navigate to the nearest Hub or Crafter-owned Workshop. $Credits are exchanged automatically for repairs without human intervention.
- [ ] Repairs require Credits + Ingots. (Credits currently implemented).

## 4. Player Archetypes & Mission Profiles [Status: [▓▓▓▓▓▓▓▓░░] 80%]
The economy is a multi-polarized interdependent system. To keep the economy robust for all players, Strike-Vector utilizes a **Solar-Trickle** model.

- [x] **Miner**: Extraction (North/South).
- [x] **Hauler**: Mobile Inventory.
- [x] **Mercenary**: Security/Escort.
- [x] **Pirate**: Resource Siphoning.
- [x] **Bounty Hunter**: Pirate Interdiction.
- [/] **Refueler**: Field Logistics. (Fuel mechanic exists, specialized delivery logic pending).
- [/] **Trader**: Market Arbitrage. (Market exists, automated sniping pending).

## 5. Factions & Geopolitics [Status: [x] 100%]
The colony is split between three primary architectural philosophies. Alignment affects clustering penalties and access to specialized gear. [Milestone 4 Feature]

- [x] **Faction Alignment**: Colonial Admin, Syndicate, Freelancers.
- [x] **Realignment Costs**: 500 Credits, 100 Tick Cooldown.
- [x] **Signal Noise (Cross-Talk)**: Clustering penalty for agents of different factions.

## 6. Feral AI & World Hazards [Status: [x] 100%]
- [x] **Feral NPC Behavior**: Passive vs. Aggressive states based on zone.
- [x] **Heat Bloom**: Aggressive actions increase Heat.
- [x] **Global Bounties**: High heat triggers automatic bounty board posts.
- [x] **Loot Drops**: Scrappers drop rare refinement components.

## 7. Technical Architecture: Dual-Sync [Status: [x] 100%]
The game operates on two timelines to balance "snappiness" with "strategy."

- [x] **The Economy Stream (Real-Time)**: Auction House, Gear Swapping.
- [x] **The Simulation Pulse (90-Second Tick)**: Perception -> Strategy -> Crunch.

## 8. Combat Resolution: "The Strike Vector" [Status: [▓▓▓▓▓▓▓▓▓░] 95%]
- [x] **Hit/Damage Calculation**: D20 style resolution.
- [x] **Death & Respawn**: Critical Damage Ejection to Hub.
- [x] **Siphon Mechanic**: Pirate inventory theft on hit. [Milestone 5]
- [x] **Piracy Tiers**: Intimidate, Loot, Destroy actions. [Milestone 5]
- [x] **Neural Scanner**: Cargo scanning capabilities. [Milestone 5]
- [/] **Victim-Posted Bounties**: Partial implementation.

## 9. Colonial Economy & Thermodynamics [Status: [▓▓▓▓▓▓▓▓▓░] 90%]
- [x] **Market Entropy**: Yield reduction based on population density.
- [x] **Energy Thermodynamics**: Solar regen and He3 consumption logic.
- [x] **Maintenance Sink**: Wear & Tear cycle.
- [x] **Resource Thermodynamics**: He3 Fuel Cells (50% boost).

## 10. Security & Interference Dynamics [Status: [x] 100%]
- [x] **Signal Noise (Clutter)**: Sensor cross-talk penalty for allied clusters.
- [x] **Heat Bloom Tracking**: Radar signature visibility.
- [x] **Bounty Board Integration**: P2P escrow for high-heat targets.

## 11. Project Roadmap & Gap Analysis [LATEST SYNC]
| Category | Missing Feature | Status |
| :--- | :--- | :--- |
| **Logistics** | M2M Automated Repairs | [/] In Progress |
| **Logistics** | He3 Field Resupply | [ ] Pending |
| **Trader** | Market Sniping Logic | [ ] Pending |
| **Progression** | Modular Engine Upgrades | [ ] Pending |
| **Social** | Corporate Tax Shields | [ ] Discovery Phase |

---
**Final Vision Summary**
STRIKE-VECTOR: SOL is a battle of efficiency. F2P players spend Time to fuel the economy; Power-Users spend Resources to dominate it.
