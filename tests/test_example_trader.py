import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / "agent_toolkit"
if str(TOOLKIT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT))

from example_trader import analyze_item, parse_price_cap  # noqa: E402


class FakeTraderClient:
    def __init__(self):
        self.buy_calls = []

    def get_market_depth(self, item_type):
        return {
            "item": item_type,
            "buy_orders": [{"price": 3.0, "qty": 10}],
            "sell_orders": [{"price": 2.5, "qty": 4}],
        }

    def place_market_buy(self, item_type, quantity, max_price):
        self.buy_calls.append((item_type, quantity, max_price))
        return {"status": "queued"}


def test_parse_price_cap_requires_item_price_pairs():
    assert parse_price_cap(["IRON_ORE=2.5", "copper_ore=4"]) == {
        "IRON_ORE": 2.5,
        "COPPER_ORE": 4.0,
    }


def test_analyze_item_dry_run_does_not_submit_buy():
    client = FakeTraderClient()

    decision = analyze_item(client, "IRON_ORE", max_unit_price=2.5, quantity=10, execute=False)

    assert decision["item_type"] == "IRON_ORE"
    assert decision["quantity"] == 4
    assert decision["max_price"] == 2.5
    assert client.buy_calls == []


def test_analyze_item_execute_submits_capped_buy():
    client = FakeTraderClient()

    result = analyze_item(client, "IRON_ORE", max_unit_price=2.5, quantity=10, execute=True)

    assert result == {"status": "queued"}
    assert client.buy_calls == [("IRON_ORE", 4, 2.5)]
