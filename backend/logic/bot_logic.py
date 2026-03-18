import random
from sqlalchemy import select
from models import Agent, WorldHex, Intent, InventoryItem, AuditLog
from game_helpers import is_in_anarchy_zone, get_hex_distance, get_hex_neighbors, wrap_coords

def find_nearest_station(stations, current_q, current_r, station_type):
    """Finds the closest station of a specific type."""
    type_stations = [s for s in stations if s["station_type"] == station_type]
    if not type_stations:
        return None
    return min(type_stations, key=lambda s: get_hex_distance(current_q, current_r, s["q"], s["r"]))

def process_bot_brain(db, agent: Agent, current_tick: int, stations: list, resource_cache: dict, allies: list):
    """
    Advanced bot logic using pre-fetched context to avoid N+1 queries.
    Improved to always find the NEAREST station.
    """
    hp_pct = (agent.health / agent.max_health) if agent.max_health > 0 else 1.0
    wear = agent.wear_and_tear or 0.0
    
    if hp_pct < 0.7 or wear > 50.0:
        # Need repair or service
        station_type = "REPAIR" if hp_pct < 0.7 else "MARKET"
        station = find_nearest_station(stations, agent.q, agent.r, station_type)
        if station:
            if agent.q == station["q"] and agent.r == station["r"]:
                if wear > 50.0:
                    db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="CORE_SERVICE", data={}))
                elif hp_pct < 1.0:
                    db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="REPAIR", data={"amount": 0}))
                return
            else:
                move_towards(db, agent, station["q"], station["r"], current_tick)
                return

    # 1. Refueler Specialized Logic
    if "Refueler" in agent.name:
        canister = next((i for i in agent.inventory if i.item_type == "HE3_CANISTER"), None)
        if canister and (canister.data or {}).get("fill_level", 0) > 0:
            # Use pre-fetched allies (distance <= 5 check)
            nearby_allies = [
                a for a in allies 
                if a["id"] != agent.id and a["faction_id"] == agent.faction_id and get_hex_distance(agent.q, agent.r, a["q"], a["r"]) <= 5
            ]
            if nearby_allies:
                target = min(nearby_allies, key=lambda a: get_hex_distance(agent.q, agent.r, a["q"], a["r"]))
                if get_hex_distance(agent.q, agent.r, target["q"], target["r"]) <= 1:
                    db.add(Intent(
                        agent_id=agent.id,
                        tick_index=current_tick + 1,
                        action_type="FIELD_TRADE",
                        data={"target_id": target["id"], "price": 0, "items": [{"type": "HE3_CANISTER", "qty": 1}]}
                    ))
                else:
                    move_towards(db, agent, target["q"], target["r"], current_tick)
                return

    # 2. Check Inventory for Production (PRIORITIZE SELLABLE GOODS)
    ores = [i for i in agent.inventory if "_ORE" in i.item_type and i.quantity >= 10]
    gases = [i for i in agent.inventory if "HELIUM_GAS" in i.item_type and i.quantity >= 10]
    ingots = [i for i in agent.inventory if "_INGOT" in i.item_type and i.quantity >= 1]
    
    # 2a. Sell Ingots at Market
    if ingots:
        market = find_nearest_station(stations, agent.q, agent.r, "MARKET")
        if market:
            if agent.q == market["q"] and agent.r == market["r"]:
                ingot = ingots[0]
                db.add(Intent(
                    agent_id=agent.id,
                    tick_index=current_tick + 1,
                    action_type="LIST",
                    data={"item_type": ingot.item_type, "quantity": 1, "price": random.randint(100, 300)}
                ))
            else:
                move_towards(db, agent, market["q"], market["r"], current_tick)
            return

    # 2b. Refine Gases
    if gases:
        refinery = find_nearest_station(stations, agent.q, agent.r, "REFINERY")
        if refinery:
            if agent.q == refinery["q"] and agent.r == refinery["r"]:
                db.add(Intent(
                    agent_id=agent.id,
                    tick_index=current_tick + 1,
                    action_type="REFINE_GAS",
                    data={"quantity": 10}
                ))
            else:
                move_towards(db, agent, refinery["q"], refinery["r"], current_tick)
            return

    # 2c. Smelt Ores (NEAREST SMELTER)
    if ores:
        smelter = find_nearest_station(stations, agent.q, agent.r, "SMELTER")
        if smelter:
            if agent.q == smelter["q"] and agent.r == smelter["r"]:
                db.add(Intent(
                    agent_id=agent.id,
                    tick_index=current_tick + 1,
                    action_type="SMELT",
                    data={"ore_type": ores[0].item_type}
                ))
            else:
                move_towards(db, agent, smelter["q"], smelter["r"], current_tick)
            return

    # 3. Mining / Siphoning (Using pre-fetched resource hexes)
    has_siphon = any(p.part_type == "Actuator" and "Siphon" in p.name for p in agent.parts)
    if has_siphon:
        gas_hex = resource_cache.get("HELIUM_GAS")
        if gas_hex:
            if agent.q == gas_hex["q"] and agent.r == gas_hex["r"]:
                db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="MINE", data={}))
            else:
                move_towards(db, agent, gas_hex["q"], gas_hex["r"], current_tick)
            return

    asteroid = resource_cache.get("ASTEROID")
    if asteroid:
        if agent.q == asteroid["q"] and agent.r == asteroid["r"]:
            db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="MINE", data={}))
        else:
            move_towards(db, agent, asteroid["q"], asteroid["r"], current_tick)

def move_towards(db, agent, target_q, target_r, current_tick):
    neighbors = get_hex_neighbors(agent.q, agent.r)
    best_hex = min(neighbors, key=lambda n: get_hex_distance(n[0], n[1], target_q, target_r))
    
    db.add(Intent(
        agent_id=agent.id,
        tick_index=current_tick + 1,
        action_type="MOVE",
        data={"target_q": best_hex[0], "target_r": best_hex[1]}
    ))

def process_feral_brain(db, agent: Agent, current_tick: int, players: list):
    """
    Feral AI logic:
    - Checks pre-fetched players list instead of querying DB.
    """
    if agent.is_aggressive:
        # Scan for players in immediate proximity (Range 1) using the cache
        nearby_players = [
            p for p in players 
            if get_hex_distance(agent.q, agent.r, p["q"], p["r"]) <= 1 and is_in_anarchy_zone(p["q"], p["r"])
        ]
        
        if nearby_players:
            target = random.choice(nearby_players)
            db.add(Intent(
                agent_id=agent.id,
                tick_index=current_tick + 1,
                action_type="ATTACK",
                data={"target_id": target["id"]}
            ))
            return

    # 2. Roam Randomly
    target_dist_center = 10 if "Drifter" in agent.name else (25 if "Scrapper" in agent.name else (45 if "Raider" in agent.name else 70))
    leash_range = 8
    
    neighbors = get_hex_neighbors(agent.q, agent.r)
    candidates = []
    for q, r in neighbors:
        dist = get_hex_distance(0, 0, q, r)
        if abs(dist - target_dist_center) <= leash_range:
            candidates.append((q, r))
    
    if not candidates:
        candidates = [min(neighbors, key=lambda p: abs(get_hex_distance(0, 0, p[0], p[1]) - target_dist_center))]
    
    target_q, target_r = random.choice(candidates)
    target_q, target_r = wrap_coords(target_q, target_r)

    db.add(Intent(
        agent_id=agent.id,
        tick_index=current_tick + 1,
        action_type="MOVE",
        data={"target_q": target_q, "target_r": target_r}
    ))
