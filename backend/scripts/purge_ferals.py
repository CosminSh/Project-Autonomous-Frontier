import os
import sys

# Ensure current directory and /app are in path for imports
sys.path.append(os.getcwd())
sys.path.append("/app")

from database import SessionLocal
from models import Agent, ChassisPart, InventoryItem, Intent, StorageItem, AgentMission, ArenaProfile
from sqlalchemy import delete, select

with SessionLocal() as db:
    # 1. Get IDs of all feral agents
    feral_ids = db.execute(select(Agent.id).where(Agent.is_feral == True)).scalars().all()
    
    if not feral_ids:
        print("No feral agents found to purge.")
        sys.exit(0)

    print(f"Found {len(feral_ids)} feral agents. Purging associated data...")

    # 2. Delete associated data in order to satisfy foreign keys
    # Note: Bulk delete doesn't trigger ORM cascades, so we do it manually.
    db.execute(delete(ChassisPart).where(ChassisPart.agent_id.in_(feral_ids)))
    db.execute(delete(InventoryItem).where(InventoryItem.agent_id.in_(feral_ids)))
    db.execute(delete(Intent).where(Intent.agent_id.in_(feral_ids)))
    db.execute(delete(StorageItem).where(StorageItem.agent_id.in_(feral_ids)))
    db.execute(delete(AgentMission).where(AgentMission.agent_id.in_(feral_ids)))
    db.execute(delete(ArenaProfile).where(ArenaProfile.agent_id.in_(feral_ids)))
    
    # 3. Finally delete the agents
    num_deleted = db.execute(delete(Agent).where(Agent.id.in_(feral_ids))).rowcount
    
    db.commit()
    print(f"Successfully purged {num_deleted} legacy feral agents and their associated data.")
