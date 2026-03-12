import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Agent

DATABASE_URL = "sqlite:///g:/Antigravity Projects/Project Autonomous Frontier/demo.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

from models import WorldHex

def check_pitfighters():
    db = SessionLocal()
    try:
        stations = db.execute(select(WorldHex).where(WorldHex.is_station == True)).scalars().all()
        print(f"Found {len(stations)} stations:")
        for s in stations:
            print(f"Station: {s.station_type} at ({s.q}, {s.r})")
            # Check for agents at this position
            agents = db.execute(select(Agent).where(Agent.q == s.q, Agent.r == s.r)).scalars().all()
            for a in agents:
                print(f"  Agent: {a.name}, is_pitfighter: {a.is_pitfighter}")
    finally:
        db.close()

if __name__ == "__main__":
    check_pitfighters()
