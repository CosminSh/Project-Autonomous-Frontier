import os
os.environ["DATABASE_URL"] = "sqlite:///./strike_vector.db"
from database import SessionLocal
from models import Agent

db = SessionLocal()
agent = db.query(Agent).first()

if agent:
    print(f"Agent ID: {agent.id}")
    power_part = next((p for p in agent.parts if p.part_type == "Power"), None)
    if power_part:
        print(f"Power Part: {power_part.name}, stats: {power_part.stats}")
        eff = (power_part.stats or {}).get("efficiency", 1.0)
        print(f"Efficiency: {eff}")
    else:
        print("No power part!")
else:
    print("No agent found")
