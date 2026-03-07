import sqlite3
import os

DB_PATH = "g:/Antigravity Projects/Project Autonomous Frontier/backend/terminal_frontier.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Checking for existing arena columns in agents table...")
    cursor.execute("PRAGMA table_info(agents)")
    columns = [row[1] for row in cursor.fetchall()]
    
    has_legacy = all(col in columns for col in ['elo', 'arena_wins', 'arena_losses'])

    if not has_legacy:
        print("Legacy columns not found in agents table. Possibly already migrated.")
    else:
        print("Creating arena_profiles table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arena_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER UNIQUE,
                elo INTEGER DEFAULT 1200,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_battle_time DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE
            )
        """)

        print("Migrating pit fighter data...")
        # Get all agents that were pit fighters
        cursor.execute("SELECT id, elo, arena_wins, arena_losses FROM agents WHERE name LIKE '%-PitFighter'")
        fighters = cursor.fetchall()
        
        for f_id, elo, wins, losses in fighters:
            cursor.execute("""
                INSERT OR IGNORE INTO arena_profiles (agent_id, elo, wins, losses)
                VALUES (?, ?, ?, ?)
            """, (f_id, elo, wins, losses))
        
        print(f"Successfully migrated {len(fighters)} pit fighter profiles.")

    # We don't drop columns in SQLite easily without recreating the table, 
    # so we'll leave them as ghosts for now or the user can do it later.
    # The models won't use them anymore.

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
