import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from logic.actions.industry import handle_smelt
from config import SMELTING_RATIO

class MockAgent:
    def __init__(self):
        self.id = 1
        self.q = 0
        self.r = 0
        self.energy = 1000
        self.inventory = []
        self.storage = []
        self.corporation_id = None
        self.max_health = 100
        self.health = 100
        self.unlocked_recipes = []
        self.performance_stats = None

class MockItem:
    def __init__(self, item_type, quantity):
        self.item_type = item_type
        self.quantity = quantity

class MockIntent:
    def __init__(self, data):
        self.data = data

async def test_smelt():
    print("Testing Titanium Smelting...")
    
    db = MagicMock()
    agent = MockAgent()
    agent.inventory = [MockItem("TITANIUM_ORE", 10)]
    intent = MockIntent({"ore_type": "TITANIUM_ORE", "quantity": 5})
    
    # Mock STATION_CACHE and helper functions
    with patch('database.STATION_CACHE', [{"station_type": "SMELTER", "q": 0, "r": 0}]):
        with patch('logic.actions.industry.get_total_resource', return_value=10):
            with patch('logic.actions.industry.consume_resources', return_value=True):
                with patch('logic.actions.industry.add_experience') as mock_exp:
                    with patch('logic.actions.industry.update_performance_stat') as mock_perf:
                        with patch('logic.actions.industry.recalculate_agent_stats') as mock_stats:
                            await handle_smelt(db, agent, intent, 0, None)
                
    # Verify AuditLog was added (expecting SUCCESS)
    # The handlesmelt calls db.add(AuditLog(...)) and db.add(InventoryItem(...)) or updates existing
    
    calls = db.add.call_args_list
    print(f"Total DB calls: {len(calls)}")
    
    success = False
    for call in calls:
        arg = call[0][0]
        arg_type = type(arg).__name__
        print(f"Call with {arg_type}")
        if arg_type == 'AuditLog':
            print(f"AuditLog Event: {arg.event_type}")
            if arg.event_type == 'INDUSTRIAL_SMELT':
                success = True
                print(f"Details: {arg.details}")
        if arg_type == 'InventoryItem':
            print(f"Produced: {arg.item_type} x{arg.quantity}")
            if arg.item_type == 'TITANIUM_INGOT':
                print("SUCCESS: Titanium Ingot produced!")

    if success:
        print("\n=== TEST PASSED ===")
    else:
        print("\n=== TEST FAILED ===")

if __name__ == "__main__":
    asyncio.run(test_smelt())
