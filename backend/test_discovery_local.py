import os
os.environ["DATABASE_URL"] = "sqlite:///./terminal_frontier.db"
from database import SessionLocal, STATION_CACHE, refresh_station_cache
from models import Agent
from game_helpers import get_discovery_packet

db = SessionLocal()
refresh_station_cache()
print("Station Cache:", STATION_CACHE)

agent = db.query(Agent).first()
if getattr(agent, "id", None):
    print(f"Agent {agent.id} at {agent.q}, {agent.r}")
    discovery = get_discovery_packet(STATION_CACHE, agent)
    print("Discovery Packet:", discovery)
else:
    print("No agent found")
