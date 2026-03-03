from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Agent, GlobalState

async def verify_api_key(request: Request, db: Session = Depends(get_db)):
    """Dependency to authenticate agents via API key in headers."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    agent = db.execute(select(Agent).where(Agent.api_key == api_key)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return agent

def get_next_tick_index(db: Session):
    """Returns the tick index for the next game simulation step."""
    state = db.execute(select(GlobalState)).scalars().first()
    return (state.tick_index + 1) if state else 1
