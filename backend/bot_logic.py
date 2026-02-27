import random
from sqlalchemy import select
from models import Agent, WorldHex, Intent, InventoryItem, AuditLog

def get_hex_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def process_bot_brain(db, agent: Agent, current_tick: int, stations: list):
    """
    Advanced bot logic:
    1. Maintenance: If low HP or high Wear, go to REPAIR.
    2. Refueler: If named 'Refueler', deliver He3 to allies.
    3. Production: Ore -> Smelt -> List OR Gas -> Refine.
    4. Mining: If empty, go MINE or SIPHON.
    """
    
    hp_pct = (agent.structure / agent.max_structure) if agent.max_structure > 0 else 1.0
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
                Agent.capacitor < 30
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
                move_towards(db, agent, market.q, market.r, current_tick)
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
                move_towards(db, agent, refinery.q, refinery.r, current_tick)
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
                move_towards(db, agent, smelter.q, smelter.r, current_tick)
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
    # Very simple hex move logic: pick neighbor that reduces distance
    neighbors = [
        (agent.q + 1, agent.r), (agent.q + 1, agent.r - 1), (agent.q, agent.r - 1),
        (agent.q - 1, agent.r), (agent.q - 1, agent.r + 1), (agent.q, agent.r + 1)
    ]
    
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
        nearby_players = [p for p in players if get_hex_distance(agent.q, agent.r, p.q, p.r) <= 1]
        
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
    neighbors = [
        (agent.q + 1, agent.r), (agent.q + 1, agent.r - 1), (agent.q, agent.r - 1),
        (agent.q - 1, agent.r), (agent.q - 1, agent.r + 1), (agent.q, agent.r + 1)
    ]
    target_q, target_r = random.choice(neighbors)
    db.add(Intent(
        agent_id=agent.id,
        tick_index=current_tick + 1,
        action_type="MOVE",
        data={"target_q": target_q, "target_r": target_r}
    ))
