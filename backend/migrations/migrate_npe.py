from sqlalchemy import text
from database import engine

def run_migration():
    print("Checking Database Connection...")
    with engine.connect() as conn:
        print("Adding last_daily_reward to agents...")
        try:
            conn.execute(text("ALTER TABLE agents ADD COLUMN last_daily_reward TIMESTAMP"))
            conn.commit()
            print("Successfully added last_daily_reward")
        except Exception as e:
            # Handle both SQLite and Postgres error styles for 'column already exists'
            e_str = str(e).lower()
            if "already exists" in e_str or "duplicate column" in e_str:
                print("Skipped agents.last_daily_reward: Already exists")
            else:
                print(f"Error adding agents.last_daily_reward: {e}")

        print("Adding min_level and max_level to daily_missions...")
        try:
            conn.execute(text("ALTER TABLE daily_missions ADD COLUMN min_level INTEGER DEFAULT 1"))
            conn.commit()
            print("Successfully added daily_missions.min_level")
        except Exception as e:
            e_str = str(e).lower()
            if "already exists" in e_str or "duplicate column" in e_str:
                print("Skipped daily_missions.min_level: Already exists")
            else:
                print(f"Error adding daily_missions.min_level: {e}")

        try:
            conn.execute(text("ALTER TABLE daily_missions ADD COLUMN max_level INTEGER DEFAULT 99"))
            conn.commit()
            print("Successfully added daily_missions.max_level")
        except Exception as e:
            e_str = str(e).lower()
            if "already exists" in e_str or "duplicate column" in e_str:
                print("Skipped daily_missions.max_level: Already exists")
            else:
                print(f"Error adding daily_missions.max_level: {e}")

    print("Migration complete!")

if __name__ == "__main__":
    run_migration()
