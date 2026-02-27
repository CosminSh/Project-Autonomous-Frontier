"""
routes_auth.py — Authentication routes: Google login, guest login, global stats.
"""
import logging
import random
import uuid

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from models import Agent, InventoryItem, ChassisPart, AuctionOrder
from database import get_db, SessionLocal
from config import PART_DEFINITIONS
from game_helpers import recalculate_agent_stats

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

logger = logging.getLogger("heartbeat")
router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "419308259695-sj14gj8q7ml5o9uao2j59pgkp1vvthh0.apps.googleusercontent.com")


@router.post("/auth/login")
async def login(request: Request):
    print("\n--- AUTH LOGIN REQUEST RECEIVED ---")
    try:
        data = await request.json()
        token = data.get("token")
        if not token:
            return {"status": "error", "message": "Missing token"}

        try:
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
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
                    q=0, r=0, faction_id=random.randint(1, 3),
                    structure=100, max_structure=100, capacitor=100
                )
                db.add(agent)
                db.flush()
                db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
                drill_def = PART_DEFINITIONS["DRILL_UNIT"]
                db.add(ChassisPart(agent_id=agent.id, part_type=drill_def["type"], name=drill_def["name"], stats=drill_def["stats"]))
                db.commit()
                db.refresh(agent)
                recalculate_agent_stats(db, agent)
                db.commit()

            return {"status": "success", "api_key": agent.api_key, "agent_id": agent.id, "name": agent.name}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Server Error: {str(e)}"}


@router.post("/auth/guest")
async def guest_login(request: Request, db: Session = Depends(get_db)):
    """Bypass Auth for local testing. Creates or returns a guest agent."""
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass

    email = data.get("email")
    if not email:
        uid = str(uuid.uuid4())[:8]
        email = f"guest-{uid}@local.test"
        name = data.get("name", f"Guest-{uid}")
    else:
        name = data.get("name", "Guest-Pilot")

    agent = db.execute(select(Agent).where(Agent.user_email == email)).scalar_one_or_none()
    if not agent:
        agent = Agent(
            user_email=email, name=name, api_key=str(uuid.uuid4()), owner="player",
            q=0, r=0, faction_id=random.randint(1, 3),
            structure=100, max_structure=100, capacitor=100
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=1000))
        drill_def = PART_DEFINITIONS["DRILL_UNIT"]
        db.add(ChassisPart(agent_id=agent.id, part_type=drill_def["type"], name=drill_def["name"], stats=drill_def["stats"]))
        panel_def = PART_DEFINITIONS["SCRAP_SOLAR_PANEL"]
        db.add(ChassisPart(agent_id=agent.id, part_type=panel_def["type"], name=panel_def["name"], stats=panel_def["stats"]))
        db.commit()
        db.refresh(agent)
        recalculate_agent_stats(db, agent)
        db.commit()

    return {"status": "success", "api_key": agent.api_key, "agent_id": agent.id, "name": agent.name}


@router.get("/api/global_stats")
async def global_stats(db: Session = Depends(get_db)):
    agent_count = db.execute(select(func.count(Agent.id))).scalar()
    item_count = db.execute(select(func.count(InventoryItem.id))).scalar()
    trade_count = db.execute(select(func.count(AuctionOrder.id))).scalar()
    return {
        "total_agents": agent_count,
        "total_items": item_count,
        "market_listings": trade_count,
        "status": "online"
    }
