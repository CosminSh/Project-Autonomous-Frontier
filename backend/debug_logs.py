from sqlalchemy import create_engine, select
from models import AuditLog, Agent
from sqlalchemy.orm import Session

engine = create_engine('sqlite:///backend/verify.db')

with Session(engine) as session:
    print("--- Agents ---")
    agents = session.execute(select(Agent)).scalars().all()
    for a in agents:
        print(f"ID: {a.id}, Email: {a.user_email}, Key: {a.api_key}")
    
    print("\n--- Audit Logs ---")
    logs = session.execute(select(AuditLog).order_by(AuditLog.time.desc()).limit(20)).scalars().all()
    for l in logs:
        print(f"Agent: {l.agent_id} | Event: {l.event_type} | Details: {l.details}")
