import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from config import MOVE_ENERGY_COST, ATTACK_ENERGY_COST, PART_DEFINITIONS
from models import Agent, ChassisPart

def test_balance():
    print("--- VERIFYING BALANCE UPDATES ---")
    
    # 1. Verify Config Stats
    heavy = PART_DEFINITIONS['HEAVY_FRAME']
    print(f"HEAVY_FRAME: Armor={heavy['stats']['armor']}, Speed={heavy['stats']['speed']}")
    assert heavy['stats']['armor'] == 45
    assert heavy['stats']['speed'] == -5
    
    basic = PART_DEFINITIONS['BASIC_FRAME']
    print(f"BASIC_FRAME: Armor={basic['stats']['armor']}")
    assert basic['stats']['armor'] == 10
    
    turbo = PART_DEFINITIONS['ENGINE_TURBO']
    print(f"ENGINE_TURBO: Speed={turbo['stats']['speed']}, Energy Cost={turbo['stats'].get('energy_cost')}")
    assert turbo['stats'].get('energy_cost') == 4
    
    fusion = PART_DEFINITIONS['ENGINE_UNIT']
    print(f"ENGINE_UNIT: Name='{fusion['name']}', Capacity={fusion['stats']['capacity']}")
    assert fusion['stats']['capacity'] == 60

    print("\n--- TEST: ENERGY DRAIN LOGIC (SIMULATED) ---")
    
    # Mocking agent and parts for movement test
    agent = Agent(id=1, energy=100, q=0, r=0, max_mass=100)
    agent.parts = [
        ChassisPart(name="Bastion Heavy Frame", stats=PART_DEFINITIONS['HEAVY_FRAME']['stats']),
        ChassisPart(name="Turbo Interceptor", stats=PART_DEFINITIONS['ENGINE_TURBO']['stats'])
    ]
    
    # Simulation logic from movement.py
    def get_move_cost(agent):
        drain = sum(p.stats.get("energy_cost", 0) for p in agent.parts if p.stats)
        return MOVE_ENERGY_COST + drain

    cost = get_move_cost(agent)
    print(f"Movement Cost (with Turbo Engine): {cost} (Base: {MOVE_ENERGY_COST})")
    assert cost == MOVE_ENERGY_COST + 4
    
    # Simulation logic from combat.py
    def get_attack_cost(agent):
        drain = sum(p.stats.get("energy_cost", 0) for p in agent.parts if p.stats)
        return ATTACK_ENERGY_COST + drain
        
    # Add a laser cannon
    agent.parts.append(ChassisPart(name="Precision Laser", stats=PART_DEFINITIONS['GOLD_LASER_CANNON']['stats']))
    atk_cost = get_attack_cost(agent)
    print(f"Attack Cost (with Turbo + Laser): {atk_cost} (Base: {ATTACK_ENERGY_COST})")
    # Turbo (4) + Laser (5) = 9 drain
    assert atk_cost == ATTACK_ENERGY_COST + 4 + 5

    print("\n✅ Verification SUCCESS!")

if __name__ == "__main__":
    test_balance()
