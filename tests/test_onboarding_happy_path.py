import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import STATION_CACHE, SessionLocal
from logic.intent_processor import IntentProcessor
from main import app
from models import Agent, AuctionOrder, ChassisPart, Intent, InventoryItem, WorldHex


client = TestClient(app)


class DummyManager:
    async def broadcast(self, _message):
        return None


def _headers(api_key):
    return {"X-API-Key": api_key}


def _intent(action_type, data=None, tick=1):
    return Intent(action_type=action_type, data=data or {}, tick_index=tick)


async def _process(db, agent, action_type, data=None, tick=1):
    processor = IntentProcessor(DummyManager())
    await processor.process_intent(db, agent, _intent(action_type, data, tick), tick)
    db.commit()
    db.expire_all()
    db.refresh(agent)


def _item_qty(agent, item_type):
    return sum(item.quantity for item in agent.inventory if item.item_type == item_type)


def _set_item(db, agent_id, item_type, quantity):
    item = db.execute(
        select(InventoryItem).where(
            InventoryItem.agent_id == agent_id,
            InventoryItem.item_type == item_type,
        )
    ).scalars().first()
    if item:
        item.quantity = quantity
    else:
        db.add(InventoryItem(agent_id=agent_id, item_type=item_type, quantity=quantity))


def _world_hex(q, r, **kwargs):
    defaults = {
        "q": q,
        "r": r,
        "terrain_type": "VOID",
        "resource_type": None,
        "resource_density": 0.0,
        "resource_quantity": 0,
        "is_station": False,
        "station_type": None,
    }
    defaults.update(kwargs)
    return WorldHex(**defaults)


async def test_new_player_onboarding_happy_path_guest_to_repaired_market_ready_agent(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    unique = uuid.uuid4().hex[:8]
    name = f"Onboarding-{unique}"

    login = client.post("/auth/guest", json={"name": name})
    assert login.status_code == 200
    payload = login.json()
    api_key = payload["api_key"]
    agent_id = payload["agent_id"]

    base_q = 9000 + int(unique[:4], 16)
    mine_q, mine_r = base_q, 0
    market_q, market_r = base_q + 1, 0
    smelter_q, smelter_r = base_q + 2, 0
    crafter_q, crafter_r = base_q + 3, 0
    repair_q, repair_r = base_q + 4, 0

    STATION_CACHE[:] = [
        {"station_type": "MARKET", "q": market_q, "r": market_r},
        {"station_type": "SMELTER", "q": smelter_q, "r": smelter_r},
        {"station_type": "CRAFTER", "q": crafter_q, "r": crafter_r},
        {"station_type": "REPAIR", "q": repair_q, "r": repair_r},
    ]

    with SessionLocal() as db:
        db.add_all(
            [
                _world_hex(
                    mine_q,
                    mine_r,
                    terrain_type="ASTEROID",
                    resource_type="IRON_ORE",
                    resource_density=1.0,
                    resource_quantity=100,
                ),
                _world_hex(market_q, market_r, is_station=True, station_type="MARKET"),
                _world_hex(smelter_q, smelter_r, is_station=True, station_type="SMELTER"),
                _world_hex(crafter_q, crafter_r, is_station=True, station_type="CRAFTER"),
                _world_hex(repair_q, repair_r, is_station=True, station_type="REPAIR"),
            ]
        )
        db.commit()

        agent = db.get(Agent, agent_id)
        assert any(part.part_type == "Actuator" and "Drill" in part.name for part in agent.parts)
        assert _item_qty(agent, "FIELD_REPAIR_KIT") == 2

        agent.q = mine_q
        agent.r = mine_r
        agent.energy = 500
        agent.mining_yield = 50
        agent.max_mass = 1000.0
        db.commit()

        await _process(db, agent, "MINE", {}, tick=10)
        assert _item_qty(agent, "IRON_ORE") >= 5

        agent.q = smelter_q
        agent.r = smelter_r
        db.commit()
        await _process(db, agent, "SMELT", {"ore_type": "IRON_ORE", "quantity": 5}, tick=20)
        assert _item_qty(agent, "IRON_INGOT") >= 1

        agent.q = crafter_q
        agent.r = crafter_r
        db.commit()
        await _process(db, agent, "CRAFT", {"item_type": "SCRAP_FRAME"}, tick=30)
        assert _item_qty(agent, "PART_SCRAP_FRAME") == 1

        await _process(db, agent, "EQUIP", {"item_type": "PART_SCRAP_FRAME"}, tick=40)
        assert any(part.part_type == "Frame" and part.name == "Scrap Frame" for part in agent.parts)

        buyer = Agent(
            user_email=f"onboarding-buyer-{unique}@test.local",
            name=f"OnboardingBuyer-{unique}",
            api_key=f"onboarding-buyer-key-{unique}",
            owner="player",
            q=market_q,
            r=market_r,
            health=100,
            max_health=100,
            energy=100,
        )
        db.add(buyer)
        db.flush()
        db.add(AuctionOrder(owner=f"agent:{buyer.id}", item_type="IRON_ORE", order_type="BUY", quantity=1, price=3))
        _set_item(db, agent.id, "IRON_ORE", max(_item_qty(agent, "IRON_ORE"), 1))
        db.commit()

        starting_credits = _item_qty(agent, "CREDITS")
        await _process(db, agent, "LIST", {"item_type": "IRON_ORE", "quantity": 1, "price": 1}, tick=50)
        assert _item_qty(agent, "CREDITS") >= starting_credits + 3

        db.add(
            AuctionOrder(
                owner=f"agent:{buyer.id}",
                item_type="COPPER_INGOT",
                order_type="SELL",
                quantity=1,
                price=1,
            )
        )
        _set_item(db, agent.id, "CREDITS", max(_item_qty(agent, "CREDITS"), 10))
        agent.q = market_q
        agent.r = market_r
        db.commit()

        await _process(db, agent, "BUY", {"item_type": "COPPER_INGOT", "quantity": 1, "max_price": 1}, tick=60)
        pickups = client.get("/api/market/pickups", headers=_headers(api_key))
        assert pickups.status_code == 200
        assert any(item["item"] == "COPPER_INGOT" and item["qty"] == 1 for item in pickups.json())

        claim = client.post("/api/market/pickup", headers=_headers(api_key))
        assert claim.status_code == 200
        assert claim.json()["claimed"] == {"COPPER_INGOT": 1}
        db.refresh(agent)
        assert _item_qty(agent, "COPPER_INGOT") == 1

        agent.q = repair_q
        agent.r = repair_r
        agent.max_health = max(agent.max_health, 100)
        agent.health = agent.max_health - 12
        _set_item(db, agent.id, "CREDITS", max(_item_qty(agent, "CREDITS"), 20))
        _set_item(db, agent.id, "IRON_INGOT", max(_item_qty(agent, "IRON_INGOT"), 5))
        damaged_health = agent.health
        db.commit()

        await _process(db, agent, "REPAIR", {"amount": "MAX"}, tick=70)
        assert agent.health > damaged_health
        assert agent.health == agent.max_health

    summary = client.get("/api/my_agent", headers=_headers(api_key))
    assert summary.status_code == 200
    assert summary.json()["name"] == name
