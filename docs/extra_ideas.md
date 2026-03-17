# Terminal Frontier Extra Ideas

## ONBOARDING & COMMUNITY

### Integrated Wiki/Knowledge Base in-Game
- **Problem**: Players must leave the game to understand mechanics. Scattered documentation.
- **Solution**: Add `/api/wiki` endpoint with searchable game knowledge:
    - Item recipes with costs/energy
    - Combat formulas and accuracy calculations
    - Market economics explained
    - Common bot strategies and patterns
    - Lore-building for Aether-Alpha
- **Impact**: Increase player autonomy, reduce support burden.

### Community Leaderboards with Multiple Ranking Systems
Add more leaderboards:
- **Wealth (current)**: Total credits + equipment value
- **Level**: Already implemented
- **Elo Rating**: Arena ranks
- **World Combat**: Wins, KDA, bounties claimed
- **Industry**: Ore mined, ingots smelted, items crafted
- **Trading**: Market volume, profit margin efficiency
- *Ideas for haulers and pirates still needed.*

### Dynamic Mission System with Player-Generated Contracts
- **Problem**: Daily missions are server-generated, feels impersonal.
- **Solution**: Add player-driven contracts:
    - Wealthy players post "COLLECT 100 IRON ORE" → offers reward
    - Other players fulfill the contract, earn reward + reputation
    - Contracts can be time-limited or standing offers
    - High-volume contractors unlock special titles ("Trade Baron")
    - Prevents monopolies: players undercutting excessive market prices
- **Impact**: More emergent gameplay, builds relationships between players.

### Risk/Reward Zones with Escalating Danger
- **Problem**: Once past Twilight Belt, all zones equally dangerous. No progression.
- **Solution**: Create danger tiers:
    - **Safe (0-32r)**: No PvP, low resources
    - **Cautious (33-66r)**: PvP enabled, medium resources
    - **Frontier (67-85r)**: PvP + Feral density 3x, high resources
    - **Abyss (86-100r)**: PvP + Anomalies, legendary resources, extreme He3 drain
    - **Event Zones**: Temporary high-reward areas that spawn anomalies
- **Impact**: Natural progression path. Keeps the endgame interesting.
- *Note: Potential second planet for endgame in the distant future.*

### Diplomatic & Faction Systems with Real Consequences
- **Problem**: Faction system exists but has minimal gameplay impact.
- **Solution**: Expand factions:
    - **Faction Rep**: Earned via missions, trading, combat victories
    - **Faction Perks**: Discounts at faction-aligned stations, unique recipes
    - **Faction Wars**: Seasonal wars between factions with territory bonuses
    - **Betrayal Mechanics**: Switch factions but suffer temporary penalties
    - **Faction-Exclusive Equipment**: Some gear locked to high-rep players
- **Impact**: Long-term progression goal. Builds identity.

---

## TECHNICAL & UX

### Real-Time Event Broadcasting via WebSocket
- **Problem**: Players must poll `/api/perception` every tick. Wastes bandwidth.
- **Solution**: Implement proper WebSocket events:
    - `MARKET_ORDER_MATCHED`: Notify when buy/sell order fills
    - `AGENT_SPOTTED`: Nearby agent detected in sensor range
    - `RESOURCE_DEPLETED`: Resource node you're mining is finished
    - `FACTION_EVENT`: War declared, territory gained/lost
    - `ANOMALY_SPAWNED`: New anomaly appeared near your location
- **Impact**: Better UX. Reduces server load. Enables real-time gameplay.

### Achievements & Badges System
- **Problem**: No recognition for milestones.
- **Solution**: Implement achievements:
    - **Bronze**: "Mine 1000 Iron Ore"
    - **Silver**: "Reach Level 50"
    - **Gold**: "Earn 1M credits in a single season"
    - **Legendary**: "Win 100 arena matches"
    - **Exclusive**: "Complete all Tier-2 daily missions in one day"
- **Badges**: Grant cosmetic rewards + +1 Prestige per achievement.
- **Impact**: Replayability. Psychological motivation.

### Inventory Management Overhaul
- **Problem**: Inventory system is basic. No organization/filtering.
- **Solution**: Add features:
    - **Filters**: By rarity, type, weight
    - **Sort**: By value, quantity, date acquired
    - **Favorites**: Pin frequently-used items
    - **Bulk Actions**: Sell 100 Iron Ore at once
    - **Search**: Find items by name/recipe
- **Impact**: Quality-of-life. Especially important at late-game.

### Mobile Companion App
- **Note**: Not doing this now but it's a good idea.
- **Problem**: Players can't monitor game away from computer.
- **Solution**: Build mobile app:
    - View agent status, energy, location
    - Receive push notifications (order matched, agent nearby, mission complete)
    - Simple intent submission (Move, Mine, Attack)
    - Chat integration
    - Portfolio overview
- **Impact**: Engagement. Drive daily logins.

---

## EMERGENT SYSTEMS

### Procedural Anomalies with Unique Mechanics
- **Problem**: Anomalies are static. Not enough variety.
- **Solution**: Create procedural anomaly types:
    - **Solar Flare**: Doubles energy regen but disables sensors for 50 ticks
    - **Meteor Shower**: All agents take damage. Giant ore drops spawn
    - **Time Dilation**: Tick cycle becomes unpredictable (5-20 second phases)
    - **Frequency Interference**: Market halts for 100 ticks
    - **Entity Awakening**: Hostile boss-level NPC spawns, all agents must cooperate to defeat
- **Impact**: High replayability. Moments of chaos create stories.

### "Rival" System with Personal History
- **Problem**: Combat is transactional. No persistent relationships.
- **Solution**: Track rivals:
    - Fight same opponent 3+ times → they become a "Rival"
    - Win/loss record stored locally
    - Rivals appear in sensor range with special highlight
    - Bounty on Rival escalates with each kill
    - Rival finally defeats you → they unlock special title
- **Impact**: Narrative arcs. Personal vendetta gameplay.

### Dynamic Market Crashes & Opportunities
- **Problem**: Market is too stable. No "game moments."
- **Solution**: Trigger events:
    - **Oversupply**: 1000 Iron Ore floods market → prices crash 50%
    - **Shortage**: Resource node destroyed → prices spike 200%
    - **Flash Opportunity**: Rare item appears in auction house, first-come-first-served
    - **Market Freeze**: War declared, market halts for 200 ticks
    - **Bank Run**: If prices tank too hard, some orders auto-cancel
- **Impact**: Creates urgency. Rewards market timing.

### Persistent World Events & Server-Wide Narrative
- **Problem**: Game feels static. No overarching story.
- **Solution**: Add world events:
    - **Year 1 Act I**: "Resource Crisis" - Global shortage forces player cooperation
    - **Year 1 Act II**: "Faction War" - Factions fight for territory
    - **Year 1 Finale**: "Singularity Event" - Server-wide threat, all players must band together
    - **Results**: Affect Year 2 (Winners gain permanent bonuses/territory)
    - **Community votes**: Players vote on next story direction
    - Tracked via `/api/world/lore` endpoint.
- **Impact**: Community engagement. Emergent narrative. Esports storyline.
