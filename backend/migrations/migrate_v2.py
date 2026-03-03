import os
from sqlalchemy import create_engine, text, inspect

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)

def run_comprehensive_migration():
    print(f"Connecting to {DATABASE_URL}...", flush=True)
    inspector = inspect(engine)
    
    # Table: agents
    agent_cols = {
        "user_email": "VARCHAR",
        "api_key": "VARCHAR",
        "owner": "VARCHAR",
        "name": "VARCHAR",
        "structure": "INTEGER DEFAULT 100",
        "max_structure": "INTEGER DEFAULT 100",
        "capacitor": "INTEGER DEFAULT 100",
        "kinetic_force": "INTEGER DEFAULT 10",
        "logic_precision": "INTEGER DEFAULT 10",
        "overclock": "INTEGER DEFAULT 10",
        "integrity": "INTEGER DEFAULT 5",
        "max_mass": "FLOAT DEFAULT 100.0",
        "storage_capacity": "FLOAT DEFAULT 500.0",
        "is_bot": "BOOLEAN DEFAULT FALSE",
        "is_feral": "BOOLEAN DEFAULT FALSE",
        "is_aggressive": "BOOLEAN DEFAULT FALSE",
        "q": "INTEGER",
        "r": "INTEGER",
        "faction_id": "INTEGER DEFAULT 1",
        "squad_id": "INTEGER",
        "pending_squad_invite": "INTEGER",
        "corporation_id": "INTEGER",
        "heat": "INTEGER DEFAULT 0",
        "overclock_ticks": "INTEGER DEFAULT 0",
        "wear_and_tear": "FLOAT DEFAULT 0.0",
        "last_faction_change_tick": "INTEGER DEFAULT 0",
        "unlocked_recipes": "JSON",
        "last_daily_reward": "DATETIME",
        "level": "INTEGER DEFAULT 1",
        "experience": "INTEGER DEFAULT 0"
    }
    
    existing_agent_cols = [c["name"] for c in inspector.get_columns("agents")]
    
    with engine.connect() as conn:
        for col, col_type in agent_cols.items():
            if col not in existing_agent_cols:
                print(f"Adding column agents.{col} ({col_type})...")
                try:
                    conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Error adding {col}: {e}")
                    conn.rollback()

    # Table: chassis_parts
    part_cols = {
        "rarity": "VARCHAR DEFAULT 'STANDARD'",
        "stats": "JSON",
        "affixes": "JSON",
        "durability": "FLOAT DEFAULT 100.0"
    }
    existing_part_cols = [c["name"] for c in inspector.get_columns("chassis_parts")]
    with engine.connect() as conn:
        for col, col_type in part_cols.items():
            if col not in existing_part_cols:
                print(f"Adding column chassis_parts.{col} ({col_type})...")
                try:
                    conn.execute(text(f"ALTER TABLE chassis_parts ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Error adding {col}: {e}")
                    conn.rollback()

    # Table: inventory_items
    inv_cols = {
        "data": "JSON"
    }
    existing_inv_cols = [c["name"] for c in inspector.get_columns("inventory_items")]
    with engine.connect() as conn:
        for col, col_type in inv_cols.items():
            if col not in existing_inv_cols:
                print(f"Adding column inventory_items.{col} ({col_type})...")
                try:
                    conn.execute(text(f"ALTER TABLE inventory_items ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Error adding {col}: {e}")
                    conn.rollback()

    # Table: daily_missions
    mission_cols = {
        "min_level": "INTEGER DEFAULT 1",
        "max_level": "INTEGER DEFAULT 99",
        "item_type": "VARCHAR"
    }
    existing_mission_cols = [c["name"] for c in inspector.get_columns("daily_missions")]
    with engine.connect() as conn:
        for col, col_type in mission_cols.items():
            if col not in existing_mission_cols:
                print(f"Adding column daily_missions.{col} ({col_type})...")
                try:
                    conn.execute(text(f"ALTER TABLE daily_missions ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Error adding {col}: {e}")
                    conn.rollback()

    # Table: bounties
    bounty_cols = {
        "claimed_by": "INTEGER",
        "claim_tick": "BIGINT"
    }
    existing_bounty_cols = [c["name"] for c in inspector.get_columns("bounties")]
    with engine.connect() as conn:
        for col, col_type in bounty_cols.items():
            if col not in existing_bounty_cols:
                print(f"Adding column bounties.{col} ({col_type})...")
                try:
                    conn.execute(text(f"ALTER TABLE bounties ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Error adding {col}: {e}")
                    conn.rollback()

    print("Comprehensive migration complete!")

if __name__ == "__main__":
    run_comprehensive_migration()
