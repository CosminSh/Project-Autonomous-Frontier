import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Ensure we can import from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_migration")

# Database URL from environment or fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///terminal_frontier.db")

def run_migrations(engine: Engine):
    """Safely applies missing columns to the database schema."""
    
    # This list should match the safe_migrations in main.py
    safe_migrations = [
        ("agents", "accuracy", "INTEGER DEFAULT 15"),
        ("agents", "overclock", "INTEGER DEFAULT 10"),
        ("agents", "max_mass", "FLOAT DEFAULT 100.0"),
        ("agents", "storage_capacity", "FLOAT DEFAULT 500.0"),
        ("agents", "last_daily_reward", "DATETIME"),
        ("agents", "is_pitfighter", "BOOLEAN DEFAULT FALSE"),
        ("agents", "is_aggressive", "BOOLEAN DEFAULT FALSE"),
        ("agents", "wear_and_tear", "FLOAT DEFAULT 0.0"),
        ("agents", "overclock_ticks", "INTEGER DEFAULT 0"),
        ("agents", "heat", "INTEGER DEFAULT 0"),
        ("agents", "unlocked_recipes", "JSON"),
        ("agents", "squad_id", "INTEGER"),
        ("agents", "pending_squad_invite", "INTEGER"),
        ("agents", "corporation_id", "INTEGER"),
        ("agents", "last_faction_change_tick", "INTEGER DEFAULT 0"),
        ("agents", "last_attacked_tick", "INTEGER DEFAULT 0"),
        ("agents", "is_in_anarchy_zone", "BOOLEAN DEFAULT FALSE"),
        ("agents", "arena_losses", "INTEGER DEFAULT 0"),
        ("arena_profiles", "daily_opponents", "JSON"),
        ("agents", "mining_yield", "INTEGER DEFAULT 10"),
        ("agents", "experience", "INTEGER DEFAULT 0"),
        ("agents", "level", "INTEGER DEFAULT 1"),
        ("agents", "speed", "INTEGER DEFAULT 10"),
        ("world_hexes", "resource_quantity", "INTEGER DEFAULT 0"),
        ("world_hexes", "expires_tick", "BIGINT"),
        ("global_state", "actions_processed", "INTEGER DEFAULT 0"),
        ("bounties", "claimed_by", "INTEGER REFERENCES agents(id)"),
        ("bounties", "claim_tick", "BIGINT"),
        ("bounties", "created_at", "DATETIME"),
        ("auction_house", "created_at", "DATETIME"),
        ("market_pickups", "created_at", "DATETIME"),
        ("intents", "created_at", "DATETIME"),
        ("daily_missions", "created_at", "DATETIME"),
        ("daily_missions", "reward_xp", "INTEGER DEFAULT 100"),
        ("corporations", "created_at", "DATETIME"),
        ("corporations", "vault_capacity", "FLOAT DEFAULT 5000.0"),
        ("corporations", "credit_vault", "INTEGER DEFAULT 0"),
        ("corporations", "tax_rate", "FLOAT DEFAULT 0.0"),
        ("api_key_revocations", "reason", "VARCHAR"),
        ("api_key_revocations", "revoked_at", "DATETIME"),
        ("agents", "corp_role", "VARCHAR DEFAULT 'MEMBER'"),
        ("corporations", "join_policy", "VARCHAR DEFAULT 'OPEN'"),
        ("corporations", "motd", "TEXT"),
        ("corporations", "upgrades", "JSON"),
    ]
    
    logger.info(f"Starting migrations on: {DATABASE_URL}")
    
    # Ensure new tables are created
    from models import Base
    Base.metadata.create_all(engine)
    logger.info("Checked/Created all missing tables.")
    
    with engine.connect() as conn:
        for table, col, col_type in safe_migrations:
            try:
                # SQLite doesn't support 'IF NOT EXISTS' for ADD COLUMN directly in standard SQL
                # So we use a try-except block to catch the error if the column already exists
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"SUCCESS: Added column '{col}' to table '{table}'.")
            except Exception as e:
                err_str = str(e).lower()
                # Common error strings for existing columns across different DB engines
                if any(x in err_str for x in ["duplicate column", "already exists", "has no column", "duplicate"]):
                    logger.debug(f"SKIP: Column '{col}' already exists in table '{table}'.")
                else:
                    logger.error(f"FAIL: Could not add column '{col}' to table '{table}': {e}")
                    # We don't raise here to allow other migrations to proceed
                    
    logger.info("Migrations complete.")

if __name__ == "__main__":
    # Create engine and run
    engine = create_engine(DATABASE_URL)
    run_migrations(engine)
