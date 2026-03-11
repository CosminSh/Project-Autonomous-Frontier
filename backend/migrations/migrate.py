import os
from sqlalchemy import create_engine, text

import sys
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("\nCRITICAL: DATABASE_URL environment variable is not set for migration.", flush=True)
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    print(f"Connecting to {DATABASE_URL}...", flush=True)
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check and add columns to 'agents' table
            columns_to_add = [
                ("is_aggressive", "BOOLEAN DEFAULT FALSE"),
                ("is_bot", "BOOLEAN DEFAULT FALSE"),
                ("is_feral", "BOOLEAN DEFAULT FALSE"),
                ("faction_id", "INTEGER"),
                ("heat", "INTEGER DEFAULT 0"),
                ("overclock_ticks", "INTEGER DEFAULT 0"),
                ("wear_and_tear", "DOUBLE PRECISION DEFAULT 0.0"),
                ("last_faction_change_tick", "INTEGER DEFAULT 0"),
                ("max_mass", "DOUBLE PRECISION DEFAULT 100.0"),
                ("unlocked_recipes", "JSON"),
                ("squad_id", "INTEGER")
            ]
            
            for col_name, col_type in columns_to_add:
                try:
                    print(f"Checking/Adding column {col_name} to agents...", flush=True)
                    conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                    print(f"  Successfully handled {col_name}", flush=True)
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"  Column {col_name} already exists.", flush=True)
                    else:
                        print(f"  CRITICAL ERROR adding {col_name}: {e}", flush=True)
                        conn.rollback()
                        raise
            
            parts_cols = [
                ("rarity", "VARCHAR DEFAULT 'STANDARD'"),
                ("affixes", "JSON"),
                ("durability", "DOUBLE PRECISION DEFAULT 100.0")
            ]

            for col_name, col_type in parts_cols:
                try:
                    print(f"Checking/Adding column {col_name} to chassis_parts...", flush=True)
                    conn.execute(text(f"ALTER TABLE chassis_parts ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                    print(f"  Successfully handled {col_name}", flush=True)
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"  Column {col_name} already exists.", flush=True)
                    else:
                        print(f"  CRITICAL ERROR adding {col_name}: {e}", flush=True)
                        conn.rollback()
                        raise

            # Check and add columns to 'inventory_items' table
            inv_cols = [
                ("data", "JSON")
            ]

            for col_name, col_type in inv_cols:
                try:
                    print(f"Checking/Adding column {col_name} to inventory_items...", flush=True)
                    conn.execute(text(f"ALTER TABLE inventory_items ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                    print(f"  Successfully handled {col_name}", flush=True)
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"  Column {col_name} already exists.", flush=True)
                    else:
                        print(f"  CRITICAL ERROR adding {col_name}: {e}", flush=True)
                        conn.rollback()
                        raise
    except Exception as e:
        print(f"CRITICAL MIGRATION ERROR: {e}", flush=True)

    print("Migration attempt complete!", flush=True)

if __name__ == "__main__":
    run_migration()
