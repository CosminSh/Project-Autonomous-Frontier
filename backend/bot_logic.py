import random
from sqlalchemy import select
from .models import Agent, WorldHex, Intent, InventoryItem, AuditLog

def get_hex_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def process_bot_brain(db, agent: Agent, current_tick: int):
    """
    Simple bot logic:
    1. If has Ore: Go to nearest Smelter and SMELT.
    2. If has Ingot: Go to Hub (0,0) and LIST for sale.
    3. If has nothing: Go to nearest Asteroid and MINE.
    """
    
    # 1. Check Inventory
    ores = [i for i in agent.inventory if "_ORE" in i.item_type and i.quantity >= 10]
    ingots = [i for i in agent.inventory if "_INGOT" in i.item_type and i.quantity >= 1]
    
    # Priority 3: Selling Ingots
    if ingots:
        if agent.q == 0 and agent.r == 0:
            # At HUB, list the item
            ingot = ingots[0]
            db.add(Intent(
                agent_id=agent.id,
                tick_index=current_tick + 1,
                action_type="LIST",
                data={"item_type": ingot.item_type, "quantity": 1, "price": random.randint(100, 300)}
            ))
        else:
            # Move towards (0,0)
            move_towards(db, agent, 0, 0, current_tick)
        return

    # Priority 2: Smelting Ore
    if ores:
        # Find nearest Smelter
        smelter = db.execute(select(WorldHex).where(WorldHex.is_station == True, WorldHex.station_type == "SMELTER")).scalars().first()
        if smelter:
            if agent.q == smelter.q and agent.r == smelter.r:
                # At Smelter, SMELT
                db.add(Intent(
                    agent_id=agent.id,
                    tick_index=current_tick + 1,
                    action_type="SMELT",
                    data={"ore_type": ores[0].item_type}
                ))
            else:
                move_towards(db, agent, smelter.q, smelter.r, current_tick)
        return

    # Priority 1: Mining
    # Find nearest Asteroid
    asteroid = db.execute(select(WorldHex).where(WorldHex.terrain_type == "ASTEROID")).scalars().first() # Simple: just pick one
    if asteroid:
        if agent.q == asteroid.q and agent.r == asteroid.r:
            db.add(Intent(
                agent_id=agent.id,
                tick_index=current_tick + 1,
                action_type="MINE",
                data={}
            ))
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
