import os
import sys
from sqlalchemy import create_engine, text

def main():
    # Attempt to load the database URL from the environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Fallback for local development if terminal_frontier.db exists
        db_path = os.path.join(os.path.dirname(__file__), "..", "terminal_frontier.db")
        if os.path.exists(db_path):
            db_url = f"sqlite:///{os.path.abspath(db_path)}"
        else:
            print("Error: DATABASE_URL environment variable is not set and terminal_frontier.db not found!")
            return

    print(f"Connecting to database at: {db_url}")
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            print("Adding 'data' column to 'auction_house' table...")
            try:
                conn.execute(text("ALTER TABLE auction_house ADD COLUMN data JSON;"))
                print("Successfully added 'data' to 'auction_house'.")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print("Column 'data' already exists in 'auction_house'.")
                else:
                    print(f"Error adding column to 'auction_house': {e}")

            print("Adding 'data' column to 'market_pickups' table...")
            try:
                conn.execute(text("ALTER TABLE market_pickups ADD COLUMN data JSON;"))
                print("Successfully added 'data' to 'market_pickups'.")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print("Column 'data' already exists in 'market_pickups'.")
                else:
                    print(f"Error adding column to 'market_pickups': {e}")

            conn.commit()
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"FATAL ERROR during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
