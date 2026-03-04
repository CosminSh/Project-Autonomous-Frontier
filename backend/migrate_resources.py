import os
import random
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from models import WorldHex

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def migrate():
    with engine.connect() as conn:
        print("Checking if resource_quantity exists...")
        try:
            # Check if column exists, if it fails, it means it doesn't exist
            conn.execute(text("SELECT resource_quantity FROM world_hexes LIMIT 1"))
            print("Column resource_quantity already exists.")
        except Exception:
            print("Adding resource_quantity column...")
            # SQLite doesn't support ADD COLUMN with DEFAULT easily for some versions, but IF NOT EXISTS isn't supported for ADD COLUMN
            # Postgres supports ADD COLUMN. Let's try to add it.
            try:
                # If SQLite
                if "sqlite" in DATABASE_URL:
                    conn.execute(text("ALTER TABLE world_hexes ADD COLUMN resource_quantity INTEGER DEFAULT 0"))
                else: 
                    # Postgres
                    conn.execute(text("ALTER TABLE world_hexes ADD COLUMN IF NOT EXISTS resource_quantity INTEGER DEFAULT 0"))
                conn.commit()
                print("Added column!")
            except Exception as e:
                print(f"Error adding column (might already exist or syntax error): {e}")

    db = SessionLocal()
    # Populate existing resources with a random finite quantity
    hexes = db.query(WorldHex).filter(WorldHex.resource_type != None).all()
    count = 0
    for h in hexes:
        if h.resource_quantity == 0 or h.resource_quantity is None:
            # Base quantity
            qty = random.randint(100, 1000)
            h.resource_quantity = qty
            count += 1
            
    db.commit()
    print(f"Populated {count} existing nodes with finite resources (100-1000)!")
    db.close()

if __name__ == "__main__":
    migrate()
