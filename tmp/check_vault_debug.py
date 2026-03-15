from sqlalchemy import create_engine, text
import json

DB_PATH = "sqlite:///backend/terminal_frontier.db"
engine = create_engine(DB_PATH)

def check_agent_86():
    with engine.connect() as conn:
        print("--- AUDIT LOGS FOR AGENT 86 (VaultCEO) ---")
        logs = conn.execute(text("SELECT event_type, details, time FROM audit_logs WHERE agent_id = 86 ORDER BY id DESC")).fetchall()
        for log in logs:
            print(f"{log[2]} | {log[0]} | {log[1]}")

        print("\n--- AGENT 86 POSITION ---")
        pos = conn.execute(text("SELECT q, r FROM agents WHERE id = 86")).fetchone()
        print(f"Pos: {pos}")

        print("\n--- AGENT 86 INVENTORY ---")
        inv = conn.execute(text("SELECT item_type, quantity FROM inventory_items WHERE agent_id = 86")).fetchall()
        print(dict(inv))

if __name__ == "__main__":
    check_agent_86()
