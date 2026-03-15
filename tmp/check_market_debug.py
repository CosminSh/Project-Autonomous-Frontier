from sqlalchemy import create_engine, text
import json

DB_PATH = "sqlite:///backend/terminal_frontier.db"
engine = create_engine(DB_PATH)

def check_logs():
    with engine.connect() as conn:
        print("--- GLOBAL STATE ---")
        gs = conn.execute(text("SELECT tick_index, phase FROM global_state")).fetchone()
        if gs:
            print(f"Current Tick: {gs[0]} | Phase: {gs[1]}")
        
        print("\n--- RECENT AUDIT LOGS ---")
        logs = conn.execute(text("SELECT agent_id, event_type, details FROM audit_logs ORDER BY id DESC LIMIT 30")).fetchall()
        for log in logs:
            print(f"Agent {log[0]} | {log[1]} | {log[2]}")

        print("\n--- PENDING INTENTS ---")
        intents = conn.execute(text("SELECT agent_id, action_type, tick_index FROM intents")).fetchall()
        for intent in intents:
            if intent[2] >= (gs[0] if gs else 0):
                print(f"Agent {intent[0]} | {intent[1]} | Tick {intent[2]}")
            
        print("\n--- AGENT INFO (DepthSeller) ---")
        agents = conn.execute(text("SELECT id, name, q, r FROM agents WHERE name LIKE 'DepthSeller%'")).fetchall()
        for agent in agents:
            print(f"ID: {agent[0]} | Name: {agent[1]} | Pos: ({agent[2]}, {agent[3]})")
            # Check inventory
            inv = conn.execute(text("SELECT item_type, quantity FROM inventory_items WHERE agent_id = :aid"), {"aid": agent[0]}).fetchall()
            print(f"  Inventory: {dict(inv)}")

if __name__ == "__main__":
    check_logs()
