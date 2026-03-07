import sqlite3
import os

DB_PATH = 'terminal_frontier.db'

def migrate_bounty():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE bounties ADD COLUMN created_at TIMESTAMP DEFAULT '2026-03-01 00:00:00';")
        print("Successfully added created_at to bounties table.")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Migration error (might already exist): {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_bounty()
