import time
import asyncio
import logging
from sqlalchemy import select, func, text
from database import SessionLocal
from models import Agent, InventoryItem, StorageItem, Intent, AuditLog, WorldHex

logging.basicConfig(level=logging.INFO)

async def check_counts():
    with SessionLocal() as db:
        print("Checking Table Counts...")
        tables = ["agents", "inventory_items", "storage_items", "intents", "audit_log", "world_hexes", "chassis_parts"]
        for t in tables:
            try:
                res = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                print(f"Table {t:20}: {res:10}")
            except Exception as e:
                print(f"Error checking {t}: {e}")
        
        # Check for heavy agents
        print("\nChecking for Heavy Inventories (Top 5)...")
        heavy = db.execute(text("SELECT agent_id, count(*) as c FROM inventory_items GROUP BY 1 ORDER BY 2 DESC LIMIT 5")).all()
        for r in heavy:
            agent = db.get(Agent, r.agent_id)
            print(f"Agent {r.agent_id:5} ({agent.name if agent else '???'}): {r.c:10} items")
            
        print("\nChecking for Heavy Storage (Top 5)...")
        heavy_s = db.execute(text("SELECT agent_id, count(*) as c FROM storage_items GROUP BY 1 ORDER BY 2 DESC LIMIT 5")).all()
        for r in heavy_s:
            agent = db.get(Agent, r.agent_id)
            print(f"Agent {r.agent_id:5} ({agent.name if agent else '???'}): {r.c:10} items")

if __name__ == "__main__":
    asyncio.run(check_counts())
