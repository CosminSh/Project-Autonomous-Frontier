import sqlite3
import os

db_files = [f for f in os.listdir('.') if f.endswith('.db')]

for db_path in db_files:
    print(f"Migrating {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check if columns exist
        cur.execute("PRAGMA table_info(agents);")
        cols = [c[1] for c in cur.fetchall()]
        
        if 'level' not in cols:
            print(f"  Adding level to {db_path}...")
            cur.execute("ALTER TABLE agents ADD COLUMN level INTEGER DEFAULT 1;")
            conn.commit()
            print("  Done.")
        else:
            print("  level already exists.")
            
        if 'experience' not in cols:
            print(f"  Adding experience to {db_path}...")
            cur.execute("ALTER TABLE agents ADD COLUMN experience INTEGER DEFAULT 0;")
            conn.commit()
            print("  Done.")
        else:
            print("  experience already exists.")
            
    except Exception as e:
        print(f"  Error: {e}")

print("Migration completed.")
