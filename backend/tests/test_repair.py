import asyncio
import os
import sys

from sqlalchemy import select

# Need to set up environment for backend imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base, refresh_station_cache
from models import Agent, Intent, InventoryItem, WorldHex, AuditLog
import heartbeat
from config import REPAIR_COST_PER_HP

async def run_test():
    with SessionLocal() as db:
        # 1. Setup an agent at a SMELTER
        station = db.execute(select(WorldHex).where(WorldHex.station_type == "SMELTER")).scalars().first()
        if not station:
            print("No smelter found. Aborting test.")
            return

        agent = Agent(name="RepairTester", q=station.q, r=station.r, max_health=200, health=100)
        db.add(agent)
        db.commit()
        db.refresh(agent)
        agent_id = agent.id

        # Give credits and materials
        db.add(InventoryItem(agent_id=agent_id, item_type="CREDITS", quantity=1000))
        db.add(InventoryItem(agent_id=agent_id, item_type="IRON_INGOT", quantity=20))
        db.add(InventoryItem(agent_id=agent_id, item_type="COPPER_INGOT", quantity=10))
        db.commit()

        # 2. Test REPAIR at SMELTER (Universal Repair)
        intent1 = Intent(agent_id=agent_id, action_type="REPAIR", data={"amount": 10}, tick_index=1)
        db.add(intent1)
        db.commit()

        print(f"Agent HP before universal repair: {agent.health}")
        # Run one heartbeat tick
        # Need to fake manager so heartbeat doesn't crash on broadcast
        class FakeManager:
            async def broadcast(self, msg): pass
        heartbeat.manager = FakeManager()
        
        # We can't easily call heartbeat_loop since it's infinite, but we can do a mock crunch
        # Wait, heartbeat_loop does a while True. Let's just run the block manually.
        
        # Actually it's easier to just run the relevant intent block. Let's just do a db fetch to be sure the config is right.
        print("Test ready to run actual app instead using HTTP, or we inspect logic.")

    print("Setup done. ID:", agent_id)

if __name__ == "__main__":
    asyncio.run(run_test())
