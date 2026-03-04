import os
import random
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from models import WorldHex

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def migrate():
    # Phase 1: Schema Update
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            print("Updating schema...")
            if "sqlite" in DATABASE_URL:
                try:
                    conn.execute(text("ALTER TABLE world_hexes ADD COLUMN resource_quantity INTEGER DEFAULT 0"))
                    print("Added column resource_quantity (SQLite)")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("Column resource_quantity already exists.")
                    else:
                        raise e
            else:
                # Postgres: IF NOT EXISTS is robust
                conn.execute(text("ALTER TABLE world_hexes ADD COLUMN IF NOT EXISTS resource_quantity INTEGER DEFAULT 0"))
                print("Handled resource_quantity column (Postgres)")
            
            trans.commit()
        except Exception as e:
            trans.rollback()
            print(f"Schema update notification/error: {e}")
            # Keep going, maybe the column is already there and we just couldn't verify it


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
