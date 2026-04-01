import sys
import os
import asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from models import Base, Agent, Intent, AuditLog
from logic.state_updates import update_global_agent_stats
from logic.bot_logic import process_feral_brain
from config import TOWN_COORDINATES, ANARCHY_THRESHOLD

# setup test DB
engine = create_engine("sqlite:///:memory:")
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

async def test_death_reaper():
    db = Session()
    print("Testing Global Death Reaper...")
    
    # 1. Create a dead agent
    p1 = Agent(name="DeadPlayer", health=-10, max_health=100, q=10, r=10, is_bot=False, is_feral=False)
    db.add(p1)
    db.commit()
    db.refresh(p1)
    
    # 2. Add a stuck intent
    intent = Intent(agent_id=p1.id, action_type="MINE", tick_index=1)
    db.add(intent)
    db.commit()
    
    # Run reaper
    await update_global_agent_stats(db, 0, None)
    
    db.refresh(p1)
    print(f"Agent state after reaper: HP={p1.health}, Pos=({p1.q}, {p1.r})")
    
    # Verify
    assert p1.health == 50
    assert p1.q == TOWN_COORDINATES[0]
    assert p1.r == TOWN_COORDINATES[1]
    
    intents = db.execute(select(Intent).where(Intent.agent_id == p1.id)).scalars().all()
    assert len(intents) == 0
    print("DONE Reaper Test Passed")
    db.close()

async def test_feral_safe_zone():
    db = Session()
    print("\nTesting Feral Safe Zone Logic...")
    
    # 1. Feral Agent
    feral = Agent(name="AggroFeral", health=100, q=1, r=1, is_feral=True, is_aggressive=True)
    db.add(feral)
    
    # 2. Player in Safe Zone (dist < 6)
    player = Agent(name="SafePlayer", health=100, q=0, r=0, is_feral=False, is_bot=False)
    db.add(player)
    db.commit()
    
    # Run brain
    process_feral_brain(db, feral, 0)
    
    # Check intents
    intents = db.execute(select(Intent).where(Intent.agent_id == feral.id)).scalars().all()
    
    # Feral should MOVE randomly, NOT attack SafePlayer
    attack_intents = [i for i in intents if i.action_type == "ATTACK"]
    assert len(attack_intents) == 0
    print("DONE Feral Safe Zone Test Passed (Feral ignored player in safe zone)")
    
    # 3. Move Player to Anarchy Zone
    player.q, player.r = 10, 10
    feral.q, feral.r = 10, 11 # Adjacent
    db.commit()
    
    # Cleanup old intents
    for i in intents: db.delete(i)
    db.commit()
    
    process_feral_brain(db, feral, 1)
    intents = db.execute(select(Intent).where(Intent.agent_id == feral.id)).scalars().all()
    attack_intents = [i for i in intents if i.action_type == "ATTACK"]
    assert len(attack_intents) == 1
    print("DONE Feral Aggro Test Passed (Feral attacked player in anarchy zone)")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_death_reaper())
    asyncio.run(test_feral_safe_zone())
