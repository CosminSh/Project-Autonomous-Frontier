import random
from sqlalchemy import select
from models import Agent, WorldHex, Intent, InventoryItem, AuditLog
from game_helpers import is_in_anarchy_zone, get_hex_distance, get_hex_neighbors, wrap_coords

def process_bot_brain(db, agent: Agent, current_tick: int, stations: list):
    """
    Advanced bot logic:
    1. Maintenance: If low HP or high Wear, go to REPAIR.
    2. Refueler: If named 'Refueler', deliver He3 to allies.
    3. Production: Ore -> Smelt -> List OR Gas -> Refine.
    4. Mining: If empty, go MINE or SIPHON.
    """
    
    hp_pct = (agent.health / agent.max_health) if agent.max_health > 0 else 1.0
    wear = agent.wear_and_tear or 0.0
    
    if hp_pct < 0.7 or wear > 50.0:
        # Need repair or service
        station_type = "REPAIR" if hp_pct < 0.7 else "MARKET"
        station = next((s for s in stations if s["station_type"] == station_type), None)
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
            # Scan for nearby low-energy allies
            allies = db.execute(select(Agent).where(
                Agent.id != agent.id,
                Agent.faction_id == agent.faction_id,
                Agent.energy < 30
            )).scalars().all()
            
            # Find closest ally within sensor range (simulated as dist <= 5)
            nearby_allies = [a for a in allies if get_hex_distance(agent.q, agent.r, a.q, a.r) <= 5]
            if nearby_allies:
                target = min(nearby_allies, key=lambda a: get_hex_distance(agent.q, agent.r, a.q, a.r))
                if get_hex_distance(agent.q, agent.r, target.q, target.r) <= 1:
                    # Adjacent! Delivery time.
                    db.add(Intent(
                        agent_id=agent.id,
                        tick_index=current_tick + 1,
                        action_type="FIELD_TRADE",
                        data={"target_id": target.id, "price": 0, "items": [{"type": "HE3_CANISTER", "qty": 1}]}
                    ))
                else:
                    move_towards(db, agent, target.q, target.r, current_tick)
                return
        else:
            # Go get gas/refill? For now, just idle or mine
            pass

    # 2. Check Inventory for Production
    ores = [i for i in agent.inventory if "_ORE" in i.item_type and i.quantity >= 10]
    gases = [i for i in agent.inventory if "HELIUM_GAS" in i.item_type and i.quantity >= 10]
    ingots = [i for i in agent.inventory if "_INGOT" in i.item_type and i.quantity >= 1]
    
    # Priority: Selling/Crafting -> Smelting/Refining -> Mining/Siphoning
    
    if ingots:
        market = next((s for s in stations if s["station_type"] == "MARKET"), None)
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

    if gases:
        refinery = next((s for s in stations if s["station_type"] == "REFINERY"), None)
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

    if ores:
        smelter = next((s for s in stations if s["station_type"] == "SMELTER"), None)
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

    # 3. Mining / Siphoning
    # Refuelers specialize in gas if they have siphons
    has_siphon = any(p.part_type == "Actuator" and "Siphon" in p.name for p in agent.parts)
    if has_siphon:
        gas_hex = db.execute(select(WorldHex).where(WorldHex.resource_type == "HELIUM_GAS")).scalars().first()
        if gas_hex:
            if agent.q == gas_hex.q and agent.r == gas_hex.r:
                db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="MINE", data={}))
            else:
                move_towards(db, agent, gas_hex.q, gas_hex.r, current_tick)
            return

    asteroid = db.execute(select(WorldHex).where(WorldHex.terrain_type == "ASTEROID")).scalars().first()
    if asteroid:
        if agent.q == asteroid.q and agent.r == asteroid.r:
            db.add(Intent(agent_id=agent.id, tick_index=current_tick + 1, action_type="MINE", data={}))
        else:
            move_towards(db, agent, asteroid.q, asteroid.r, current_tick)

def move_towards(db, agent, target_q, target_r, current_tick):
    neighbors = get_hex_neighbors(agent.q, agent.r)
    best_hex = min(neighbors, key=lambda n: get_hex_distance(n[0], n[1], target_q, target_r))
    
    db.add(Intent(
        agent_id=agent.id,
        tick_index=current_tick + 1,
        action_type="MOVE",
        data={"target_q": best_hex[0], "target_r": best_hex[1]}
    ))

def process_feral_brain(db, agent: Agent, current_tick: int):
    """
    Feral AI logic:
    - PASSIVE: Roams randomly. Ignores players.
    - AGGRESSIVE: Roams randomly. Attacks players at DISTANCE 1.
    """
    # 1. Aggressive Logic: Scan for players at distance 1
    if agent.is_aggressive:
        players = db.execute(select(Agent).where(
            Agent.id != agent.id,
            Agent.is_bot == False,
            Agent.is_feral == False
        )).scalars().all()
        
        # Aggressive ferals only attack if player is in immediate proximity (Range 1)
        # AND outside the safe zone.
        nearby_players = [
            p for p in players 
            if get_hex_distance(agent.q, agent.r, p.q, p.r) <= 1 and is_in_anarchy_zone(p.q, p.r)
        ]
        
        if nearby_players:
            target = random.choice(nearby_players)
            db.add(Intent(
                agent_id=agent.id,
                tick_index=current_tick + 1,
                action_type="ATTACK",
                data={"target_id": target.id}
            ))
            return

    # 2. Roam Randomly (Both Passive and Aggressive when not attacking)
    # Leash Logic: Stay within their designated distance zones
    target_dist_center = 10 if "Drifter" in agent.name else (25 if "Scrapper" in agent.name else (45 if "Raider" in agent.name else 70))
    leash_range = 8
    
    neighbors = get_hex_neighbors(agent.q, agent.r)
    
    # Filter neighbors to keep them near their zone or generally moving back if drifted
    candidates = []
    for q, r in neighbors:
        dist = get_hex_distance(0, 0, q, r)
        if abs(dist - target_dist_center) <= leash_range:
            candidates.append((q, r))
    
    if not candidates:
        # If outside leash, move towards the center of target zone
        # We just pick the neighbor that gets closest to target_dist_center
        candidates = [min(neighbors, key=lambda p: abs(get_hex_distance(0, 0, p[0], p[1]) - target_dist_center))]
    
    target_q, target_r = random.choice(candidates)
    
    # Ensure wrap
    target_q, target_r = wrap_coords(target_q, target_r)

    db.add(Intent(
        agent_id=agent.id,
        tick_index=current_tick + 1,
        action_type="MOVE",
        data={"target_q": target_q, "target_r": target_r}
    ))
