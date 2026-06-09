"""
Terminal Frontier example trader.

Dry-run is the default. Use --execute to submit BUY intents.
"""

import argparse
import os
import time

from bot_client import TFClient


DEFAULT_ITEMS = ["IRON_ORE", "COPPER_ORE", "GOLD_ORE", "IRON_INGOT", "HE3_CANISTER"]


def best_bid(depth: dict):
    bids = depth.get("buy_orders", [])
    return bids[0] if bids else None


def best_ask(depth: dict):
    asks = depth.get("sell_orders", [])
    return asks[0] if asks else None


def analyze_item(client: TFClient, item_type: str, max_unit_price: float | None, quantity: int, execute: bool):
    depth = client.get_market_depth(item_type)
    bid = best_bid(depth)
    ask = best_ask(depth)
    bid_price = bid["price"] if bid else None
    ask_price = ask["price"] if ask else None
    spread = (bid_price - ask_price) if bid_price is not None and ask_price is not None else None

    print(f"{item_type}: best_bid={bid_price} best_ask={ask_price} spread={spread}")

    if ask_price is None:
        return None
    if max_unit_price is None:
        return None
    if ask_price > max_unit_price:
        return None

    buy_qty = min(quantity, ask.get("qty", quantity))
    decision = {
        "item_type": item_type,
        "quantity": buy_qty,
        "max_price": ask_price,
        "reason": f"ask {ask_price} <= configured max {max_unit_price}",
    }
    if execute:
        print(f"EXECUTE BUY {buy_qty} {item_type} @ max {ask_price}")
        return client.place_market_buy(item_type, buy_qty, ask_price)

    print(f"DRY RUN BUY {buy_qty} {item_type} @ max {ask_price}: {decision['reason']}")
    return decision


def parse_price_cap(values: list[str]) -> dict[str, float]:
    caps = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --max-price value: {value}. Use ITEM=PRICE.")
        item, price = value.split("=", 1)
        caps[item.strip().upper()] = float(price)
    return caps


def main():
    parser = argparse.ArgumentParser(description="Dry-run or execute simple market sniping decisions.")
    parser.add_argument("--base-url", default=os.getenv("TF_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("TF_API_KEY"))
    parser.add_argument("--items", nargs="*", default=DEFAULT_ITEMS)
    parser.add_argument("--max-price", action="append", default=[], help="Cap as ITEM=PRICE. Example: IRON_ORE=2.5")
    parser.add_argument("--quantity", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between loops. 0 means run once.")
    parser.add_argument("--execute", action="store_true", help="Submit BUY intents. Default is dry-run.")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Set TF_API_KEY or pass --api-key.")
    if args.quantity <= 0:
        raise SystemExit("--quantity must be positive.")

    price_caps = parse_price_cap(args.max_price)
    client = TFClient(api_key=args.api_key, base_url=args.base_url.rstrip("/"))
    items = [item.upper() for item in args.items]

    while True:
        for item_type in items:
            cap = price_caps.get(item_type)
            try:
                analyze_item(client, item_type, cap, args.quantity, args.execute)
            except Exception as exc:
                print(f"{item_type}: error: {exc}")

        if args.interval <= 0:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
