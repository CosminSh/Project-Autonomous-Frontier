import os
from sqlalchemy import create_engine, text

def main():
    # Attempt to load the database URL from the environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set!")
        print("Please export your DATABASE_URL before running this script.")
        print("Example: export DATABASE_URL='postgresql://user:password@localhost/dbname'")
        return

    print("Connecting to the database...")
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Execute the migration query to add the column
            conn.execute(text("ALTER TABLE global_state ADD COLUMN actions_processed INTEGER DEFAULT 0;"))
            conn.commit()
            print("==========================================================")
            print(" SUCCESS! The column 'actions_processed' has been added.")
            print("==========================================================")
    except Exception as e:
        err_msg = str(e).lower()
        if "duplicate column" in err_msg or "already exists" in err_msg:
            print("==========================================================")
            print(" INFO: The column 'actions_processed' already exists.")
            print("       No changes were made.")
            print("==========================================================")
        else:
            print("==========================================================")
            print(" FATAL ERROR: Could not add the column.")
            print(f" Details: {e}")
            print("==========================================================")

if __name__ == "__main__":
    main()
