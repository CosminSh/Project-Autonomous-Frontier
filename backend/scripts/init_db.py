import os
import time
from sqlalchemy import create_engine, text
from models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/terminal_frontier")

def init_db():
    print(f"Connecting to database at {DATABASE_URL}...")
    
    # Wait for DB to be ready
    retries = 5
    while retries > 0:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception as e:
            print(f"Waiting for database... ({e})")
            retries -= 1
            time.sleep(5)
    
    if retries == 0:
        print("Could not connect to database. Exiting.")
        return

    print("Creating tables...")
    Base.metadata.create_all(engine)

    print("Setting up TimescaleDB hypertables...")
    with engine.connect() as conn:
        try:
            # Check if timescaledb extension is available and created
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            # Convert audit_logs to a hypertable
            # We use try/except because if it's already a hypertable, it will fail
            conn.execute(text("SELECT create_hypertable('audit_logs', 'time', if_not_exists => TRUE);"))
            conn.commit()
            print("TimescaleDB setup complete.")
        except Exception as e:
            print(f"Note: TimescaleDB setup encountered an issue (might already be configured): {e}")

    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
