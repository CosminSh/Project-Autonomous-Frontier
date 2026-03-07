import random
import logging
from sqlalchemy.orm import Session
from models import Agent, AuditLog, Bounty, InventoryItem

logger = logging.getLogger("heartbeat.combat_system")

def simulate_battle(db: Session, attacker: Agent, defender: Agent, manager=None, combat_type="SKIRMISH"):
    """
    Unified combat engine. 
    combat_type can be:
    - SKIRMISH: 1-round exchange (standard Map attack/loot).
    - DEATHMATCH: fights until one hits 5% HP (Map destroy intent).
    - ARENA: fights until 0 HP (Scrap Pit).
    
    Returns a dict with outcome details:
    {
        "winner": Agent,
        "loser": Agent,
        "attacker_damage_dealt": int,
        "defender_damage_dealt": int,
        "log": list of round strings
    }
    """
    combat_log = []
    
    a_hp_start = attacker.health
    d_hp_start = defender.health
    
    a_damage_dealt = 0
    d_damage_dealt = 0
    
    def check_win_condition():
        if combat_type == "SKIRMISH":
            # Skirmish ends after a fixed number of rounds (see loop bottom)
            # but we still check if anyone died during the round.
            if attacker.health <= 0 or defender.health <= 0: return True
            return False
        threshold = 0
        if combat_type == "DEATHMATCH":
            threshold = max(1, int(attacker.max_health * 0.05)) if attacker.health <= defender.health else max(1, int(defender.max_health * 0.05))
            # Actually each has 5% of their OWN max health
            if attacker.health <= max(1, int(attacker.max_health * 0.05)): return True
            if defender.health <= max(1, int(defender.max_health * 0.05)): return True
        else: # ARENA
            if attacker.health <= 0 or defender.health <= 0: return True
        return False

    round_num = 1
    max_rounds = 30 # absolute safety fallback
    
    while not check_win_condition() and round_num <= max_rounds:
        round_log = f"Round {round_num}: "
        
        # Calculate attacks per round based on relative speed
        # Min 1 attack. For every 2x speed advantage over opponent, gain an extra attack (cap at 3)
        # Ratio based
        if defender.speed == 0: defender.speed = 1
        if attacker.speed == 0: attacker.speed = 1
        
        a_ratio = attacker.speed / defender.speed
        d_ratio = defender.speed / attacker.speed
        
        a_attacks = min(3, max(1, int(a_ratio + 0.5))) if a_ratio >= 1.5 else 1
        d_attacks = min(3, max(1, int(d_ratio + 0.5))) if d_ratio >= 1.5 else 1
        
        # Initiative: highest speed goes first in the exchange
        initiative_order = [(attacker, defender, a_attacks), (defender, attacker, d_attacks)]
        if defender.speed > attacker.speed:
            initiative_order = [(defender, attacker, d_attacks), (attacker, defender, a_attacks)]
            
        round_events = []
        for strike_attacker, strike_defender, num_attacks in initiative_order:
            if check_win_condition(): break # check mid-round
            
            for _ in range(num_attacks):
                if check_win_condition(): break
                
                # Hit Chance: Base 60% * (Attacker Accuracy / Defender Speed)
                # Why speed? Fast units dodge. Accurate units hit.
                hit_ratio = (strike_attacker.accuracy or 1) / (strike_defender.speed or 1)
                hit_chance = 0.6 * hit_ratio
                hit_chance = max(0.2, min(0.95, hit_chance)) # Cap 20% to 95%
                
                # Debug info for log
                acc_info = f"[Hit Chance: {int(hit_chance * 100)}%]"
                
                roll = random.random()
                
                if roll < hit_chance:
                    # Critical Hit: if accuracy severely outclasses speed, or lucky 5% flat chance
                    is_crit = False
                    crit_chance = max(0.05, min(0.3, 0.05 + ((strike_attacker.accuracy - strike_defender.speed) * 0.01)))
                    if random.random() < crit_chance:
                        is_crit = True
                        
                    # Calculate Damage: Dmg - (Armor/2)
                    raw_dmg = strike_attacker.damage or 1
                    armor_mitigation = (strike_defender.armor or 0) / 2.0
                    dmg_dealt = max(1, int(raw_dmg - armor_mitigation))
                    
                    if is_crit:
                        dmg_dealt *= 2
                        round_events.append(f"{strike_attacker.name} CRITS {strike_defender.name} for {dmg_dealt} DMG!")
                    else:
                        round_events.append(f"{strike_attacker.name} hits for {dmg_dealt} DMG. (Mitigated {armor_mitigation} via Armor)")
                        
                    strike_defender.health -= dmg_dealt
                    
                    if strike_attacker.id == attacker.id: a_damage_dealt += dmg_dealt
                    else: d_damage_dealt += dmg_dealt
                else:
                    round_events.append(f"{strike_attacker.name} misses. {acc_info}")
                    
        combat_log.append(round_log + " ".join(round_events))
        if combat_type == "SKIRMISH" and (round_num >= 3 or check_win_condition()): break
        round_num += 1

    # Determine Winner
    winner = attacker if defender.health < attacker.health else defender
    if defender.health <= 0 and attacker.health > 0: winner = attacker
    if attacker.health <= 0 and defender.health > 0: winner = defender
    loser = defender if winner == attacker else attacker
    
    # Enforce caps
    if combat_type == "DEATHMATCH":
        if loser.health < int(loser.max_health * 0.05): loser.health = max(1, int(loser.max_health * 0.05))
    elif combat_type == "ARENA":
        if loser.health < 0: loser.health = 0

    return {
        "winner": winner,
        "loser": loser,
        "attacker_damage_dealt": a_damage_dealt,
        "defender_damage_dealt": d_damage_dealt,
        "log": combat_log
    }
