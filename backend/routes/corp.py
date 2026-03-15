import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from models import Agent, Corporation, InventoryItem, AuditLog
from database import get_db
from .common import verify_api_key

logger = logging.getLogger("heartbeat")
router = APIRouter()

@router.post("/api/corp/create")
async def create_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    name = data.get("name")
    ticker = data.get("ticker")
    tax_rate = data.get("tax_rate", 0.0)
    
    if not name or not ticker:
        raise HTTPException(status_code=400, detail="Name and ticker are required.")
    
    if current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are already in a corporation.")
        
    # Check 10,000 Credits fee
    credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < 10000:
        raise HTTPException(status_code=400, detail="Creating a corporation requires 10,000 Credits.")
        
    existing = db.execute(select(Corporation).where((Corporation.name == name) | (Corporation.ticker == ticker))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Corporation name or ticker already taken.")
        
    credits.quantity -= 10000
    
    corp = Corporation(
        name=name,
        ticker=ticker,
        owner_id=current_agent.id,
        faction_id=current_agent.faction_id,
        tax_rate=float(tax_rate)
    )
    db.add(corp)
    db.flush()
    
    current_agent.corporation_id = corp.id
    current_agent.corp_role = "CEO"
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_CREATED", details={"corp_id": corp.id, "name": corp.name}))
    db.commit()
    return {"status": "success", "corp_id": corp.id, "message": f"Corporation {corp.name} [{corp.ticker}] established."}

@router.post("/api/corp/promote")
async def promote_member(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    target_id = data.get("agent_id")
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
    
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Only CEO or Officers can promote members.")
        
    target = db.get(Agent, target_id)
    if not target or target.corporation_id != current_agent.corporation_id:
        raise HTTPException(status_code=404, detail="Member not found in your corporation.")
    
    # Hierarchy: Initiate -> Member -> Officer
    if target.corp_role == "INITIATE":
        target.corp_role = "MEMBER"
    elif target.corp_role == "MEMBER":
        if current_agent.corp_role != "CEO":
             raise HTTPException(status_code=403, detail="Only the CEO can promote to Officer.")
        target.corp_role = "OFFICER"
    else:
        raise HTTPException(status_code=400, detail="Target is already at max rank (Officer) or is CEO.")
        
    db.commit()
    return {"status": "success", "new_role": target.corp_role}

@router.post("/api/corp/demote")
async def demote_member(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    target_id = data.get("agent_id")
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
    
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
        
    target = db.get(Agent, target_id)
    if not target or target.corporation_id != current_agent.corporation_id:
        raise HTTPException(status_code=404, detail="Member not found.")
        
    if target.corp_role == "CEO":
        raise HTTPException(status_code=400, detail="Cannot demote the CEO.")
        
    if current_agent.corp_role == "OFFICER" and target.corp_role == "OFFICER":
        raise HTTPException(status_code=403, detail="Officers cannot demote other Officers.")
        
    # Hierarchy: Officer -> Member -> Initiate
    if target.corp_role == "OFFICER":
        target.corp_role = "MEMBER"
    elif target.corp_role == "MEMBER":
        target.corp_role = "INITIATE"
    else:
        raise HTTPException(status_code=400, detail="Already at lowest rank.")
        
    db.commit()
    return {"status": "success", "new_role": target.corp_role}

@router.post("/api/corp/motd")
async def update_motd(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    motd = data.get("motd")
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Only CEO or Officers can update MOTD.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    corp.motd = motd
    db.commit()
    return {"status": "success", "motd": motd}

from models import Agent, Corporation, InventoryItem, AuditLog, CorpInvite

@router.post("/api/corp/join")
async def join_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    ticker = data.get("ticker")
    
    if current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Already in a corporation.")
        
    corp = db.execute(select(Corporation).where(Corporation.ticker == ticker)).scalar_one_or_none()
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    # Check policy
    if corp.join_policy == "INVITE_ONLY":
        # Must have an accepted INVITE
        invite = db.execute(select(CorpInvite).where(
            CorpInvite.corporation_id == corp.id,
            CorpInvite.agent_id == current_agent.id,
            CorpInvite.invite_type == "INVITE",
            CorpInvite.status == "ACCEPTED"
        )).scalars().first()
        
        if not invite:
             raise HTTPException(status_code=403, detail="This corporation is invite-only. You must first accept an invitation.")
    
    elif corp.join_policy == "CLOSED":
        raise HTTPException(status_code=403, detail="This corporation is currently closed to new members.")

    current_agent.corporation_id = corp.id
    current_agent.corp_role = "INITIATE" # New members start as Initiate
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_JOINED", details={"corp_id": corp.id}))
    db.commit()
    return {"status": "success", "message": f"Welcome to {corp.name}."}

@router.post("/api/corp/leave")
async def leave_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if corp and corp.owner_id == current_agent.id:
        raise HTTPException(status_code=400, detail="CEO cannot leave. Transfer ownership or disband corp first.")
        
    current_agent.corporation_id = None
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_LEFT", details={"corp_id": corp.id if corp else None}))
    db.commit()
    return {"status": "success", "message": "Left corporation."}

@router.post("/api/corp/deposit")
async def corp_deposit(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    amount = data.get("amount", 0)
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0.")
        
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if not credits or credits.quantity < amount:
        raise HTTPException(status_code=400, detail="Insufficient credits.")
        
    credits.quantity -= amount
    corp.credit_vault += amount
    
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_DEPOSIT", details={"corp_id": corp.id, "amount": amount}))
    db.commit()
    return {"status": "success", "message": f"Deposited {amount} CR into vault."}

@router.post("/api/corp/invite")
async def invite_agent(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    target_id = data.get("agent_id")
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Insufficient credits to invite.") # Actually it should be permission
        
    target = db.get(Agent, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Agent not found.")
        
    if target.corporation_id:
        raise HTTPException(status_code=400, detail="Agent is already in a corporation.")
        
    invite = CorpInvite(
        corporation_id=current_agent.corporation_id,
        agent_id=target.id,
        invite_type="INVITE"
    )
    db.add(invite)
    db.commit()
    return {"status": "success", "invite_id": invite.id}

@router.post("/api/corp/apply")
async def apply_to_corp(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    ticker = data.get("ticker")
    
    if current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Already in a corporation.")
        
    corp = db.execute(select(Corporation).where(Corporation.ticker == ticker)).scalar_one_or_none()
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    invite = CorpInvite(
        corporation_id=corp.id,
        agent_id=current_agent.id,
        invite_type="APPLICATION"
    )
    db.add(invite)
    db.commit()
    return {"status": "success", "invite_id": invite.id}

@router.get("/api/corp/applications")
async def get_corp_applications(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Not in a corporation.")
        
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
        
    apps = db.execute(select(CorpInvite).where(
        CorpInvite.corporation_id == current_agent.corporation_id,
        CorpInvite.invite_type == "APPLICATION",
        CorpInvite.status == "PENDING"
    )).scalars().all()
    
    return [
        {"id": a.id, "agent_id": a.agent_id, "agent_name": a.agent.name, "created_at": a.created_at}
        for a in apps
    ]

@router.post("/api/corp/application/respond")
async def respond_to_application(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    invite_id = data.get("invite_id")
    status = data.get("status") # ACCEPTED, REJECTED
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Not in a corp.")
        
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
        
    invite = db.get(CorpInvite, invite_id)
    if not invite or invite.corporation_id != current_agent.corporation_id:
        raise HTTPException(status_code=404, detail="Application not found.")
        
    invite.status = status
    if status == "ACCEPTED":
        # Note: join logic will handle the actual joining once the agent calls /api/corp/join
        # OR we can just join them here if they are already applying.
        # Let's keep it consistent: ACCEPTED means they can now JOIN.
        pass
    
    db.commit()
    return {"status": "success"}

@router.get("/api/my_invites")
async def get_my_invites(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    invites = db.execute(select(CorpInvite).where(
        CorpInvite.agent_id == current_agent.id,
        CorpInvite.invite_type == "INVITE",
        CorpInvite.status == "PENDING"
    )).scalars().all()
    
    return [
        {"id": i.id, "corp_name": i.corporation.name, "corp_ticker": i.corporation.ticker, "created_at": i.created_at}
        for i in invites
    ]

@router.post("/api/invite/respond")
async def respond_to_invite(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    invite_id = data.get("invite_id")
    status = data.get("status") # ACCEPTED, REJECTED
    
    invite = db.get(CorpInvite, invite_id)
    if not invite or invite.agent_id != current_agent.id:
        raise HTTPException(status_code=404, detail="Invite not found.")
        
    invite.status = status
    db.commit()
    return {"status": "success"}

@router.post("/api/corp/withdraw")
async def corp_withdraw(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    amount = data.get("amount", 0)
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0.")
        
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    if corp.credit_vault < amount:
        raise HTTPException(status_code=400, detail="Insufficient credits in vault.")
        
    # Permission check: CEO or Officer
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Only CEO or Officers can withdraw credits.")
        
    corp.credit_vault -= amount
    credits = next((i for i in current_agent.inventory if i.item_type == "CREDITS"), None)
    if credits: credits.quantity += amount
    else: db.add(InventoryItem(agent_id=current_agent.id, item_type="CREDITS", quantity=amount))
    
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_WITHDRAW", details={"corp_id": corp.id, "amount": amount}))
    db.commit()
    return {"status": "success", "message": f"Withdrew {amount} CR from vault."}

@router.get("/api/corp/members")
async def get_corp_members(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="Not in a corporation.")
        
    members = db.execute(select(Agent).where(Agent.corporation_id == current_agent.corporation_id)).scalars().all()
    
    return [
        {
            "agent_id": m.id,
            "name": m.name,
            "role": m.corp_role,
            "level": m.level,
            "q": m.q,
            "r": m.r
        }
        for m in members
    ]

@router.get("/api/corp/vault")
async def get_corp_vault(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    # Get physical storage
    from models import CorpStorageItem
    storage = db.execute(select(CorpStorageItem).where(CorpStorageItem.corporation_id == corp.id)).scalars().all()
    
    return {
        "corp_id": corp.id,
        "name": corp.name,
        "ticker": corp.ticker,
        "motd": corp.motd,
        "join_policy": corp.join_policy,
        "tax_rate": corp.tax_rate,
        "credit_balance": corp.credit_vault,
        "vault_capacity": corp.vault_capacity,
        "upgrades": corp.upgrades or {},
        "storage": [
            {"item_type": s.item_type, "quantity": s.quantity, "data": s.data}
            for s in storage
        ]
    }

@router.get("/api/corp/upgrades")
async def get_corp_upgrades(current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    from config import CORPORATE_UPGRADES
    
    current_upgrades = corp.upgrades or {}
    
    return {
        "upgrades": current_upgrades,
        "definitions": CORPORATE_UPGRADES
    }

@router.post("/api/corp/upgrade/purchase")
async def purchase_upgrade(request: Request, current_agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    data = await request.json()
    category = data.get("category")
    
    if not current_agent.corporation_id:
        raise HTTPException(status_code=400, detail="You are not in a corporation.")
        
    if current_agent.corp_role not in ["CEO", "OFFICER"]:
        raise HTTPException(status_code=403, detail="Only CEO or Officers can purchase upgrades.")
        
    corp = db.get(Corporation, current_agent.corporation_id)
    if not corp:
        raise HTTPException(status_code=404, detail="Corporation not found.")
        
    from config import CORPORATE_UPGRADES
    if category not in CORPORATE_UPGRADES:
        raise HTTPException(status_code=400, detail="Invalid upgrade category.")
        
    current_upgrades = corp.upgrades or {}
    current_level = current_upgrades.get(category, 0)
    next_level = current_level + 1
    
    upgrade_data = CORPORATE_UPGRADES[category]
    if next_level > len(upgrade_data["levels"]):
        raise HTTPException(status_code=400, detail="This upgrade is already at maximum level.")
        
    cost = upgrade_data["levels"][next_level - 1]["cost"]
    
    if corp.credit_vault < cost:
        raise HTTPException(status_code=400, detail=f"Insufficient credits in corporate vault. Need {cost} CR.")
        
    # Deduct cost and update level
    corp.credit_vault -= cost
    
    # SQLAlchemy JSON mutation tracker workaround
    new_upgrades = dict(corp.upgrades) if corp.upgrades else {}
    new_upgrades[category] = next_level
    corp.upgrades = new_upgrades
    
    db.add(AuditLog(agent_id=current_agent.id, event_type="CORP_UPGRADE_PURCHASE", details={"corp_id": corp.id, "category": category, "level": next_level, "cost": cost}))
    
    # Recalculate stats for all members
    from game_helpers import recalculate_agent_stats
    for member in corp.members:
        recalculate_agent_stats(db, member)
        
    db.commit()
    return {"status": "success", "category": category, "new_level": next_level, "message": f"Purchased {upgrade_data['name']} Level {next_level}."}
