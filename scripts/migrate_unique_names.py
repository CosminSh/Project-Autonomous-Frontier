import sqlite3
import os

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found, skipping.")
        return

    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # 1. Check for duplicates (safety check)
        cur.execute("SELECT name, COUNT(*) FROM agents GROUP BY name HAVING COUNT(*) > 1")
        duplicates = cur.fetchall()
        
        if duplicates:
            print(f"Found duplicates in {db_path}: {duplicates}")
            for name, count in duplicates:
                cur.execute("SELECT id FROM agents WHERE name = ? ORDER BY id", (name,))
                ids = cur.fetchall()
                # Keep the first one, rename others
                for i, (agent_id,) in enumerate(ids[1:], start=1):
                    new_name = f"{name}-{agent_id}"
                    print(f"Renaming agent {agent_id} from '{name}' to '{new_name}'")
                    cur.execute("UPDATE agents SET name = ? WHERE id = ?", (new_name, agent_id))
        
        # 2. Add Unique Index
        print("Adding unique index on 'name' column...")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_unique_name ON agents(name)")
        
        conn.commit()
        print(f"Migration successful for {db_path}.")
    except Exception as e:
        print(f"Error migrating {db_path}: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    base_dir = "g:/Antigravity Projects/Project Autonomous Frontier"
    migrate_db(os.path.join(base_dir, "terminal_frontier.db"))
    migrate_db(os.path.join(base_dir, "demo.db"))
