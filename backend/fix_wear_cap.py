from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import os
import sys

# Add current directory to path to import models
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from models import Agent

db_url = os.getenv("DATABASE_URL", "sqlite:///backend/terminal_frontier.db")
engine = create_engine(db_url)

with Session(engine) as session:
    agent = session.execute(select(Agent).where(Agent.name == "Wabbs")).scalar_one_or_none()
    if agent:
        print(f"Agent {agent.name} current wear: {agent.wear_and_tear}")
        if agent.wear_and_tear > 100.0:
            print("Capping wear at 100.0...")
            agent.wear_and_tear = 100.0
            session.commit()
            print("Wear capped successfully.")
        else:
            print("Wear already at or below 100.0.")
    else:
        # List all agents if not found
        all_agents = session.execute(select(Agent)).scalars().all()
        print(f"Agent 'Wabbs' not found. Available agents: {[a.name for a in all_agents]}")
