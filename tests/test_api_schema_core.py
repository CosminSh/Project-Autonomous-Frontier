import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from main import app
from models import Agent, AuctionOrder, Corporation, InventoryItem, MarketPickup, StorageItem


client = TestClient(app)


def _create_agent(name_prefix="SchemaAgent", credits=0):
    uid = uuid.uuid4().hex[:10]
    agent = Agent(
        user_email=f"{name_prefix.lower()}-{uid}@test.local",
        name=f"{name_prefix}-{uid}",
        api_key=f"schema-key-{uid}",
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
        db.flush()
        db.add(InventoryItem(agent_id=agent.id, item_type="CREDITS", quantity=credits))
        db.commit()
        db.refresh(agent)
        return {"id": agent.id, "name": agent.name, "api_key": agent.api_key}


def _headers(agent):
    return {"X-API-Key": agent["api_key"]}


def test_market_routes_keep_frontend_field_names():
    agent = _create_agent("MarketSchema")
    item_type = f"SCHEMA_ORE_{uuid.uuid4().hex[:8].upper()}"
    pickup_type = f"SCHEMA_INGOT_{uuid.uuid4().hex[:8].upper()}"
    with SessionLocal() as db:
        order = AuctionOrder(
            owner=agent["name"],
            item_type=item_type,
            quantity=12,
            price=7.5,
            order_type="SELL",
        )
        pickup = MarketPickup(agent_id=agent["id"], item_type=pickup_type, quantity=3)
        db.add_all([order, pickup])
        db.commit()
        order_id = order.id
        pickup_id = pickup.id

    market_response = client.get("/api/market")
    my_orders_response = client.get("/api/market/my_orders", headers=_headers(agent))
    pickups_response = client.get("/api/market/pickups", headers=_headers(agent))
    depth_response = client.get(f"/api/market/depth?item_type={item_type}")

    assert market_response.status_code == 200
    market_order = next(o for o in market_response.json() if o["id"] == order_id)
    assert market_order == {"id": order_id, "item": item_type, "qty": 12, "price": 7.5, "type": "SELL"}

    assert my_orders_response.status_code == 200
    assert next(o for o in my_orders_response.json() if o["id"] == order_id)["qty"] == 12

    assert pickups_response.status_code == 200
    assert pickups_response.json() == [{"id": pickup_id, "item": pickup_type, "qty": 3}]

    assert depth_response.status_code == 200
    assert depth_response.json() == {
        "item": item_type,
        "buy_orders": [],
        "sell_orders": [{"price": 7.5, "qty": 12}],
    }


def test_my_agent_and_storage_info_keep_frontend_field_names():
    agent = _create_agent("AgentSchema", credits=50)
    with SessionLocal() as db:
        db.add(InventoryItem(agent_id=agent["id"], item_type="IRON_ORE", quantity=4))
        db.add(StorageItem(agent_id=agent["id"], item_type="IRON_INGOT", quantity=2))
        db.commit()

    agent_response = client.get("/api/my_agent", headers=_headers(agent))
    storage_response = client.get("/api/storage/info", headers=_headers(agent))

    assert agent_response.status_code == 200
    payload = agent_response.json()
    for key in ["id", "name", "q", "r", "energy", "health", "inventory", "storage", "parts", "webhook_url"]:
        assert key in payload
    assert any(item["type"] == "CREDITS" and item["quantity"] == 50 for item in payload["inventory"])
    assert any(item["type"] == "IRON_ORE" and item["quantity"] == 4 for item in payload["inventory"])
    assert any(item["type"] == "IRON_INGOT" and item["quantity"] == 2 for item in payload["storage"])

    assert storage_response.status_code == 200
    storage = storage_response.json()
    assert {"items", "capacity", "used", "next_upgrade_requirements"}.issubset(storage.keys())
    assert any(item["type"] == "IRON_INGOT" and item["quantity"] == 2 for item in storage["items"])


def test_corp_routes_keep_frontend_field_names():
    agent = _create_agent("CorpSchema", credits=0)
    with SessionLocal() as db:
        corp = Corporation(
            name=f"Schema Corp {uuid.uuid4().hex[:6]}",
            ticker=f"S{uuid.uuid4().hex[:4]}".upper()[:5],
            owner_id=agent["id"],
            faction_id=1,
            credit_vault=1234,
            vault_capacity=5000.0,
            tax_rate=0.1,
            motd="Mine safely.",
            upgrades={"LOGISTICS": 1},
        )
        db.add(corp)
        db.flush()
        db_agent = db.get(Agent, agent["id"])
        db_agent.corporation_id = corp.id
        db_agent.corp_role = "CEO"
        db.commit()
        corp_id = corp.id

    members_response = client.get("/api/corp/members", headers=_headers(agent))
    vault_response = client.get("/api/corp/vault", headers=_headers(agent))
    upgrades_response = client.get("/api/corp/upgrades", headers=_headers(agent))

    assert members_response.status_code == 200
    member = next(m for m in members_response.json() if m["agent_id"] == agent["id"])
    assert {"agent_id", "name", "role", "level", "q", "r"}.issubset(member.keys())
    assert member["role"] == "CEO"

    assert vault_response.status_code == 200
    vault = vault_response.json()
    assert vault["corp_id"] == corp_id
    assert {"name", "ticker", "motd", "join_policy", "tax_rate", "credit_balance", "vault_capacity", "upgrades", "storage"}.issubset(vault.keys())
    assert vault["credit_balance"] == 1234

    assert upgrades_response.status_code == 200
    assert {"upgrades", "definitions"}.issubset(upgrades_response.json().keys())
