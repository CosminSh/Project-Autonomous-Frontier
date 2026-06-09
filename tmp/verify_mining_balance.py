import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from config import MINING_TIERS

def calculate_yield(mining_yield, res_name, density=1.0, overclock=False):
    roll = 1.0 # Use average roll for testing
    base_yield = (mining_yield or 10) * roll * density
    if overclock: base_yield *= 2.0
    
    hardness = MINING_TIERS.get(res_name, {}).get("hardness", 1.0)
    yield_amount = max(1, int(base_yield / hardness))
    return yield_amount

def run_tests():
    agents = {
        "Starter (1 Yield)": 1,
        "Mid-Tier (40 Yield)": 40,
        "Elite (200 Yield)": 200,
        "Elite Overclocked (200+OC)": 200 # Handled by flag
    }
    
    resources = ["IRON_ORE", "COPPER_ORE", "GOLD_ORE", "COBALT_ORE", "TITANIUM_ORE", "HELIUM_GAS"]
    
    print(f"{'Agent Type':<25} | {'Resource':<15} | {'Yield/Tick'}")
    print("-" * 55)
    
    for agent_desc, yield_stat in agents.items():
        is_oc = "Overclocked" in agent_desc
        for res in resources:
            # Starter might not meet tier requirements, but we're testing the math here
            y = calculate_yield(yield_stat, res, density=1.5, overclock=is_oc)
            print(f"{agent_desc:<25} | {res:<15} | {y}")
        print("-" * 55)

if __name__ == "__main__":
    run_tests()
