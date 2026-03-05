"""
arena_manager.py
Handles the asynchronous Scrap Pit PvP battles and season resets.
"""

import logging
import random
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Agent, AuditLog, ChassisPart
from database import SessionLocal

logger = logging.getLogger("heartbeat.arena")

def resolve_battle(f1: Agent, f2: Agent, db: Session):
    """
    Simulates a battle between two pit fighters based on stats.
    Returns the winner and a brief log string.
    """
    # Calculate effective health
    hp1 = f1.structure
    hp2 = f2.structure
    
    # Calculate effective damage (KF + Logic precision bonus)
    dmg1 = f1.kinetic_force * (1 + (f1.logic_precision / 100.0))
    dmg2 = f2.kinetic_force * (1 + (f2.logic_precision / 100.0))
    
    # Avoid infinite loops / div by zero
    if dmg1 <= 0: dmg1 = 1
    if dmg2 <= 0: dmg2 = 1

    # Time to kill (lower is better/faster)
    ttk1 = hp2 / dmg1
    ttk2 = hp1 / dmg2

    # Add a slight 10% RNG variance to time-to-kill to prevent exact mirrors from always drawing
    ttk1 *= random.uniform(0.9, 1.1)
    ttk2 *= random.uniform(0.9, 1.1)

    winner = None
    loser = None
    if ttk1 < ttk2:
        winner, loser = f1, f2
    elif ttk2 < ttk1:
        winner, loser = f2, f1
    else:
        # Coin flip tiebreaker
        winner, loser = random.choice([(f1, f2), (f2, f1)])

    # Elo calculation (K-factor 32)
    expected_win = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
    elo_change = int(32 * (1 - expected_win))
    
    # Ensure minimum gain/loss
    if elo_change < 1: elo_change = 1

    old_w_elo = winner.elo
    old_l_elo = loser.elo

    winner.elo += elo_change
    winner.arena_wins += 1
    loser.elo = max(0, loser.elo - elo_change)
    loser.arena_losses += 1

    # Audit Logs
    log_w = f"You defeated {loser.name} (Elo: {old_l_elo}) in the Scrap Pit! Rating changed: {old_w_elo} -> {winner.elo} (+{elo_change})"
    log_l = f"You were defeated by {winner.name} (Elo: {old_w_elo}) in the Scrap Pit. Rating changed: {old_l_elo} -> {loser.elo} (-{elo_change})"

    db.add(AuditLog(agent_id=winner.id, event_type="ARENA_VICTORY", details={"message": log_w, "opponent_id": loser.id, "elo_delta": elo_change}))
    db.add(AuditLog(agent_id=loser.id, event_type="ARENA_DEFEAT", details={"message": log_l, "opponent_id": winner.id, "elo_delta": -elo_change}))

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
    
    # Get all pit fighters that have some combat capability (don't match fresh empty bots)
    fighters = db.execute(
        select(Agent)
        .where(Agent.is_pit_fighter == True)
        .order_by(Agent.elo.desc())
    ).scalars().all()

    # Filter out fighters with literally no gear (0 KF or 0 Structure means they haven't been equipped)
    active_fighters = [f for f in fighters if f.structure > 0 and f.kinetic_force > 0]
    
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
                if abs(f1.elo - active_fighters[j].elo) <= 300:
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
    
    fighters = db.execute(select(Agent).where(Agent.is_pit_fighter == True)).scalars().all()
    
    total_parts_destroyed = 0
    for f in fighters:
        # Delete parts
        parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == f.id)).scalars().all()
        for p in parts:
            db.delete(p)
            total_parts_destroyed += 1
            
        # Reset Stats to base (empty chassis frame)
        f.kinetic_force = 0
        f.logic_precision = 0
        f.structure = 0
        f.max_structure = 0
        f.storage_capacity = 0.0
        
        # Soft reset Elo (compress towards 1200)
        f.elo = 1200 + ((f.elo - 1200) // 2)
        f.arena_wins = 0
        f.arena_losses = 0

    db.commit()
    logger.info(f"Season Reset Complete. Destroyed {total_parts_destroyed} pieces of gear across {len(fighters)} Pit Fighters.")
