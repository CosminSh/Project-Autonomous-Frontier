import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import STATION_CACHE, SessionLocal
from game_helpers import trigger_mayday_webhook
from main import app
from models import Agent, AuditLog, DailyMission, InventoryItem, PlayerContract, StorageItem


client = TestClient(app)


def _create_agent(name_prefix="Agent", credits=0, q=0, r=0):
    uid = uuid.uuid4().hex[:10]
    agent = Agent(
        user_email=f"{name_prefix.lower()}-{uid}@test.local",
        name=f"{name_prefix}-{uid}",
        api_key=f"test-key-{uid}",
        owner="player",
        q=q,
        r=r,
        faction_id=1,
        health=100,
        max_health=100,
        energy=100,
        storage_capacity=500.0,
        level=1,
        experience=0,
    )
    with SessionLocal() as db:
        db.add(agent)
        db.flush()
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=credits))
        db.commit()
        db.refresh(agent)
        return {"id": agent.id, "name": agent.name, "api_key": agent.api_key}


def _headers(agent):
    return {"X-API-Key": agent["api_key"]}


def _credits(agent_id):
    with SessionLocal() as db:
        item = db.execute(
            select(InventoryItem).where(
                InventoryItem.agent_id == agent_id,
                InventoryItem.item_type == "CREDITS",
            )
        ).scalars().first()
        return item.quantity if item else 0


def test_guest_login_disabled_by_default_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ALLOW_GUEST_LOGIN", raising=False)

    response = client.post("/auth/guest", json={})

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_guest_login_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_GUEST_LOGIN", "true")

    response = client.post("/auth/guest", json={"name": f"Guest-{uuid.uuid4().hex[:8]}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["api_key"]


def test_webhook_settings_reject_private_and_local_targets():
    agent = _create_agent("WebhookTester")

    bad_urls = [
        "http://example.com/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://10.0.0.5/hook",
        "https://example.com:8443/hook",
        "https://user:pass@example.com/hook",
    ]

    for url in bad_urls:
        response = client.post(
            "/api/settings/webhook",
            json={"webhook_url": url},
            headers=_headers(agent),
        )
        assert response.status_code == 400, url


def test_webhook_settings_accept_https_public_host():
    agent = _create_agent("WebhookOk")

    response = client.post(
        "/api/settings/webhook",
        json={"webhook_url": "https://discord.com/api/webhooks/test/token"},
        headers=_headers(agent),
    )

    assert response.status_code == 200
    assert response.json()["webhook_url"] == "https://discord.com/api/webhooks/test/token"
    assert response.json()["webhook_status"] is None

    status = client.get("/api/settings/webhook/status", headers=_headers(agent))
    assert status.status_code == 200
    assert status.json() == {
        "configured": True,
        "webhook_url": "https://discord.com/api/webhooks/test/token",
        "webhook_status": None,
    }


def test_contract_post_cancel_and_normalized_schema():
    STATION_CACHE[:] = [{"station_type": "MARKET", "q": 0, "r": 0}]
    issuer = _create_agent("Issuer", credits=500)

    response = client.post(
        "/api/contracts/post",
        json={
            "contract_type": "DELIVERY",
            "item_type": "IRON_ORE",
            "quantity": 3,
            "reward_credits": 125,
            "target_station_q": 0,
            "target_station_r": 0,
        },
        headers=_headers(issuer),
    )

    assert response.status_code == 200
    contract_id = response.json()["contract_id"]
    assert _credits(issuer["id"]) == 375

    available = client.get("/api/contracts/available").json()
    contract = next(c for c in available if c["id"] == contract_id)
    assert contract["type"] == "DELIVERY"
    assert contract["contract_type"] == "DELIVERY"
    assert contract["item"] == "IRON_ORE"
    assert contract["item_type"] == "IRON_ORE"
    assert contract["quantity"] == 3
    assert contract["reward"] == 125
    assert contract["reward_credits"] == 125
    assert contract["target"] == {"q": 0, "r": 0}
    assert contract["target_station_q"] == 0
    assert contract["target_station_r"] == 0

    cancel = client.post(f"/api/contracts/cancel/{contract_id}", headers=_headers(issuer))
    assert cancel.status_code == 200
    assert _credits(issuer["id"]) == 500


def test_contract_rejects_invalid_station_and_unsupported_type():
    STATION_CACHE[:] = [{"station_type": "MARKET", "q": 0, "r": 0}]
    issuer = _create_agent("BadContract", credits=500)
    payload = {
        "contract_type": "DELIVERY",
        "item_type": "IRON_ORE",
        "quantity": 3,
        "reward_credits": 125,
        "target_station_q": 99,
        "target_station_r": 99,
    }

    response = client.post("/api/contracts/post", json=payload, headers=_headers(issuer))
    assert response.status_code == 400
    assert "station" in response.json()["detail"].lower()

    payload["contract_type"] = "PROCUREMENT"
    payload["target_station_q"] = 0
    payload["target_station_r"] = 0
    response = client.post("/api/contracts/post", json=payload, headers=_headers(issuer))
    assert response.status_code == 400
    assert "delivery" in response.json()["detail"].lower()


def test_expired_open_contract_refunds_escrow():
    STATION_CACHE[:] = [{"station_type": "MARKET", "q": 0, "r": 0}]
    issuer = _create_agent("ExpiredIssuer", credits=400)

    with SessionLocal() as db:
        credits = db.execute(
            select(InventoryItem).where(
                InventoryItem.agent_id == issuer["id"],
                InventoryItem.item_type == "CREDITS",
            )
        ).scalars().one()
        credits.quantity -= 175
        contract = PlayerContract(
            issuer_id=issuer["id"],
            issuer_name=issuer["name"],
            contract_type="DELIVERY",
            requirements={"item": "IRON_ORE", "qty": 2},
            reward_credits=175,
            target_station_q=0,
            target_station_r=0,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status="OPEN",
        )
        db.add(contract)
        db.commit()
        contract_id = contract.id

    response = client.get("/api/contracts/available")

    assert response.status_code == 200
    assert all(c["id"] != contract_id for c in response.json())
    assert _credits(issuer["id"]) == 400

    with SessionLocal() as db:
        contract = db.get(PlayerContract, contract_id)
        assert contract.status == "EXPIRED"


def test_claimed_contract_fulfillment_moves_items_and_pays_reward():
    STATION_CACHE[:] = [{"station_type": "MARKET", "q": 0, "r": 0}]
    issuer = _create_agent("ContractIssuer", credits=250)
    courier = _create_agent("Courier", credits=0, q=0, r=0)

    post = client.post(
        "/api/contracts/post",
        json={
            "contract_type": "DELIVERY",
            "item_type": "IRON_ORE",
            "quantity": 4,
            "reward_credits": 200,
            "target_station_q": 0,
            "target_station_r": 0,
        },
        headers=_headers(issuer),
    )
    assert post.status_code == 200
    contract_id = post.json()["contract_id"]

    claim = client.post(f"/api/contracts/claim/{contract_id}", headers=_headers(courier))
    assert claim.status_code == 200

    with SessionLocal() as db:
        db.add(InventoryItem(agent_id=courier["id"], item_type="IRON_ORE", quantity=4))
        db.commit()

    fulfill = client.post(f"/api/contracts/fulfill/{contract_id}", headers=_headers(courier))

    assert fulfill.status_code == 200
    assert _credits(courier["id"]) == 200

    with SessionLocal() as db:
        delivered = db.execute(
            select(StorageItem).where(
                StorageItem.agent_id == issuer["id"],
                StorageItem.item_type == "IRON_ORE",
            )
        ).scalars().one()
        contract = db.get(PlayerContract, contract_id)
        assert delivered.quantity == 4
        assert contract.status == "COMPLETED"


def test_mission_response_keeps_frontend_compatibility_aliases():
    agent = _create_agent("MissionAgent")
    with SessionLocal() as db:
        mission = DailyMission(
            mission_type="TURN_IN",
            target_amount=7,
            reward_credits=321,
            reward_xp=55,
            item_type="IRON_ORE",
            min_level=1,
            max_level=99,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(mission)
        db.commit()
        mission_id = mission.id

    response = client.get("/api/missions", headers=_headers(agent))

    assert response.status_code == 200
    missions = response.json()
    mission = next(m for m in missions if m["id"] == mission_id)
    assert mission["type"] == "TURN_IN"
    assert mission["target"] == 7
    assert mission["target_amount"] == 7
    assert mission["required_quantity"] == 7
    assert mission["progress"] == 0
    assert mission["current_quantity"] == 0
    assert mission["is_completed"] is False
    assert mission["is_turned_in"] is False
    assert mission["reward_credits"] == 321
    assert mission["item_type"] == "IRON_ORE"
    assert mission["title"] == "TURN IN"
    assert "description" in mission


def test_wiki_routes_keep_manual_and_command_shapes():
    data_response = client.get("/api/wiki/data")
    manual_response = client.get("/api/wiki/manual")
    commands_response = client.get("/api/wiki/commands")

    assert data_response.status_code == 200
    assert manual_response.status_code == 200
    assert commands_response.status_code == 200

    data = data_response.json()
    manual = manual_response.json()
    commands = commands_response.json()

    assert isinstance(data["manual"], list)
    assert isinstance(data["commands"], list)
    assert manual == data["manual"]
    assert commands == data["commands"]
    assert {"type", "desc"}.issubset(commands[0].keys())


async def test_mayday_webhook_posts_expected_payload(monkeypatch):
    posts = []

    class FakeResponse:
        status = 204

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, timeout=None):
            posts.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "aiohttp", SimpleNamespace(ClientSession=FakeSession))

    agent = Agent(
        id=42,
        name="Webhook Pilot",
        q=3,
        r=4,
        health=12,
        max_health=100,
        webhook_url="https://discord.com/api/webhooks/test/token",
    )

    result = await trigger_mayday_webhook(agent, "LOW_HEALTH", {"source": "test"})

    assert len(posts) == 1
    assert result == {"status": "success", "reason": "LOW_HEALTH", "http_status": 204}
    assert posts[0]["url"] == "https://discord.com/api/webhooks/test/token"
    assert posts[0]["timeout"] == 5
    payload = posts[0]["json"]
    assert payload["content"] == "🚨 **MAYDAY ALERT: Webhook Pilot**"
    assert payload["embeds"][0]["title"] == "Critical Event: LOW_HEALTH"
    assert payload["embeds"][0]["fields"] == [
        {"name": "Location", "value": "Hex (3, 4)", "inline": True},
        {"name": "Health", "value": "12/100", "inline": True},
        {"name": "Details", "value": "{'source': 'test'}", "inline": False},
    ]
    assert payload["embeds"][0]["timestamp"]

    with SessionLocal() as db:
        delivery = db.execute(
            select(AuditLog)
            .where(AuditLog.agent_id == 42, AuditLog.event_type == "WEBHOOK_DELIVERY")
            .order_by(AuditLog.id.desc())
        ).scalars().first()
        assert delivery.details["status"] == "success"
        assert delivery.details["reason"] == "LOW_HEALTH"
        assert delivery.details["http_status"] == 204


async def test_mayday_webhook_records_failed_http_status(monkeypatch):
    class FakeResponse:
        status = 429

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, timeout=None):
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "aiohttp", SimpleNamespace(ClientSession=FakeSession))

    agent = Agent(
        id=44,
        name="Rate Limited Webhook Pilot",
        q=3,
        r=4,
        health=12,
        max_health=100,
        webhook_url="https://discord.com/api/webhooks/test/token",
    )

    result = await trigger_mayday_webhook(agent, "LOW_HEALTH", {"source": "test"})

    assert result == {"status": "failed", "reason": "LOW_HEALTH", "http_status": 429}
    with SessionLocal() as db:
        delivery = db.execute(
            select(AuditLog)
            .where(AuditLog.agent_id == 44, AuditLog.event_type == "WEBHOOK_DELIVERY")
            .order_by(AuditLog.id.desc())
        ).scalars().first()
        assert delivery.details["status"] == "failed"
        assert delivery.details["http_status"] == 429


async def test_mayday_webhook_skips_unsafe_stored_url(monkeypatch):
    posts = []

    class FakeSession:
        def post(self, url, json=None, timeout=None):
            posts.append(url)
            raise AssertionError("unsafe webhook should not be posted")

    monkeypatch.setitem(sys.modules, "aiohttp", SimpleNamespace(ClientSession=FakeSession))

    agent = Agent(
        id=43,
        name="Unsafe Webhook Pilot",
        q=0,
        r=0,
        health=1,
        max_health=100,
        webhook_url="https://127.0.0.1/hook",
    )

    result = await trigger_mayday_webhook(agent, "LOW_HEALTH", {})

    assert result["status"] == "skipped"
    assert result["reason"] == "UNSAFE_URL"
    assert posts == []

    with SessionLocal() as db:
        delivery = db.execute(
            select(AuditLog)
            .where(AuditLog.agent_id == 43, AuditLog.event_type == "WEBHOOK_DELIVERY")
            .order_by(AuditLog.id.desc())
        ).scalars().first()
        assert delivery.details["status"] == "skipped"
        assert delivery.details["reason"] == "LOW_HEALTH"
        assert "Private network" in delivery.details["error"]
