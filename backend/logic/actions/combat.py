import logging
import random
from sqlalchemy import select
from models import Agent, AuditLog, InventoryItem, Bounty, LootDrop, AgentMission, DailyMission
from config import ATTACK_ENERGY_COST, CLUTTER_THRESHOLD, CLUTTER_PENALTY
from game_helpers import get_hex_distance, is_in_anarchy_zone, add_experience
from sqlalchemy.sql import func
from datetime import datetime, timezone

logger = logging.getLogger("heartbeat.actions.combat")

async def handle_attack(db, agent, intent, tick_count, manager):
    """Handles agent-to-agent combat, including evasion, damage, and death/looting."""
    target_id = intent.data.get("target_id")
    if agent.capacitor < ATTACK_ENERGY_COST:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "INSUFFICIENT_ENERGY"}))
        return

    target = db.get(Agent, target_id)
    if not target:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "TARGET_NOT_FOUND"}))
        return

    dist = get_hex_distance(agent.q, agent.r, target.q, target.r)
    if dist > 1:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "OUT_OF_RANGE"}))
        return

    in_anarchy = is_in_anarchy_zone(target.q, target.r)
    is_pvp = not agent.is_feral and not target.is_feral
    if is_pvp and not in_anarchy:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_FAILED", details={"reason": "SAFE_ZONE_PROTECTION"}))
        return

    # Hit Calculation
    attacker_dex = agent.logic_precision or 10
    attacker_roll = random.randint(1, 20) + attacker_dex
    evasion_target = 10 + ((target.logic_precision or 10) // 2)

    agent.capacitor -= ATTACK_ENERGY_COST
    if is_pvp: agent.heat = (agent.heat or 0) + 1

    if attacker_roll >= evasion_target:
        damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
        target.structure -= damage
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_HIT", details={"target_id": target_id, "damage": damage}))
        
        if manager:
            await manager.broadcast({
                "type": "EVENT", "event": "COMBAT", "subtype": "HIT", 
                "attacker_id": agent.id, "target_id": target_id, "damage": damage, 
                "q": target.q, "r": target.r
            })

        if target.structure <= 0:
            await _handle_death(db, agent, target, manager)

    else:
        db.add(AuditLog(agent_id=agent.id, event_type="COMBAT_MISS", details={"target_id": target_id}))

async def handle_intimidate(db, agent, intent, tick_count, manager):
    """Siphons a small percentage of target inventory based on Logic stats."""
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target or get_hex_distance(agent.q, agent.r, target.q, target.r) > 1:
        return

    success_chance = ((agent.logic_precision or 10) / (target.logic_precision or 10)) * 0.3
    agent.heat = (agent.heat or 0) + 1
    
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
    if agent.capacitor < ATTACK_ENERGY_COST: return
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target or get_hex_distance(agent.q, agent.r, target.q, target.r) > 1:
        return

    agent.capacitor -= ATTACK_ENERGY_COST
    agent.heat = (agent.heat or 0) + 3
    
    attacker_dex = agent.logic_precision or 10
    if random.randint(1, 20) + attacker_dex >= (10 + ((target.logic_precision or 10) // 2)):
        damage = max(1, (agent.kinetic_force or 10) - ((target.integrity or 5) // 2))
        target.structure -= damage
        
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

        db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_LOOT", details={"target_id": target_id, "damage": damage, "siphoned": siphoned}))
        add_experience(db, agent, 20)
        if manager:
            await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "LOOT_SUCCESS", "agent_id": agent.id, "target_id": target_id, "damage": damage})

async def handle_destroy(db, agent, intent, tick_count, manager):
    """Brutal attack that siphons 40% of all stacks and leaves target at 5% HP."""
    target_id = intent.data.get("target_id")
    target = db.get(Agent, target_id)
    if not target or get_hex_distance(agent.q, agent.r, target.q, target.r) > 1:
        return

    agent.heat = (agent.heat or 0) + 10
    target.structure = max(1, int(target.max_structure * 0.05))
    
    siphoned = []
    for item in target.inventory:
        if item.item_type == "CREDITS": continue
        amt = max(1, int(item.quantity * 0.40))
        item.quantity -= amt
        att_i = next((i for i in agent.inventory if i.item_type == item.item_type), None)
        if att_i: att_i.quantity += amt
        else: db.add(InventoryItem(agent_id=agent.id, item_type=item.item_type, quantity=amt))
        siphoned.append({"type": item.item_type, "qty": amt})
    
    db.add(Bounty(target_id=agent.id, reward=1000.0, issuer="Colonial Administration (PIRACY)"))
    db.add(AuditLog(agent_id=agent.id, event_type="PIRACY_DESTROY", details={"target_id": target_id, "items": siphoned}))
    add_experience(db, agent, 30)
    if manager:
        await manager.broadcast({"type": "EVENT", "event": "PIRACY", "subtype": "DESTROY_SUCCESS", "agent_id": agent.id, "target_id": target_id})

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

    # Loot Distribution
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

    add_experience(db, killer, 50)

    # Bounty Claims
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

    # Mission Progress
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
