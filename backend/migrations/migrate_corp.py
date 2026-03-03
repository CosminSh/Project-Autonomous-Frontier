import sqlite3

def apply_migration(db_path):
    print(f"Migrating {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("ALTER TABLE agents ADD COLUMN corporation_id INTEGER")
        conn.commit()
        print(f"Successfully added corporation_id to {db_path}.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column corporation_id already exists in {db_path}.")
        else:
            print(f"Skipped {db_path}: {e}")
    except Exception as e:
        print(f"Error migrating {db_path}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration("demo.db")
    apply_migration("terminal_frontier.db")
    print("Migration complete.")
