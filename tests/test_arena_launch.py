import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from logic.arena_manager import reset_arena_season
from main import app
from models import Agent, ArenaProfile, AuditLog, ChassisPart


client = TestClient(app)


def _create_agent(name_prefix="ArenaAgent"):
    uid = uuid.uuid4().hex[:10]
    agent = Agent(
        user_email=f"{name_prefix.lower()}-{uid}@test.local",
        name=f"{name_prefix}-{uid}",
        api_key=f"arena-key-{uid}",
        owner="player",
        faction_id=1,
        q=0,
        r=0,
        health=100,
        max_health=100,
        energy=100,
        storage_capacity=500.0,
        level=1,
        experience=0,
    )
    with SessionLocal() as db:
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return {"id": agent.id, "name": agent.name, "api_key": agent.api_key}


def _headers(agent):
    return {"X-API-Key": agent["api_key"]}


def test_arena_status_exposes_frontend_compatibility_aliases():
    agent = _create_agent("ArenaSchema")

    response = client.get("/api/arena/status", headers=_headers(agent))

    assert response.status_code == 200
    payload = response.json()
    assert {
        "fighter_name",
        "season_info",
        "elo",
        "wins",
        "losses",
        "stats",
        "is_ready",
        "requirements",
        "gear",
        "arena_gear",
        "logs",
        "arena_logs",
    }.issubset(payload.keys())
    assert payload["gear"] == payload["arena_gear"]
    assert payload["logs"] == payload["arena_logs"]


def test_arena_equip_updates_status_gear_aliases():
    agent = _create_agent("ArenaEquip")
    with SessionLocal() as db:
        part = ChassisPart(
            agent_id=agent["id"],
            part_type="Frame",
            name="Schema Test Frame",
            rarity="STANDARD",
            stats={"max_health": 25, "armor": 3, "upgrade_level": 2},
            durability=88.0,
        )
        db.add(part)
        db.commit()
        part_id = part.id

    equip = client.post("/api/arena/equip", json={"part_id": part_id}, headers=_headers(agent))
    assert equip.status_code == 200

    status = client.get("/api/arena/status", headers=_headers(agent)).json()
    assert len(status["arena_gear"]) == 1
    gear = status["arena_gear"][0]
    assert gear["id"] == part_id
    assert gear["name"] == "Schema Test Frame"
    assert gear["level"] == 2
    assert gear in status["gear"]


def test_arena_season_reset_is_audited_idempotent_and_resets_pit_stats():
    main_agent = _create_agent("ArenaReset")
    with SessionLocal() as db:
        fighter = Agent(
            user_email=f"pit-{uuid.uuid4().hex[:8]}@test.local",
            name=f"{main_agent['name']}-PitFighter",
            api_key=f"pit-key-{uuid.uuid4().hex[:8]}",
            owner=main_agent["name"],
            is_bot=True,
            is_pitfighter=True,
            health=50,
            max_health=50,
            damage=12,
            accuracy=8,
            speed=6,
            armor=4,
            q=0,
            r=0,
        )
        db.add(fighter)
        db.flush()
        db.add(ArenaProfile(agent_id=fighter.id, elo=1400, wins=5, losses=2, daily_opponents=[123]))
        db.add(ChassisPart(agent_id=fighter.id, part_type="Frame", name="Reset Frame", stats={"max_health": 50}))
        db.add(ChassisPart(agent_id=fighter.id, part_type="Actuator", name="Reset Cannon", stats={"damage": 12}))
        db.commit()
        fighter_id = fighter.id

        reset_time = datetime(2099, 1, 4, 0, 5, tzinfo=timezone.utc)
        first = reset_arena_season(db, reset_time=reset_time, force=True, source="pytest")
        second = reset_arena_season(db, reset_time=reset_time, source="pytest")

        db.refresh(fighter)
        profile = fighter.arena_profile
        remaining_parts = db.execute(select(ChassisPart).where(ChassisPart.agent_id == fighter_id)).scalars().all()
        audit = db.execute(
            select(AuditLog).where(AuditLog.event_type == "ARENA_SEASON_RESET").order_by(AuditLog.id.desc())
        ).scalars().first()
        fighter_audit = db.execute(
            select(AuditLog)
            .where(AuditLog.agent_id == fighter_id, AuditLog.event_type == "ARENA_SEASON_RESET_AGENT")
            .order_by(AuditLog.id.desc())
        ).scalars().first()
        reset_state = {
            "max_health": fighter.max_health,
            "health": fighter.health,
            "damage": fighter.damage,
            "elo": profile.elo,
            "wins": profile.wins,
            "losses": profile.losses,
            "daily_opponents": profile.daily_opponents,
            "remaining_parts": len(remaining_parts),
            "season_key": audit.details["season_key"],
            "audit_parts_destroyed": audit.details["parts_destroyed"],
            "fighter_audit_parts_destroyed": fighter_audit.details["parts_destroyed"],
        }

    assert first["status"] == "ok"
    assert first["parts_destroyed"] >= 2
    assert second["status"] == "skipped"
    assert reset_state["remaining_parts"] == 0
    assert reset_state["max_health"] == 0
    assert reset_state["health"] == 0
    assert reset_state["damage"] == 0
    assert reset_state["elo"] == 1300
    assert reset_state["wins"] == 0
    assert reset_state["losses"] == 0
    assert reset_state["daily_opponents"] == []
    assert reset_state["season_key"] == first["season_key"]
    assert reset_state["audit_parts_destroyed"] >= 2
    assert reset_state["fighter_audit_parts_destroyed"] == 2


def test_admin_arena_reset_endpoint_requires_key_and_returns_result(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "arena-admin-secret")
    monkeypatch.setenv("ENVIRONMENT", "production")
    agent = _create_agent("ArenaAdmin")

    with SessionLocal() as db:
        fighter = Agent(
            user_email=f"admin-pit-{uuid.uuid4().hex[:8]}@test.local",
            name=f"{agent['name']}-PitFighter",
            api_key=f"admin-pit-key-{uuid.uuid4().hex[:8]}",
            owner=agent["name"],
            is_bot=True,
            is_pitfighter=True,
            health=10,
            max_health=10,
            damage=5,
            q=0,
            r=0,
        )
        db.add(fighter)
        db.flush()
        db.add(ArenaProfile(agent_id=fighter.id, elo=1250, wins=1, losses=1))
        db.add(ChassisPart(agent_id=fighter.id, part_type="Actuator", name="Admin Reset Drill", stats={"damage": 5}))
        db.commit()

    denied = client.post("/api/admin/arena/reset_season", json={"force": True}, headers={"X-Admin-Key": "wrong"})
    allowed = client.post(
        "/api/admin/arena/reset_season",
        json={"force": True},
        headers={"X-Admin-Key": "arena-admin-secret"},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["status"] == "ok"
    assert payload["source"] == "admin"
    assert payload["parts_destroyed"] >= 1
