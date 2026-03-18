from sqlalchemy import create_all, select, update
from sqlalchemy.orm import Session
from models import Agent, Base
import os

db_url = os.getenv("DATABASE_URL", "sqlite:///backend/terminal_frontier.db")
from sqlalchemy import create_engine
engine = create_engine(db_url)

with Session(engine) as session:
    agent = session.execute(select(Agent).where(Agent.name == "Wabbs")).scalar_one_or_none()
    if agent:
        print(f"Agent {agent.name} current wear: {agent.wear_and_tear}")
        if agent.wear_and_tear > 100.0:
            print("Capping wear at 100.0")
            agent.wear_and_tear = 100.0
            session.commit()
            print("Wear capped successfully.")
    else:
        print("Agent 'Wabbs' not found.")
