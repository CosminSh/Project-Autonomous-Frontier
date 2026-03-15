from sqlalchemy import create_engine, text
import json

DB_PATH = "sqlite:///backend/terminal_frontier.db"
engine = create_engine(DB_PATH)

def check_agent_80():
    with engine.connect() as conn:
        print("--- AUDIT LOGS FOR AGENT 80 (BulkBuyer) ---")
        logs = conn.execute(text("SELECT event_type, details, time FROM audit_logs WHERE agent_id = 80 ORDER BY id DESC")).fetchall()
        for log in logs:
            print(f"{log[2]} | {log[0]} | {log[1]}")

        print("\n--- AGENT 80 INVENTORY ---")
        inv = conn.execute(text("SELECT item_type, quantity FROM inventory_items WHERE agent_id = 80")).fetchall()
        print(dict(inv))

        print("\n--- ACTIVE SELL ORDERS FOR IRON_ORE ---")
        orders = conn.execute(text("SELECT id, owner, quantity, price FROM auction_house WHERE item_type = 'IRON_ORE' AND order_type = 'SELL'")).fetchall()
        for o in orders:
            print(f"ID: {o[0]} | Owner: {o[1]} | Qty: {o[2]} | Price: {o[3]}")

if __name__ == "__main__":
    check_agent_80()
