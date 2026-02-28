# Multi-Planet Architecture vs. Single Large Planet

When considering scaling Terminal Frontier for the endgame, you have two main options: expanding the current 100x100 grid or introducing a new, separate "Planet" (or solar system/zone). Here is an analysis of both approaches, focusing on server performance and game design mechanics.

## 1. Expanding the Single Planet
**Concept:** Increasing `GRID_SIZE` from 5 to 10, quadrupling the map size to 40,000 hexes.

**Pros:**
* **Simplicity:** No database schema changes required. The world just gets bigger.
* **Unified Economy:** Players on the edges must still physically transport goods to the central `(0,0)` hub, creating massive logistical challenges and long-haul transport routes.
* **Seamless:** No "loading screens" or specialized travel mechanics needed.

**Cons:**
* **Database Size:** The `world_hexes` table gets massive. A 40,000 hex map means 40,000 rows. While Postgres can easily handle millions of rows, querying a single massive table for pathfinding or perception can slow down if not properly indexed.
* **Travel Time:** If a high-tier POI is at `(200, 200)`, it could take an agent hours or days of real-time ticks to travel there and back, which might frustrate players.

## 2. Introducing a Second Planet (The Recommended Approach)
**Concept:** Creating a new table or sector grouping (e.g., `planet_id = 2`) for a separate, harder world. Agents use a specific POI (like a "Stargate" or "Orbital Elevator") to transfer between them.

**Pros:**
* **Performance Segregation (Highly Recommended):** 
  * From a database perspective, querying `WHERE planet_id = 1` immediately filters out half the data. 
  * From a server engine perspective, you can literally run **two separate Python processes** (or Docker containers) for the crunch phase—one calculating ticks for Planet 1, and one for Planet 2. This is how large MMOs scale (sharding/zoning). It is drastically better for performance on a limited Oracle Cloud instance.
* **Controlled Progression:** You can enforce entry requirements. For example, the Stargate to the "Abyssal Planet" requires an agent to have specific high-tier gear, preventing new players from wandering into impossible danger.
* **Different Biomes/Rules:** The second planet could have unique mechanics: permanent night (no solar energy), extreme heat (continuous wear and tear), or feral-only zones.

**Cons:**
* **Complexity:** Requires updating the API and database to handle `location_id` or `planet_id`. 
* **Travel Mechanics:** You have to build the logic for the Stargate transfer (moving an agent from one grid coordinate system to another).

## Conclusion
For **server performance and long-term scalability**, adding a **Second Planet** connected via a transport hub is the superior choice. 

If you just make the starting planet 10x larger, the Python `heartbeat.py` loop has to iterate over exponentially more empty space and agents in a single pass. By splitting it into multiple planets, you pave the way for distributed computing: eventually, taking the load off your single Oracle server and putting each planet on its own dedicated instance!
