import sys
from sqlalchemy import select, func
from database import SessionLocal
from models import Agent, Intent

with SessionLocal() as db:
    total = db.execute(select(func.count(Agent.id))).scalar()
    ferals = db.execute(select(func.count(Agent.id)).where(Agent.is_feral == True)).scalar()
    pitfighters = db.execute(select(func.count(Agent.id)).where(Agent.is_pitfighter == True)).scalar()
    players = db.execute(select(func.count(Agent.id)).where(Agent.is_bot == False, Agent.is_feral == False)).scalar()
    reg_bots = db.execute(select(func.count(Agent.id)).where(Agent.is_bot == True, Agent.is_pitfighter == False, Agent.is_feral == False)).scalar()
    intents = db.execute(select(func.count(Intent.id))).scalar()
    print(f"Total Agents: {total}")
    print(f"Ferals: {ferals}")
    print(f"PitFighters: {pitfighters}")
    print(f"Players: {players}")
    print(f"Standard Bots: {reg_bots}")
    print(f"Intents in DB: {intents}")
