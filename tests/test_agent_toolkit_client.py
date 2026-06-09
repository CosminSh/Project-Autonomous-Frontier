import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / "agent_toolkit"
if str(TOOLKIT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT))

from bot_client import TFClient  # noqa: E402


class FakeResponse:
    def __init__(self, payload=None, ok=True, status_code=200):
        self._payload = payload or {}
        self.ok = ok
        self.status_code = status_code
        self.text = str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def mount(self, *args, **kwargs):
        pass

    def get(self, url):
        self.calls.append(("GET", url, None))
        if url.endswith("/api/contracts/my_contracts"):
            return FakeResponse([{"id": 1, "status": "OPEN"}])
        return FakeResponse({})

    def post(self, url, json=None):
        self.calls.append(("POST", url, json))
        return FakeResponse({"status": "success"})

    def patch(self, url, json=None):
        self.calls.append(("PATCH", url, json))
        return FakeResponse({"status": "success"})

    def delete(self, url):
        self.calls.append(("DELETE", url, None))
        return FakeResponse({"status": "success"})


def _client():
    client = TFClient("test-key", "https://example.test")
    fake = FakeSession()
    fake.headers.update(client.session.headers)
    client.session = fake
    return client, fake


def test_toolkit_contract_methods_match_backend_routes():
    client, session = _client()

    contracts = client.get_my_contracts()
    posted = client.post_contract("IRON_ORE", 5, 100, 0, 0)
    cancelled = client.cancel_contract(1)

    assert contracts == [{"id": 1, "status": "OPEN"}]
    assert posted["status"] == "success"
    assert cancelled["status"] == "success"
    assert session.calls == [
        ("GET", "https://example.test/api/contracts/my_contracts", None),
        ("POST", "https://example.test/api/contracts/post", {
            "contract_type": "DELIVERY",
            "item_type": "IRON_ORE",
            "quantity": 5,
            "reward_credits": 100,
            "target_station_q": 0,
            "target_station_r": 0,
        }),
        ("POST", "https://example.test/api/contracts/cancel/1", {}),
    ]


def test_toolkit_corp_methods_match_backend_routes():
    client, session = _client()

    client.get_corp_members()
    client.get_corp_vault()
    client.get_corp_upgrades()
    client.create_corp("Deep Space Mining", "DSM", 0.05)

    assert session.calls == [
        ("GET", "https://example.test/api/corp/members", None),
        ("GET", "https://example.test/api/corp/vault", None),
        ("GET", "https://example.test/api/corp/upgrades", None),
        ("POST", "https://example.test/api/corp/create", {
            "name": "Deep Space Mining",
            "ticker": "DSM",
            "tax_rate": 0.05,
        }),
    ]


def test_toolkit_market_methods_match_backend_routes():
    client, session = _client()

    client.get_market_depth("IRON_ORE")
    client.place_market_buy("IRON_ORE", 4, 2.5)
    client.place_market_sell("COPPER_ORE", 3, 5.0)
    client.adjust_market_order(7, 4.5)
    client.cancel_market_order(8)
    client.claim_market_pickups()

    assert session.calls == [
        ("GET", "https://example.test/api/market/depth?item_type=IRON_ORE", None),
        ("POST", "https://example.test/api/intent", {
            "action_type": "BUY",
            "data": {
                "item_type": "IRON_ORE",
                "quantity": 4,
                "max_price": 2.5,
            },
        }),
        ("POST", "https://example.test/api/intent", {
            "action_type": "LIST",
            "data": {
                "item_type": "COPPER_ORE",
                "quantity": 3,
                "price": 5.0,
            },
        }),
        ("PATCH", "https://example.test/api/market/orders/7", {"price": 4.5}),
        ("DELETE", "https://example.test/api/market/orders/8", None),
        ("POST", "https://example.test/api/market/pickup", {}),
    ]
