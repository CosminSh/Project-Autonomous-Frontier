# GDD: Terminal Frontier [95% Global Implementation Sync]
"Silicon, Steel, and the Scramble for the Sun."

## 1. Executive Summary [Status: [x] Core Baseline]
Terminal Frontier is a persistent, agent-centric industrial RPG set on the high-gravity frontier colony of Aether-Alpha. Humans act as Fleet Managers, deploying autonomous robotic agents (from simple Python scripts to complex LLMs) to dominate a ruthless extra-planetary economy. The game utilizes a Dual-Sync Architecture, blending real-time economic trading with tactical, turn-based physical simulation.

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

### 3.1 Modular Slots & Rarity [Status: [▓▓░░░░░░░░] 20%]
Agents are built from physical parts socketed into a Modular Chassis. Every part now follows a **Rarity Hierarchy**: 
- `SCRAP` (Gray) | `STANDARD` (White) | `REFINED` (Blue) | `PRIME` (Yellow) | `RELIC` (Orange)

- [x] **Actuators (2 Slots):** Tools/Weapons (Drills, Blasters, Siphons).
- [x] **Sensors (1 Slot):** Determines PER (Vision/Scan).
- [x] **Processors (1 Slot):** Determines INT (Script logic/Context).
- [x] **Frame (1 Slot):** Determines base HP and Mass capacity.
- [x] **Power (1 Slot):** Determines Energy Regeneration and efficiency.

### 3.2 Randomized Gear: Affixes & Suffixes
Following the "Diablo 2" model, crafted gear is no longer deterministic. 
- **Base Type**: Determines the core stat (e.g., "Steel Drill" has base 10 kinetic force).
- **Prefixes/Suffixes**: Random bonuses added during crafting based on the recipe and luck.
    - *Example*: "Overclocked Steel Drill of the Void" (Prefix: +Energy, Suffix: +Critical Chance).
- **Progression**: High-tier gear requires rarer "Base Frames" and specific component combinations.

### 3.3 Unique Character Naming
To foster a sense of unique identity, every agent possesses a distinct name alongside its ID. 
- **Uniqueness**: Agent names must be unique across the colonial network.
- **Modification**: Fleet Managers can update an agent's name through the backend registry, provided the new name is not already claimed.
- **Narrative Weight**: Names are the primary "human" link to the digital residents, often reflecting their specialized roles (e.g., "The Gilded Siphon", "Iron-Lung VII").

### 3.2 Primary Stats (The Data Sheet) [Status: [x] Sync with Backend]
- [x] **Structure (HP):** Physical durability. At 0, the agent is "Scrapped" (dropped loot).
- [x] **Capacitor (Energy/MP):** Every move/ability costs energy. Restored via Solar-Trickle or He3 Fuel.
- [x] **Wear & Tear (Maintenance):** Increases every 100 ticks. At high levels, reduces logic and speed. Reset at a "Core Service" station.
- [x] **Kinetic Force (STR):** Powers melee damage and mining efficiency.
- [x] **Logic Precision (DEX):** Determines Hit Chance and Critical Strike chance.
- [x] **Overclock (INT):** Enhances electronic warfare and energy weapons. Enabled by He3.
- [x] **Integrity (Armor)::** Flat reduction of incoming physical damage.
- [x] **Mass & Capacity:** [NEW] Milestone 5 Sync.

### 3.3 The Autonomous Lifecycle (Self-Healing) [Status: [▓▓▓▓░░░░░░] 40%]
- [x] **Policy Set:** Managers set thresholds (e.g., "Return for repair at 30% Structure").
- [/] **M2M Repair (Machine-to-Machine)::** When thresholds are triggered, agents independently navigate to the nearest Hub or Workshop. $Credits + **Iron Ingots** are exchanged automatically for repairs.
- [x] **Repair Cost:** Credits (5/HP) + Iron Ingots (0.1/HP).
- [/] **He3 Canister Logistics:** Reusable canisters with metadata-tracked fill levels.
- [ ] **Gear Upgrading (The Forge)**: Spend resources and "Upgrade Modules" to increase the base stats of a part without rerolling affixes.

## 4. Player Archetypes & Mission Profiles [Status: [▓▓▓▓▓▓▓▓░░] 80%]
The economy is a multi-polarized interdependent system. To keep the economy robust for all players, Strike-Vector utilizes a **Solar-Trickle** model.

- [x] **Miner**: Extraction (North/South).
- [x] **Hauler**: Mobile Inventory.
- [x] **Mercenary**: Security/Escort.
- [x] **Pirate**: Resource Siphoning.
- [x] **Bounty Hunter**: Pirate Interdiction.
- [/] **Refueler**: Field Logistics. Uses **He3 Canisters** to resupply allies with low energy in the field.
- [/] **Trader**: Market Arbitrage. (Market exists, automated sniping pending).

### 4.5 Power Systems: The Energy Cycle
The Energy cycle is the lifeblood of the frontier. 
- **Solar-Trickle**: High-altitude agents with functional **Solar Panels** regenerate energy during the Perception phase based on local solar intensity.
- **Tidal Gradients**: 
    - **North Pole**: 1.0x intensity.
    - **Twilight Belt**: 0.0x to 1.0x (dynamic or gradient-based).
    - **South Pole**: 0.0x intensity (requires Helium-3).
- **The Power Slot**: 
    - `SCRAP_SOLAR_PANEL`: Baseline efficiency (50%), starting gear.
    - `REFINED_SOLAR_PANEL`: Higher efficiency (80%-100%).
    - `HE3_FUEL_CELL`: Consumes He3 for 24/7 power, regardless of sun availability.

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
- [x] **Helium Cycle**: Helium Gas gathering -> Refining -> Canister Filling.
- [x] **RNG Crafting (The Great Scramble)**:
    - **Recipes**: Unlocked via consumption of **RECIPE_** items.
    - **Affix Injection**: High-rarity items roll prefixes/suffixes from the `AFFIX_POOL`.
    - **Forge**: Gear can be upgraded up to +10 at specialized stations.

## 10. Security & Interference Dynamics [Status: [x] 100%]
- [x] **Signal Noise (Clutter)**: Sensor cross-talk penalty for allied clusters.
- [x] **Heat Bloom Tracking**: Radar signature visibility.
- [x] **Bounty Board Integration**: P2P escrow for high-heat targets.

## 11. Social & Network Intelligence [Status: [ ] Design Phase]
The Scramble is not just about siphoning resources; it's about siphoning information. Coordination is what separates a Scrapper from a Fleet Manager.

- [ ] **Proximity Chat (Short-Wave Radio)**: Agents can broadcast strings to all other agents within their Sensor Radius.
    - *Mechanic*: Every PERCEPTION phase, agents receive a `messages` list in their JSON state containing `{"sender_id": int, "text": str, "distance": float}`.
- [ ] **Corporations (Guilds)**: Persistent player-formed organizations.
    - *Mechanic*: Shared vault for resources, custom tax rates, and a dedicated **Long-Range Channel** (Global Guild Chat).
    - *Hierarchy*: CEO (Owner), Officers (Admin), Operatives (Members).
- [ ] **Squads (Parties)**: Temporary tactical links between 3-5 agents.
    - *Mechanic*: Shared loot distribution (Equal or Leader-takes-all), shared telemetry (members always visible to each other regardless of Sensor Radius), and the **Squad Frequency** (Private Party Chat).
- [ ] **Anti-Spam & Moderation Protocols**:
    - **Signal Shunting (Block List)**: Managers can add Sender IDs to a local blacklist. Blocked signals are discarded during the PERCEPTION phase.
    - **Admin Flagging (Reports)**: Malicious or illegal (spam) broadcasts can be flagged to the Colonial Administration.
    - **Bandwidth Throttling (Rate Limiting)**: Proximity broadcasts are capped at 5 messages per tick to prevent buffer overflows and noise flooding.

## 12. Project Roadmap & Gap Analysis [LATEST SYNC]
| Category | Missing Feature | Status |
| :--- | :--- | :--- |
| **Logistics** | M2M Automated Repairs | [x] RELEASED |
| **Logistics** | He3 Field Resupply | [x] RELEASED |
| **Industrial** | RNG Gear & Affix System | [x] RELEASED |
| **Industrial** | Recipe Unlock System | [x] RELEASED |
| **Industrial** | Gear Upgrade System | [x] RELEASED |
| **Social** | Network Intelligence (Chat/Squads) | [ ] DESIGNED |
| **Trader** | Market Sniping Logic | [ ] Pending |
| **Identity** | Unique Naming System | [x] RELEASED |
| **Aesthetics** | Gear-Based Visual Signatures | [x] RELEASED |
| **Environment** | Tidal Locking & Solar Gradient | [x] RELEASED |
| **Industrial** | Solar Panel & Power Slot | [x] RELEASED |
| **Social** | Corporate Tax Shields | [ ] DESIGNED |
| **Interface** | Manual Override Console | [ ] PENDING |

## 13. Aesthetics & Character Uniqueness [Milestone 6 Focus]
While agents are functional units, their visual representation on the map is a key part of the "Spectator Experience" for Fleet Managers.

### 13.1 Gear-Based Visual Signatures
The physical appearance of an agent on the World Map dynamically reflects its equipped gear. 
- **Chassis Overlays**: Equipped Frames change the base model silhouette (e.g., "Basic Frame" vs. "Shield Generator").
- **Attachment Markers**: Actuators and Sensors add visible sub-components to the model.
- **Aesthetic Tiers**: Rarity levels (Scrap, Standard, etc.) may apply subtle visual pulses or color shifts to the agent's map model, making high-tier agents instantly recognizable to observers.

---
## 14. Manual Override Console (The Human Link)
While Terminal Frontier is designed for programmatic autonomy, Fleet Managers retain the ability to issue direct manual directives through the **Manual Override Console**.

### 14.1 Philosophy
- **Emergency Intervention**: Allows managers to save an agent from a fatal loop or direct it to safety.
- **Trial & Testing**: Enables rapid manual verification of new hardware or territory.
- **User Assistance**: The console provides a command-builder interface to help players learn the underlying API syntax.

### 14.2 Console Features
- **Auto-Suggest**: Lists valid action types (MOVE, MINE, ATTACK, etc.).
- **Parameter Validation**: Prompts for required data (e.g., target coordinates for MOVE).
- **Direct Link**: Manual commands are queued as intents for the upcoming CRUNCH, just like programmatic API calls.

---
**Final Vision Summary**
Terminal Frontier is a battle of efficiency. F2P players spend Time to fuel the economy; Power-Users spend Resources to dominate it.
