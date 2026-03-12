
import os
import logging
from sqlalchemy import create_engine, text
from database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_patch")

def patch_db():
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not set!")
        return

    logger.info(f"Connecting to database at {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)

    # Exhaustive list of columns to ensure they exist
    # (table, column, type)
    required_cols = [
        ("agents", "health", "INTEGER DEFAULT 100"),
        ("agents", "max_health", "INTEGER DEFAULT 100"),
        ("agents", "energy", "INTEGER DEFAULT 100"),
        ("agents", "armor", "INTEGER DEFAULT 5"),
        ("agents", "damage", "INTEGER DEFAULT 10"),
        ("agents", "accuracy", "INTEGER DEFAULT 15"),
        ("agents", "overclock", "INTEGER DEFAULT 10"),
        ("agents", "max_mass", "FLOAT DEFAULT 100.0"),
        ("agents", "storage_capacity", "FLOAT DEFAULT 500.0"),
        ("agents", "mining_yield", "INTEGER DEFAULT 10"),
        ("agents", "experience", "INTEGER DEFAULT 0"),
        ("agents", "level", "INTEGER DEFAULT 1"),
        ("agents", "speed", "INTEGER DEFAULT 10"),
        ("agents", "is_bot", "BOOLEAN DEFAULT False"),
        ("agents", "is_feral", "BOOLEAN DEFAULT False"),
        ("agents", "is_pitfighter", "BOOLEAN DEFAULT False"),
        ("agents", "is_aggressive", "BOOLEAN DEFAULT False"),
        ("agents", "heat", "INTEGER DEFAULT 0"),
        ("agents", "overclock_ticks", "INTEGER DEFAULT 0"),
        ("agents", "wear_and_tear", "FLOAT DEFAULT 0.0"),
        ("agents", "last_faction_change_tick", "INTEGER DEFAULT 0"),
        ("agents", "last_attacked_tick", "INTEGER DEFAULT 0"),
        ("agents", "is_in_anarchy_zone", "BOOLEAN DEFAULT False"),
        ("agents", "last_daily_reward", "TIMESTAMP"),
        ("agents", "unlocked_recipes", "JSON"),
        ("agents", "squad_id", "INTEGER"),
        ("agents", "pending_squad_invite", "INTEGER"),
        ("agents", "corporation_id", "INTEGER"),
        
        ("world_hexes", "resource_quantity", "INTEGER DEFAULT 0"),
        ("global_state", "actions_processed", "INTEGER DEFAULT 0"),
        
        ("bounties", "claimed_by", "INTEGER"),
        ("bounties", "claim_tick", "BIGINT"),
        ("bounties", "created_at", "TIMESTAMP"),
        
        ("auction_house", "created_at", "TIMESTAMP"),
        ("market_pickups", "created_at", "TIMESTAMP"),
        ("intents", "created_at", "TIMESTAMP"),
        ("daily_missions", "created_at", "TIMESTAMP"),
        ("corporations", "created_at", "TIMESTAMP"),
        ("api_key_revocations", "reason", "VARCHAR"),
        ("api_key_revocations", "revoked_at", "TIMESTAMP"),
    ]

    for table, col, col_type in required_cols:
        with engine.connect() as conn:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Fixed: Added {col} to {table}")
            except Exception as e:
                # Most DBs allow rolling back after a failed ADD COLUMN if it already exists
                err = str(e).lower()
                if "already exists" in err or "duplicate column" in err:
                    pass 
                else:
                    logger.warning(f"Could not add {table}.{col}: {e}")

    # Sanity check: Ensure mass/capacity aren't NULL for existing rows
    with engine.connect() as conn:
        conn.execute(text("UPDATE agents SET max_mass = 100.0 WHERE max_mass IS NULL"))
        conn.execute(text("UPDATE agents SET storage_capacity = 500.0 WHERE storage_capacity IS NULL"))
        conn.commit()
        logger.info("Sanity check: Validated agent mass/capacity constraints.")

    logger.info("Database patching complete.")

if __name__ == "__main__":
    patch_db()
