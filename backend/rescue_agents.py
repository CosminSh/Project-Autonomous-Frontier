from database import SessionLocal
from models import Agent, AuditLog
from game_helpers import get_world_bounds
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rescue")

def rescue_agents():
    db = SessionLocal()
    bounds = get_world_bounds(db)
    
    # Find all agents
    agents = db.query(Agent).all()
    rescued = 0
    
    for agent in agents:
        wq, wr = wrap_coords(agent.q, agent.r)
        if wq != agent.q or wr != agent.r:
            logger.info(f"Agent {agent.name} (ID: {agent.id}) is out of bounds/needs wrapping at ({agent.q}, {agent.r}). Wrapping to ({wq}, {wr}).")
            agent.q = wq
            agent.r = wr
            
            # Log it for the agent's history
            db.add(AuditLog(agent_id=agent.id, event_type="ADMIN_RESCUE", details={"reason": "COORDINATE_WRAP_SYNC"}))
            rescued += 1
            
    if rescued > 0:
        db.commit()
        logger.info(f"Successfully rescued {rescued} agents.")
    else:
        logger.info("No agents are out of bounds.")
        
    db.close()

if __name__ == "__main__":
    rescue_agents()
