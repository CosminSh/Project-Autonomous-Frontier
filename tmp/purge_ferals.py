from backend.database import SessionLocal
from backend.models import Agent
from sqlalchemy import delete

with SessionLocal() as db:
    # Delete all feral agents so the TickManager repopulates them with new stats/templates
    num_deleted = db.execute(delete(Agent).where(Agent.is_feral == True)).rowcount
    db.commit()
    print(f"Purged {num_deleted} legacy feral agents.")
