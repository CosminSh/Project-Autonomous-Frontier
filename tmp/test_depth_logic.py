from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
import json

class AuctionOrder:
    def __init__(self, id, order_type, price, quantity):
        self.id = id
        self.order_type = order_type
        self.price = price
        self.quantity = quantity

def test_depth_logic():
    DB_PATH = "sqlite:///backend/terminal_frontier.db"
    engine = create_engine(DB_PATH)
    
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, order_type, price, quantity FROM auction_house WHERE item_type = 'IRON_ORE'")).fetchall()
        orders = [AuctionOrder(r[0], r[1], r[2], r[3]) for r in res]
        
        print(f"Total orders in DB: {len(orders)}")
        for o in orders:
            print(f"  ID: {o.id} | Type: {o.order_type} | Price: {o.price} | Qty: {o.quantity}")

        depth = {"BUY": {}, "SELL": {}}
        for o in orders:
            price_str = f"{o.price:.2f}"
            depth[o.order_type][price_str] = depth[o.order_type].get(price_str, 0) + o.quantity
            
        result = {
            "sell_orders": sorted([{"price": float(p), "qty": q} for p, q in depth["SELL"].items()], key=lambda x: x["price"])
        }
        print("\nAggregated Result:")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_depth_logic()
