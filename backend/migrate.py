import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@db:5432/strike_vector")
engine = create_engine(DATABASE_URL)

def run_migration():
    print(f"Connecting to {DATABASE_URL}...")
    with engine.connect() as conn:
        # Check and add columns to 'agents' table
        columns_to_add = [
            ("is_aggressive", "BOOLEAN DEFAULT FALSE"),
            ("faction_id", "INTEGER"),
            ("heat", "INTEGER DEFAULT 0"),
            ("overclock_ticks", "INTEGER DEFAULT 0"),
            ("wear_and_tear", "DOUBLE PRECISION DEFAULT 0.0"),
            ("last_faction_change_tick", "INTEGER DEFAULT 0"),
            ("max_mass", "DOUBLE PRECISION DEFAULT 100.0"),
            ("unlocked_recipes", "JSON")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                print(f"Adding column {col_name} to agents...")
                conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type};"))
                conn.commit()
                print(f"Successfully added {col_name}")
            except Exception as e:
                print(f"Column {col_name} might already exist or error: {e}")
                conn.rollback()

        # Check and add columns to 'chassis_parts' table
        parts_cols = [
            ("rarity", "VARCHAR DEFAULT 'STANDARD'"),
            ("affixes", "JSON")
        ]

        for col_name, col_type in parts_cols:
            try:
                print(f"Adding column {col_name} to chassis_parts...")
                conn.execute(text(f"ALTER TABLE chassis_parts ADD COLUMN {col_name} {col_type};"))
                conn.commit()
                print(f"Successfully added {col_name}")
            except Exception as e:
                print(f"Column {col_name} might already exist or error: {e}")
                conn.rollback()

    print("Migration complete!")

if __name__ == "__main__":
    run_migration()
