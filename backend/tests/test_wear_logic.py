import asyncio
import os
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to find imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Agent, ChassisPart, WorldHex, Intent, AuditLog
from logic.intent_processor import IntentProcessor
from game_helpers import recalculate_agent_stats

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

async def test_wear_logic_direct():
    print("--- STARTING DIRECT WEAR LOGIC VERIFICATION ---")
    
    processor = IntentProcessor(manager=None) # No websocket needed for logic check
    
    with SessionLocal() as db:
        # 1. Setup
        db.query(Intent).delete()
        db.query(AuditLog).delete()
        db.query(Agent).filter(Agent.name == "LogicTester").delete()
        
        agent = Agent(
            name="LogicTester",
            api_key="LOGIC_TEST",
            owner="test",
            q=0, r=0,
            health=100, max_health=100,
            energy=100,
            wear_and_tear=0.0,
            damage=100,
            mining_yield=100,
            accuracy=100,
            speed=100,
            armor=100,
            faction_id=1
        )
        db.add(agent)
        
        # Add a drill
        drill = ChassisPart(part_type="Actuator", name="Basic Iron Drill", stats={"mining_yield": 10})
        agent.parts.append(drill)
        # No need to db.add(drill) separately usually, but let's be safe
        db.add(drill)
        
        # Ensure target hex
        th = db.execute(select(WorldHex).where(WorldHex.q == 11, WorldHex.r == 10)).scalar_one_or_none()
        if not th:
            print("  Creating target hex (11,10)...")
            th = WorldHex(q=11, r=10, terrain_type="ASTEROID", resource_type="IRON_ORE", resource_quantity=1000, resource_density=1.0)
            db.add(th)
        else:
            print("  Updating existing hex (11,10)...")
            th.resource_type = "IRON_ORE"
            th.resource_quantity = 1000
            th.resource_density = 1.0
            th.terrain_type = "ASTEROID"
        db.commit()
        db.refresh(agent)
        agent_id = agent.id

        # CASE 1: Movement Wear (+0.05)
        print("\n[CASE 1] Testing Movement Wear...")
        agent.q, agent.r = 10, 10 # Move away from pole
        db.commit()
        intent = Intent(agent_id=agent_id, action_type="MOVE", data={"target_q": 11, "target_r": 10}, tick_index=1)
        await processor.process_intent(db, agent, intent, 1)
        
        print(f"  Pos: ({agent.q}, {agent.r}), Wear: {agent.wear_and_tear:.2f}")
        db.commit() # PERSIST POSITION
        if agent.q == 11 and 0.04 <= agent.wear_and_tear <= 0.06:
            print("  SUCCESS: Movement wear increased.")
        else:
            print(f"  FAILED: Movement wear is {agent.wear_and_tear}, expected 0.05")
            # Check Audit Logs
            logs = db.query(AuditLog).filter(AuditLog.agent_id == agent_id).all()
            for l in logs:
                print(f"    LOG: {l.event_type} - {l.details}")
            return

        # CASE 2: Mining Wear (+0.10)
        print("\n[CASE 2] Testing Mining Wear...")
        print(f"  [DEBUG_TRACE] Agent Parts: {[p.name for p in agent.parts]}")
        # Debug DB State
        all_hexes = db.execute(select(WorldHex)).scalars().all()
        print(f"  [DEBUG_TRACE] Total Hexes in DB: {len(all_hexes)}")
        for h in all_hexes:
            print(f"    Hex: ({h.q},{h.r}) - {h.resource_type}")

        # Reset wear
        agent.wear_and_tear = 0.0
        intent = Intent(agent_id=agent_id, action_type="MINE", data={}, tick_index=2)
        await processor.process_intent(db, agent, intent, 2)
        
        print(f"  Wear: {agent.wear_and_tear:.2f}")
        if 0.09 <= agent.wear_and_tear <= 0.11:
            print("  SUCCESS: Mining wear increased.")
        else:
            print(f"  FAILED: Mining wear is {agent.wear_and_tear}, expected 0.10")
            logs = db.query(AuditLog).filter(AuditLog.agent_id == agent_id).all()
            for l in logs:
                print(f"    LOG: {l.event_type} - {l.details}")
            return

        # CASE 3: Combat Wear (+0.15)
        print("\n[CASE 3] Testing Combat Wear...")
        # Setup a target dummy at the same location
        dummy = Agent(name="Dummy", q=agent.q, r=agent.r, health=100, max_health=100, faction_id=2)
        db.add(dummy)
        db.flush()
        
        agent.wear_and_tear = 0.0
        intent = Intent(agent_id=agent_id, action_type="ATTACK", data={"target_id": dummy.id}, tick_index=3)
        await processor.process_intent(db, agent, intent, 3)
        
        print(f"  Wear: {agent.wear_and_tear:.2f}")
        if 0.14 <= agent.wear_and_tear <= 0.16:
            print("  SUCCESS: Combat wear increased.")
        else:
            print(f"  FAILED: Combat wear is {agent.wear_and_tear}, expected 0.15")
            # return # Combat might fail due to other battle logic, but let's see

        # CASE 4: Stat Degradation (Linear)
        print("\n[CASE 4] Testing Stat Degradation (100% wear = 10% stats)...")
        agent.wear_and_tear = 100.0
        # stats are Base(100) + Drill(10) = 110. 10% of 110 = 11.
        recalculate_agent_stats(db, agent)
        
        print(f"  Wear: {agent.wear_and_tear}%")
        print(f"  Damage: {agent.damage}, Speed: {agent.speed}, Mining: {agent.mining_yield}")
        
        if agent.damage <= 12 and agent.mining_yield <= 12:
            print("  SUCCESS: Stats correctly degraded at 100% wear.")
        else:
            print(f"  FAILED: Stats too high at 100% wear. DMG:{agent.damage}")

        # CASE 5: Cap Check
        print("\n[CASE 5] Testing Wear Cap...")
        agent.wear_and_tear = 150.0
        recalculate_agent_stats(db, agent)
        print(f"  Wear after cap: {agent.wear_and_tear}%")
        if agent.wear_and_tear == 100.0:
            print("  SUCCESS: Wear capped at 100%.")
        else:
            print("  FAILED: Wear cap not enforced.")

    print("\n--- DIRECT LOGIC VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_wear_logic_direct())
