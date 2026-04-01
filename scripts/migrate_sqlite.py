import sqlite3

for db_path in ["terminal_frontier.db"]:
    print(f"Migrating {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("PRAGMA table_info(agents);")
        cols = cur.fetchall()
        has_squad = any(c[1] == 'squad_id' for c in cols)
        
        if not has_squad:
            print(f"  Adding squad_id to {db_path}...")
            cur.execute("ALTER TABLE agents ADD COLUMN squad_id INTEGER;")
            conn.commit()
            print("  Done.")
        else:
            print("  squad_id already exists.")
        
    except Exception as e:
        print(f"  Error: {e}")

print("Migration completed.")
