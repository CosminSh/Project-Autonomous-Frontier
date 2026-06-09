import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from main import app
from models import Agent, AuditLog, InventoryItem


client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Key": "moderation-secret"}


def _create_agent(name_prefix="ModerationAgent", credits=0):
    uid = uuid.uuid4().hex[:10]
    agent = Agent(
        user_email=f"{name_prefix.lower()}-{uid}@test.local",
        name=f"{name_prefix}-{uid}",
        api_key=f"moderation-key-{uid}",
        owner="player",
        faction_id=1,
        q=7,
        r=9,
        health=20,
        max_health=100,
        energy=12,
        storage_capacity=500.0,
        level=1,
        experience=0,
    )
    with SessionLocal() as db:
        db.add(agent)
        db.flush()
        if credits:
            db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=credits))
        db.commit()
        db.refresh(agent)
        return {"id": agent.id, "name": agent.name, "api_key": agent.api_key}


def _auth_headers(agent):
    return {"X-API-Key": agent["api_key"]}


def test_admin_agent_lookup_rescue_credit_adjustment_and_audit(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "moderation-secret")
    agent = _create_agent("AdminLookup", credits=25)

    lookup = client.get(f"/api/admin/agents?query={agent['name']}", headers=ADMIN_HEADERS)
    assert lookup.status_code == 200
    assert any(a["id"] == agent["id"] for a in lookup.json()["agents"])

    rescue = client.post(
        f"/api/admin/agents/{agent['id']}/rescue",
        json={"q": 0, "r": 0, "heal": True, "reason": "support rescue test"},
        headers=ADMIN_HEADERS,
    )
    assert rescue.status_code == 200
    rescued_agent = rescue.json()["agent"]
    assert rescued_agent["q"] == 0
    assert rescued_agent["r"] == 0

    credits = client.post(
        f"/api/admin/agents/{agent['id']}/credits",
        json={"delta": 75, "reason": "support credit correction"},
        headers=ADMIN_HEADERS,
    )
    assert credits.status_code == 200
    assert credits.json()["old_balance"] == 25
    assert credits.json()["new_balance"] == 100

    audit = client.get(f"/api/admin/audit?agent_id={agent['id']}&event_type=ADMIN_CREDIT_ADJUST", headers=ADMIN_HEADERS)
    assert audit.status_code == 200
    logs = audit.json()["logs"]
    assert len(logs) >= 1
    assert logs[0]["details"]["new_balance"] == 100


def test_admin_ban_blocks_api_key_until_unbanned(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "moderation-secret")
    agent = _create_agent("AdminBan")

    banned = client.post(
        f"/api/admin/agents/{agent['id']}/ban",
        json={"is_banned": True, "reason": "automated ban test"},
        headers=ADMIN_HEADERS,
    )
    assert banned.status_code == 200
    assert banned.json()["agent"]["is_banned"] is True

    blocked = client.get("/api/my_agent", headers=_auth_headers(agent))
    assert blocked.status_code == 403
    assert "banned" in blocked.json()["detail"].lower()

    unbanned = client.post(
        f"/api/admin/agents/{agent['id']}/ban",
        json={"is_banned": False, "reason": "automated unban test"},
        headers=ADMIN_HEADERS,
    )
    assert unbanned.status_code == 200
    assert unbanned.json()["agent"]["is_banned"] is False

    allowed = client.get("/api/my_agent", headers=_auth_headers(agent))
    assert allowed.status_code == 200

    with SessionLocal() as db:
        events = db.execute(
            select(AuditLog.event_type).where(AuditLog.agent_id == agent["id"]).order_by(AuditLog.id.desc())
        ).all()
    assert "ADMIN_AGENT_BANNED" in [event[0] for event in events]
    assert "ADMIN_AGENT_UNBANNED" in [event[0] for event in events]


def test_admin_mute_blocks_chat_until_unmuted(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "moderation-secret")
    agent = _create_agent("AdminMute")

    muted = client.post(
        f"/api/admin/agents/{agent['id']}/mute",
        json={"minutes": 30, "reason": "automated mute test"},
        headers=ADMIN_HEADERS,
    )
    assert muted.status_code == 200
    assert muted.json()["agent"]["muted_until"]

    blocked = client.post("/api/chat", json={"channel": "GLOBAL", "message": "hello"}, headers=_auth_headers(agent))
    assert blocked.status_code == 403
    assert "muted" in blocked.json()["detail"].lower()

    unmuted = client.post(
        f"/api/admin/agents/{agent['id']}/mute",
        json={"minutes": 0, "reason": "automated unmute test"},
        headers=ADMIN_HEADERS,
    )
    assert unmuted.status_code == 200
    assert unmuted.json()["agent"]["muted_until"] is None

    allowed = client.post("/api/chat", json={"channel": "GLOBAL", "message": "hello"}, headers=_auth_headers(agent))
    assert allowed.status_code == 200


def test_admin_metrics_exposes_launch_observability(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "moderation-secret")

    denied = client.get("/api/admin/metrics", headers={"X-Admin-Key": "wrong"})
    allowed = client.get("/api/admin/metrics", headers=ADMIN_HEADERS)

    assert denied.status_code == 403
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["status"] == "ok"
    assert {"tick", "phase", "heartbeat", "simulation", "http", "websocket", "database", "process"}.issubset(payload.keys())
    assert "active_connections" in payload["websocket"]
    assert "pool" in payload["database"]
    assert "memory_rss_mb" in payload["process"]
    assert "failed_intents_last_hour" in payload["simulation"]
    assert "recent_slow_requests" in payload["http"]
