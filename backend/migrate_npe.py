import sqlite3

def run_migration():
    db_path = "terminal_frontier.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Adding last_daily_reward to agents...")
    try:
        cursor.execute("ALTER TABLE agents ADD COLUMN last_daily_reward DATETIME")
    except sqlite3.OperationalError as e:
        print(f"Skipped agents.last_daily_reward: {e}")

    print("Adding min_level and max_level to daily_missions...")
    try:
        cursor.execute("ALTER TABLE daily_missions ADD COLUMN min_level INTEGER DEFAULT 1")
    except sqlite3.OperationalError as e:
        print(f"Skipped daily_missions.min_level: {e}")

    try:
        cursor.execute("ALTER TABLE daily_missions ADD COLUMN max_level INTEGER DEFAULT 99")
    except sqlite3.OperationalError as e:
        print(f"Skipped daily_missions.max_level: {e}")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    run_migration()
