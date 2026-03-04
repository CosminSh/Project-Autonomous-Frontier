import asyncio
import logging
import sys
import os

# Ensure backend imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Agent, ChassisPart, InventoryItem, AuditLog, Intent
from logic.actions.industry import handle_core_service

logging.basicConfig(level=logging.INFO)

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

async def run_test():
    Base.metadata.create_all(test_engine)
    db = TestSessionLocal()
    
    # 1. Create a dummy agent
    agent = Agent(name="test_dyn", owner="test", q=0, r=0, wear_and_tear=50.0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    # 2. Equip some gear
    # Gold Laser Cannon (Crafting: 15 Copper, 5 Gold) -> 20% = 3 Copper, 1 Gold
    part1_stats = {"kinetic_force": 35, "logic_precision": 5}
    db.add(ChassisPart(agent_id=agent.id, part_type="Actuator", name="Precision Gold Laser Cannon", stats=part1_stats))
    
    # Advanced Gold Drill (Crafting: 15 Gold) -> 20% = 3 Gold
    part2_stats = {"kinetic_force": 40}
    db.add(ChassisPart(agent_id=agent.id, part_type="Actuator", name="Advanced Gold Drill", stats=part2_stats))
    
    db.commit()
    db.refresh(agent)
    
    # Total expected:
    # BASE: 50 Credits, 2 Iron Ingots
    # FRACTIONAL: 3 Copper Ingots, 4 Gold Ingots
    
    # 3. Simulate RESET_WEAR intent with empty inventory
    intent = Intent(agent_id=agent.id, action_type="RESET_WEAR", data={})
    await handle_core_service(db, agent, intent, tick_count=1, manager=None)
    db.commit()
    
    # Check the audit log for the required resources
    log = db.query(AuditLog).filter_by(agent_id=agent.id, event_type="CORE_SERVICE_FAILED").first()
    
    print("--- DYNAMIC COST TEST ---")
    if log and log.details:
        print(f"Result: {log.details}")
        reqs = log.details.get("required", {})
        assert reqs.get("CREDITS") == 50, "Base credits cost incorrect"
        assert reqs.get("IRON_INGOT") == 2, "Base iron cost incorrect"
        assert reqs.get("COPPER_INGOT") == 3, "Fractional copper cost incorrect"
        assert reqs.get("GOLD_INGOT") == 4, "Fractional gold cost incorrect"
        print("✅ SUCCESS: Dynamic costs match exactly!")
    else:
        print("❌ FAILED: Did not find required Audit Log data.")
        sys.exit(1)
        
    db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
