"""
arena_manager.py
Handles the asynchronous Scrap Pit PvP battles and season resets.
"""

import logging
import random
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Agent, AuditLog, ChassisPart, InventoryItem
from database import SessionLocal
from logic.combat_system import simulate_battle
from game_helpers import recalculate_agent_stats

logger = logging.getLogger("heartbeat.arena")

def resolve_battle(f1: Agent, f2: Agent, db: Session):
    """
    Simulates a battle between two pit fighters based on stats.
    Returns the winner and a brief log string.
    """
    outcome = simulate_battle(db, f1, f2, manager=None, combat_type="ARENA")
    winner = outcome["winner"]
    loser = outcome["loser"]

    # Elo calculation (K-factor 32)
    expected_win = 1 / (1 + 10 ** ((loser.arena_profile.elo - winner.arena_profile.elo) / 400))
    elo_change = int(32 * (1 - expected_win))
    
    # Ensure minimum gain/loss
    if elo_change < 1: elo_change = 1

    old_w_elo = winner.arena_profile.elo
    old_l_elo = loser.arena_profile.elo

    winner.arena_profile.elo += elo_change
    winner.arena_profile.wins += 1
    loser.arena_profile.elo = max(0, loser.arena_profile.elo - elo_change)
    loser.arena_profile.losses += 1

    # Audit Logs
    log_w = f"You defeated {loser.name} (Elo: {old_l_elo}) in the Scrap Pit! Rating changed: {old_w_elo} -> {winner.arena_profile.elo} (+{elo_change})"
    log_l = f"You were defeated by {winner.name} (Elo: {old_w_elo}) in the Scrap Pit. Rating changed: {old_l_elo} -> {loser.arena_profile.elo} (-{elo_change})"

    db.add(AuditLog(agent_id=winner.id, event_type="ARENA_VICTORY", details={"message": log_w, "opponent_id": loser.id, "elo_delta": elo_change, "log": outcome["log"]}))
    db.add(AuditLog(agent_id=loser.id, event_type="ARENA_DEFEAT", details={"message": log_l, "opponent_id": winner.id, "elo_delta": -elo_change, "log": outcome["log"]}))

    # [NEW] Rare Material Reward: ARENA_REMAINS (10% chance for winner)
    if random.random() < 0.10:
        remains_item = next((i for i in winner.inventory if i.item_type == "ARENA_REMAINS"), None)
        if remains_item: remains_item.quantity += 1
        else:
            db.add(InventoryItem(agent_id=winner.id, item_type="ARENA_REMAINS", quantity=1))
        db.add(AuditLog(agent_id=winner.id, event_type="RARE_DISCOVERY", details={"item": "ARENA_REMAINS", "source": "ARENA_WIN"}))
        logger.info(f"ARENA: Winner {winner.name} found ARENA_REMAINS!")

    # Also log permanent gear durability loss (5% flat reduction per battle)
    w_parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == winner.id)).scalars().all()
    l_parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == loser.id)).scalars().all()
    
    for part in w_parts + l_parts:
        part.durability = max(0.0, part.durability - 5.0)

    db.commit()


def trigger_arena_battles(db: Session):
    """
    Finds all active pit fighters, buckets them by Elo, and forces matches.
    """
    logger.info("Triggering Scrap Pit Arena Battles...")
    
    # Get all pit fighters from world that have a profile
    from models import ArenaProfile
    fighters = db.execute(
        select(Agent)
        .join(ArenaProfile)
        .order_by(ArenaProfile.elo.desc())
    ).scalars().all()

    # Filter out fighters with literally no gear
    active_fighters = [f for f in fighters if f.health > 0 and f.damage > 0]
    
    if len(active_fighters) < 2:
        logger.info("Not enough active Pit Fighters to match.")
        return

    # Shuffle slightly within localized Elo bands to prevent identical repeat matchups
    matched = set()
    matches_made = 0

    for i in range(len(active_fighters)):
        if i in matched: continue
        f1 = active_fighters[i]
        
        # Find next available opponent within reasonable Elo range (e.g., +/- 300)
        # Since list is sorted by Elo, looking at next indices is sufficient
        f2_idx = None
        for j in range(i + 1, len(active_fighters)):
            if j not in matched:
                if abs(f1.arena_profile.elo - active_fighters[j].arena_profile.elo) <= 300:
                    f2_idx = j
                    break
        
        # If no close match, just take the absolute closest available to not leave them hanging
        if f2_idx is None:
            for j in range(i + 1, len(active_fighters)):
                if j not in matched:
                    f2_idx = j
                    break
        
        if f2_idx is not None:
            f2 = active_fighters[f2_idx]
            matched.add(i)
            matched.add(f2_idx)
            resolve_battle(f1, f2, db)
            matches_made += 1

    logger.info(f"Arena processing complete. Resolved {matches_made} matches.")


def reset_arena_season(db: Session):
    """
    Wipes ALL chassis parts attached to pit fighters and resets Elo.
    This acts as the massive weekly gear sink.
    """
    logger.info("Initializing Scrap Pit Season Reset...")
    
    from models import ArenaProfile
    fighters = db.execute(
        select(Agent)
        .join(ArenaProfile)
    ).scalars().all()
    
    total_parts_destroyed = 0
    for f in fighters:
        # Delete parts
        parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == f.id)).scalars().all()
        for p in parts:
            db.delete(p)
            total_parts_destroyed += 1
            
            
        # Reset Stats to base (empty chassis frame) using proper helper
        recalculate_agent_stats(db, f)
        
        # Soft reset Elo (compress towards 1200)
        profile = f.arena_profile
        if profile:
            profile.elo = 1200 + ((profile.elo - 1200) // 2)
            profile.wins = 0
            profile.losses = 0

    db.commit()
    logger.info(f"Season Reset Complete. Destroyed {total_parts_destroyed} pieces of gear across {len(fighters)} Pit Fighters.")


def generate_daily_matchups(db: Session):
    """
    For every active Pit Fighter, generate a list of 3 potential opponents
    within their Elo range that they can challenge today.
    """
    logger.info("Generating daily Arena matchups...")
    
    from models import ArenaProfile
    all_fighters = db.execute(
        select(Agent)
        .join(ArenaProfile)
        .where(Agent.is_pitfighter == True)
    ).scalars().all()

    if len(all_fighters) < 2:
        return

    for agent in all_fighters:
        # Filter potential targets: Pit fighters, not self
        targets = [f for f in all_fighters if f.id != agent.id]
        
        # Sort by Elo proximity
        targets.sort(key=lambda x: abs(x.arena_profile.elo - agent.arena_profile.elo))
        
        # Take the top 5 closest and pick 3 randomly to give some variety
        pool = targets[:5]
        selected = random.sample(pool, min(len(pool), 3))
        
        agent.arena_profile.daily_opponents = [s.id for s in selected]
        
    db.commit()
    logger.info(f"Generated daily matchups for {len(all_fighters)} fighters.")
