import sqlite3
import os

DB_PATH = 'terminal_frontier.db'

def migrate_sqlite():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # SQLite columns renaming (Supported in SQLite 3.25.0+)
        cursor.execute("ALTER TABLE agents RENAME COLUMN structure TO health;")
        cursor.execute("ALTER TABLE agents RENAME COLUMN max_structure TO max_health;")
        cursor.execute("ALTER TABLE agents RENAME COLUMN kinetic_force TO damage;")
        cursor.execute("ALTER TABLE agents RENAME COLUMN logic_precision TO accuracy;")
        cursor.execute("ALTER TABLE agents RENAME COLUMN integrity TO armor;")
        cursor.execute("ALTER TABLE agents RENAME COLUMN capacitor TO energy;")
        
        # Add new speed column
        cursor.execute("ALTER TABLE agents ADD COLUMN speed FLOAT DEFAULT 10.0;")
        
        print("Successfully migrated local SQLite database to new RPG stats (health, damage, energy, etc.)")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Migration error (might already be migrated or SQLite version is too old): {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_sqlite()
