import os
from sqlalchemy import create_engine, text

def main():
    db_url = "sqlite:///g:/Antigravity Projects/Project Autonomous Frontier/backend/terminal_frontier.db"
    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    queries = [
        "ALTER TABLE agents ADD COLUMN performance_stats JSON DEFAULT '{}';",
        "ALTER TABLE agents ADD COLUMN webhook_url TEXT;"
    ]
    
    with engine.connect() as conn:
        for q in queries:
            try:
                conn.execute(text(q))
                conn.commit()
                print(f"Executed: {q}")
            except Exception as e:
                err = str(e).lower()
                if "duplicate column" in err or "already exists" in err:
                    print(f"Column already exists: {q}")
                else:
                    print(f"Error executing {q}: {e}")

if __name__ == "__main__":
    main()
