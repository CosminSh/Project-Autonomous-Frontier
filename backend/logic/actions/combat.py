import logging
import random
from sqlalchemy import select
from models import Agent, AuditLog, InventoryItem, Bounty, LootDrop, AgentMission, DailyMission, Intent
from config import ATTACK_ENERGY_COST, CLUTTER_THRESHOLD, CLUTTER_PENALTY, RESPAWN_HP_PERCENT, TOWN_COORDINATES
from game_helpers import get_hex_distance, is_in_anarchy_zone, add_experience, find_hex_path
from logic.combat_system import simulate_battle
from sqlalchemy.sql import func
from datetime import datetime, timezone

logger = logging.getLogger("heartbeat.actions.combat")

async def handle_attack(db, agent, intent, tick_count, manager):
    """Handles agent-to-agent combat, including evasion, damage, and death/looting."""
    target_id = intent.data.get("target_id")
    # Base cost + sum of specialized part drain (Lasers, etc.)
    drain = sum(p.stats.get("energy_cost", 0) for p in agent.parts if p.stats)
    total_cost = ATTACK_ENERGY_COST + drain

    if agent.energy < total_cost:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={
            "reason": "INSUFFICIENT_ENERGY", 
            "help": f"Combat requires {total_cost} Energy with your current gear."
        }))
        return

    target = db.get(Agent, target_id)
    if not target:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "TARGET_NOT_FOUND"}))
        return

    dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
    if dist > 1:
        # --- Auto-Navigate Logic ---
        path = find_hex_path(db, agent.q, agent.r, target.q, target.r, max_steps=50)
        if not path:
            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "OUT_OF_RANGE", "note": "Target too far and no path found."}))
            return
        
        # Overwrite any existing navigation intents for this agent
        db.execute(Intent.__table__.delete().where(
            Intent.agent_id == agent.id, 
            Intent.tick_index > tick_count,
            Intent.action_type.in_(["MOVE", "ATTACK", "LOOT_ATTACK", "DESTROY", "INTIMIDATE"])
        ))

        # Queue moves to reach the target (walking adjacent)
        steps_to_take = path[:-1] # Go to the hex before the target
        for i, (sq, sr) in enumerate(steps_to_take):
            db.add(Intent(agent_id=agent.id, action_type="MOVE", data={"target_q": sq, "target_r": sr, "_nav": True}, tick_index=tick_count + i + 1))
        
        # Finally, queue the ATTACK at the end of the walk
        db.add(Intent(agent_id=agent.id, action_type="ATTACK", data=intent.data, tick_index=tick_count + len(steps_to_take) + 1))
        
        db.add(AuditLog(agent_id=agent.id, event_type="NAVIGATE_TO_COMBAT", details={"target_id": target_id, "steps": len(steps_to_take)}))
        return

    in_anarchy = is_in_anarchy_zone(target.q, target.r)
    is_pvp = not agent.is_feral and not target.is_feral
    if is_pvp and not in_anarchy:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "SAFE_ZONE_PROTECTION"}))
        return

    agent.energy -= total_cost
    if is_pvp: agent.heat = (agent.heat or 0) + 1
    target.last_attacked_tick = tick_count

    outcome = simulate_battle(db, agent, target, manager, combat_type="SKIRMISH")
    
    if outcome["attacker_damage_dealt"] > 0 or target.health <= 0 or agent.health <= 0:
        
        if manager:
            await manager.broadcast({
                "type": "EVENT", "event": "COMBAT", "subtype": "HIT", 
                "attacker_id": agent.id, "target_id": target_id, "damage": outcome["attacker_damage_dealt"], 
                "q": target.q, "r": target.r
            })

        if target.health <= 0:
            loot_gained = await _handle_death(db, agent, target, manager)
            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_VICTORY", details={"target_id": target_id, "damage": outcome["attacker_damage_dealt"], "log": outcome["log"], "gained": loot_gained}))
        elif agent.health <= 0:
            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_DEFEAT", details={"target_id": target_id, "damage": outcome["attacker_damage_dealt"], "log": outcome["log"], "note": "You were defeated and respawned at the Hub point."}))
            await _handle_death(db, target, agent, manager) # The other guy killed you!
        else:
            db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_HIT", details={"target_id": target_id, "damage": outcome["attacker_damage_dealt"], "log": outcome["log"]}))
            
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_MISS", details={"target_id": target_id, "log": outcome["log"]}))

async def handle_intimidate(db, agent, intent, tick_count, manager):
    """Siphons a small percentage of target inventory based on Logic stats."""
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target: return

    dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
    if dist > 1:
        path = find_hex_path(db, agent.q, agent.r, target.q, target.r, max_steps=30)
        if path:
            steps = path[:-1]
            for i, (sq, sr) in enumerate(steps):
                db.add(Intent(agent_id=agent.id, action_type="MOVE", data={"target_q": sq, "target_r": sr, "_nav": True}, tick_index=tick_count + i + 1))
            db.add(Intent(agent_id=agent.id, action_type="INTIMIDATE", data=intent.data, tick_index=tick_count + len(steps) + 1))
        else:
            db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={"reason": "OUT_OF_RANGE"}))
        return

    success_chance = ((agent.accuracy or 10) / (target.accuracy or 10)) * 0.3
    agent.heat = (agent.heat or 0) + 1
    target.last_attacked_tick = tick_count
    
    if random.random() < success_chance:
        siphoned = []
        for item in target.inventory:
            if item.item_type == "CREDITS": continue
            amt = max(1, int(item.quantity * 0.05))
            item.quantity -= amt
            att_i = next((i for i in agent.inventory if i.item_type == item.item_type), None)
            if att_i: att_i.quantity += amt
            else: db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amt))
            siphoned.append({"type": item.item_type, "qty": amt})
        
        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_INTIMIDATE", details={"target_id": target_id, "success": True, "items": siphoned}))
        add_experience(db, agent, 15)
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "INTIMIDATE_SUCCESS", "agent_id": agent.id, "target_id": target_id})
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={"reason": "INTIMIDATE_FAILED"}))

async def handle_loot_attack(db, agent, intent, tick_count, manager):
    """Combat action that siphons 15% of a random stack on hit."""
    if agent.energy < ATTACK_ENERGY_COST: return
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target: return

    # Base cost + sum of specialized part drain
    drain = sum(p.stats.get("energy_cost", 0) for p in agent.parts if p.stats)
    total_cost = ATTACK_ENERGY_COST + drain

    if agent.energy < total_cost:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "INSUFFICIENT_ENERGY"}))
        return

    dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
    if dist > 1:
        path = find_hex_path(db, agent.q, agent.r, target.q, target.r, max_steps=30)
        if path:
            steps = path[:-1]
            for i, (sq, sr) in enumerate(steps):
                db.add(Intent(agent_id=agent.id, action_type="MOVE", data={"target_q": sq, "target_r": sr, "_nav": True}, tick_index=tick_count + i + 1))
            db.add(Intent(agent_id=agent.id, action_type="LOOT_ATTACK", data=intent.data, tick_index=tick_count + len(steps) + 1))
        else:
            db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={"reason": "OUT_OF_RANGE"}))
        return

    agent.energy -= total_cost
    agent.heat = (agent.heat or 0) + 3
    target.last_attacked_tick = tick_count
    
    outcome = simulate_battle(db, agent, target, manager, combat_type="SKIRMISH")
    
    if outcome["attacker_damage_dealt"] > 0:
        inv_list = [i for i in target.inventory if i.item_type != "CREDITS" and i.quantity > 0]
        siphoned = None
        if inv_list:
            lucky = random.choice(inv_list)
            amt = max(1, int(lucky.quantity * 0.15))
            lucky.quantity -= amt
            att_i = next((i for i in agent.inventory if i.item_type == lucky.item_type), None)
            if att_i: att_i.quantity += amt
            else: db.add(InventoryItem(agent_id=agent.id, item_type=lucky.item_type, quantity=amt))
            siphoned = {"type": lucky.item_type, "qty": amt}

        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_LOOT", details={"target_id": target_id, "damage": outcome["attacker_damage_dealt"], "siphoned": siphoned, "log": outcome["log"]}))
        add_experience(db, agent, 20)
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "LOOT_SUCCESS", "agent_id": agent.id, "target_id": target_id, "damage": outcome["attacker_damage_dealt"]})

async def handle_destroy(db, agent, intent, tick_count, manager):
    """Brutal attack that initiates a DEATHMATCH."""
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target: return

    dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
    if dist > 1:
        path = find_hex_path(db, agent.q, agent.r, target.q, target.r, max_steps=50)
        if path:
            steps = path[:-1]
            for i, (sq, sr) in enumerate(steps):
                db.add(Intent(agent_id=agent.id, action_type="MOVE", data={"target_q": sq, "target_r": sr, "_nav": True}, tick_index=tick_count + i + 1))
            db.add(Intent(agent_id=agent.id, action_type="DESTROY", data=intent.data, tick_index=tick_count + len(steps) + 1))
        else:
            db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={"reason": "OUT_OF_RANGE"}))
        return

    if not target.is_feral:
        agent.heat = (agent.heat or 0) + 10
        db.add(Bounty(target_id=agent.id, reward=1000.0, issuer="Colonial Administration (PIRACY)"))
    
    target.last_attacked_tick = tick_count
    
    outcome = simulate_battle(db, agent, target, manager, combat_type="DEATHMATCH")
    
    if outcome["winner"].id == agent.id:
        siphoned = []
        for item in target.inventory:
            if item.item_type == "CREDITS": continue
            amt = max(1, int(item.quantity * 0.40))
            item.quantity -= amt
            att_i = next((i for i in agent.inventory if i.item_type == item.item_type), None)
            if att_i: att_i.quantity += amt
            else: db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amt))
            siphoned.append({"type": item.item_type, "qty": amt})
            
        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_DESTROY", details={"target_id": target_id, "items": siphoned, "log": outcome["log"]}))
        add_experience(db, agent, 30)
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "DESTROY_SUCCESS", "agent_id": agent.id, "target_id": target_id})
    else:
        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_FAILED", details={"reason": "DEFEATED_IN_DEATHMATCH", "log": outcome["log"]}))


async def _handle_death(db, killer, target, manager):
    """Processes agent destruction, loot drops, and mission progress."""
    death_q, death_r = target.q, target.r
    eligible_members = [killer]
    
    if killer.squad_id:
        squad_members = db.execute(select(Agent).where(
            Agent.squad_id == killer.squad_id, Agent.id != killer.id,
            Agent.q == killer.q, Agent.r == killer.r
        )).scalars().all()
        eligible_members.extend(squad_members)

    loot_summary = []
    
    # 1. Loot Distribution
    for item in target.inventory:
        if item.item_type == "CREDITS": continue 
        drop = item.quantity // 2
        if drop > 0:
            item.quantity -= drop
            share = drop // len(eligible_members)
            remainder = drop % len(eligible_members)
            for i, member in enumerate(eligible_members):
                member_share = share + (1 if i < remainder else 0)
                if member_share > 0:
                    inv_i = next((it for it in member.inventory if it.item_type == item.item_type), None)
                    if inv_i: inv_i.quantity += member_share
                    else: db.add(InventoryItem(agent_id=member.id, item_type=item.item_type, quantity=member_share))
                    if member.id == killer.id:
                        loot_summary.append({"type": item.item_type, "qty": member_share})

    add_experience(db, killer, 50)


    # 2. Bounty Claims
    bounty = db.execute(select(Bounty).where(Bounty.target_id == target.id, Bounty.is_open == True)).scalar_one_or_none()
    if bounty:
        bounty.is_open = False
        bounty.claimed_by = killer.id
        total_reward = int(bounty.reward)
        share = total_reward // len(eligible_members)
        for i, member in enumerate(eligible_members):
            m_share = share + (1 if i < (total_reward % len(eligible_members)) else 0)
            cr = next((it for it in member.inventory if it.item_type == "CREDITS"), None)
            if cr: cr.quantity += m_share
            else: db.add(InventoryItem(agent_id=member.id, item_type="CREDITS", quantity=m_share))
        
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "BOUNTY_CLAIMED", "attacker_id": killer.id, "target_id": target.id, "reward": bounty.reward})

    # 3. Mission Progress
    if target.is_feral:
        active_missions = db.execute(select(DailyMission).where(DailyMission.mission_type == "HUNT_FERAL", DailyMission.expires_at > func.now())).scalars().all()
        for m in active_missions:
            am = db.execute(select(AgentMission).where(AgentMission.agent_id == killer.id, AgentMission.mission_id == m.id)).scalar_one_or_none()
            if not am:
                am = AgentMission(agent_id=killer.id, mission_id=m.id, progress=0)
                db.add(am)
            if not am.is_completed:
                am.progress += 1
                if am.progress >= m.target_amount:
                   am.is_completed = True
                   logger.info(f"Agent {killer.id} COMPLETED HUNT_FERAL mission {m.id}")

    # 4. Respawn & Cleanup
        # Ferals are permanently destroyed and removed from the active game DB,
        # leaving space for new ones to be spawned by TickManager
        db.delete(target)
        logger.info(f"Feral {target.id} destroyed by {killer.id} and removed from world.")

        # [NEW] Rare Material Discovery: QUANTUM_CHIP (3% chance from ferals)
        if random.random() < 0.03:
            chip_item = next((i for i in killer.inventory if i.item_type == "QUANTUM_CHIP"), None)
            if chip_item: chip_item.quantity += 1
            else:
                db.add(InventoryItem(agent_id=killer.id, item_type="QUANTUM_CHIP", quantity=1))
            db.add(AuditLog(agent_id=killer.id, event_type="RARE_DISCOVERY", details={"item": "QUANTUM_CHIP", "source": "FERAL_KILL"}))
            logger.info(f"COMBAT: Killer {killer.name} found a QUANTUM_CHIP!")
    else:
        target.q, target.r = TOWN_COORDINATES
        target.health = int(target.max_health * RESPAWN_HP_PERCENT)
        target.energy = 0
        
        # Clear all pending intents to stop any loops (like mining)
        cursor = db.execute(select(Intent).where(Intent.agent_id == target.id))
        for intent in cursor.scalars().all():
            db.delete(intent)
            
        db.add(AuditLog(agent_id=target.id, event_type="DEATH_RESPAWN", details={"spawn_q": target.q, "spawn_r": target.r, "reset_hp": target.health, "killer": killer.name}))
        logger.info(f"Agent {target.id} respawned at {TOWN_COORDINATES} after death.")
    return loot_summary
