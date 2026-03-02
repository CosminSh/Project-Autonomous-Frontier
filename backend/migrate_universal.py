import os
import sqlalchemy
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
print(f"Connecting to: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)

def apply_migrations():
    with engine.connect() as conn:
        print("Checking 'agents' table for missing columns...")
        
        # SQL to check columns depends on DB type
        if "postgresql" in DATABASE_URL:
            # Postgres check
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='agents'
            """)
            result = conn.execute(check_sql)
            columns = [row[0] for row in result]
        else:
            # SQLite check
            check_sql = text("PRAGMA table_info(agents)")
            result = conn.execute(check_sql)
            columns = [row[1] for row in result]
            
        # 1. level
        if "level" not in columns:
            print("  Adding 'level' column...")
            conn.execute(text("ALTER TABLE agents ADD COLUMN level INTEGER DEFAULT 1"))
            conn.commit()
        else:
            print("  'level' column already exists.")

        # 2. experience
        if "experience" not in columns:
            print("  Adding 'experience' column...")
            conn.execute(text("ALTER TABLE agents ADD COLUMN experience INTEGER DEFAULT 0"))
            conn.commit()
        else:
            print("  'experience' column already exists.")

        # 3. corporation_id
        if "corporation_id" not in columns:
            print("  Adding 'corporation_id' column...")
            conn.execute(text("ALTER TABLE agents ADD COLUMN corporation_id INTEGER"))
            conn.commit()
        else:
            print("  'corporation_id' column already exists.")

    print("Migration check complete.")

if __name__ == "__main__":
    apply_migrations()
