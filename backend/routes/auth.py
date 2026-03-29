"""
routes_auth.py — Authentication routes: Google login, guest login, global stats.
"""
import logging
import random
import uuid

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from models import Agent, InventoryItem, ChassisPart, AuctionOrder, APIKeyRevocation
from database import get_db, SessionLocal
from config import PART_DEFINITIONS
from game_helpers import recalculate_agent_stats
from pydantic import BaseModel
from typing import Optional
from routes.common import verify_api_key

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import time

logger = logging.getLogger("heartbeat")
router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "419308259695-sj14gj8q7ml5o9uao2j59pgkp1vvthh0.apps.googleusercontent.com")


class LoginRequest(BaseModel):
    token: str

class GuestLoginRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

@router.post("/auth/login")
def login(request: Request, login_data: LoginRequest):
    print("\n--- AUTH LOGIN REQUEST RECEIVED ---")
    try:
        token = login_data.token
        if not token:
            return {"status": "error", "message": "Missing token"}

        try:
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
            
            # Verify token not too old (max 1 hour / 3600 seconds)
            token_age = time.time() - idinfo.get("iat", 0)
            if token_age > 3600:
                 return {"status": "error", "message": "Google Token Expired (Too Old)"}
            
            email = idinfo["email"]
            name = idinfo.get("name", email.split("@")[0])
            print(f"VERIFIED GOOGLE USER: {email}")
        except Exception as e:
            return {"status": "error", "message": f"Google Verification Failed: {str(e)}"}

        with SessionLocal() as db:
            agent = db.execute(select(Agent).where(Agent.user_email == email)).scalar_one_or_none()
            if not agent:
                api_key = str(uuid.uuid4())
                agent = Agent(
                    user_email=email, name=name, api_key=api_key, owner="player",
                    q=0, r=0, faction_id=1,
                    health=100, max_health=100, energy=100,
                    storage_capacity=500.0,
                    level=1, experience=0
                )
                db.add(agent)
                db.flush()
                db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
                db.add(InventoryItem(agent_id=agent.id, item_type="FIELD_REPAIR_KIT", quantity=2, data={"is_tradable": False}))
                drill_def = PART_DEFINITIONS.get("DRILL_UNIT") or PART_DEFINITIONS.get("DRILL_IRON_BASIC")
                if drill_def:
                    db.add(ChassisPart(agent_id=agent.id, part_type=drill_def["type"], name=drill_def["name"], stats=drill_def["stats"]))
                
                db.commit()
                db.refresh(agent)
                recalculate_agent_stats(db, agent)
                db.commit()

            # Audit Log for Login
            from models import AuditLog
            db.add(AuditLog(agent_id=agent.id, event_type="LOGIN", details={
                "ip": request.client.host,
                "timestamp": time.time()
            }))
            db.commit()

            return {"status": "success", "api_key": agent.api_key, "agent_id": agent.id, "name": agent.name}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Server Error: {str(e)}"}


@router.post("/auth/rotate_key")
def rotate_api_key(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Rotates the agent's API key. Invalidates the old one immediately."""
    # Record revocation of old key
    db.add(APIKeyRevocation(
        agent_id=agent.id,
        revoked_key=agent.api_key,
        reason="rotation"
    ))
    
    new_key = str(uuid.uuid4())
    agent.api_key = new_key
    db.commit()
    logger.info(f"Agent {agent.id} rotated their API key.")
    return {"status": "success", "new_api_key": new_key}

@router.post("/auth/guest")
def guest_login(login_data: GuestLoginRequest, db: Session = Depends(get_db)):
    """Bypass Auth for local testing. Creates or returns a guest agent."""
    email = login_data.email
    name = login_data.name

    if not email:
        uid = str(uuid.uuid4())[:8]
        email = f"guest-{uid}@local.test"
        name = name or f"Guest-{uid}"
    else:
        name = name or "Guest-Pilot"

    agent = db.execute(select(Agent).where(Agent.user_email == email)).scalar_one_or_none()
    if not agent:
        agent = Agent(
            user_email=email, name=name, api_key=str(uuid.uuid4()), owner="player",
            q=0, r=0, faction_id=1,
            health=100, max_health=100, energy=100,
            storage_capacity=500.0,
            level=1, experience=0
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        db.add(InventoryItem(agent_id=agent.id, item_type="FIELD_REPAIR_KIT", quantity=2, data={"is_tradable": False}))
        drill_def = PART_DEFINITIONS.get("DRILL_UNIT") or PART_DEFINITIONS.get("DRILL_IRON_BASIC")
        if drill_def:
            db.add(ChassisPart(agent_id=agent.id, part_type=drill_def["type"], name=drill_def["name"], stats=drill_def["stats"]))
        panel_def = PART_DEFINITIONS.get("SCRAP_SOLAR_PANEL")
        if panel_def:
            db.add(ChassisPart(agent_id=agent.id, part_type=panel_def["type"], name=panel_def["name"], stats=panel_def["stats"]))
        db.commit()
        db.refresh(agent)
        recalculate_agent_stats(db, agent)
        db.commit()

    return {"status": "success", "api_key": agent.api_key, "agent_id": agent.id, "name": agent.name}



