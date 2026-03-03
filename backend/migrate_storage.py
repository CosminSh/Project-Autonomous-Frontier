import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import DATABASE_URL

logger = logging.getLogger("migrate_storage")
logging.basicConfig(level=logging.INFO)

def migrate():
    logger.info(f"Connecting to database at {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Add storage_capacity to agents
        logger.info("Checking for 'storage_capacity' in 'agents' table...")
        if engine.name == 'sqlite':
            result = session.execute(text("PRAGMA table_info(agents);"))
            columns = [row[1] for row in result]
            if 'storage_capacity' not in columns:
                logger.info("Adding 'storage_capacity' to 'agents' table...")
                session.execute(text("ALTER TABLE agents ADD COLUMN storage_capacity FLOAT DEFAULT 500.0;"))
            else:
                logger.info("'storage_capacity' already exists.")
        else:
            # PostgreSQL
            check_query = text("SELECT column_name FROM information_schema.columns WHERE table_name='agents' AND column_name='storage_capacity';")
            if not session.execute(check_query).fetchone():
                logger.info("Adding 'storage_capacity' to 'agents' table...")
                session.execute(text("ALTER TABLE agents ADD COLUMN storage_capacity FLOAT DEFAULT 500.0;"))
            else:
                logger.info("'storage_capacity' already exists.")

        # 2. Create storage_items table
        logger.info("Creating 'storage_items' table if it doesn't exist...")
        create_table_query = text("""
            CREATE TABLE IF NOT EXISTS storage_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER REFERENCES agents(id),
                item_type TEXT,
                quantity INTEGER DEFAULT 1,
                data JSON,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );
        """)
        if engine.name != 'sqlite':
             create_table_query = text("""
                CREATE TABLE IF NOT EXISTS storage_items (
                    id SERIAL PRIMARY KEY,
                    agent_id INTEGER REFERENCES agents(id),
                    item_type VARCHAR,
                    quantity INTEGER DEFAULT 1,
                    data JSONB
                );
            """)
        
        session.execute(create_table_query)
        session.commit()
        logger.info("Migration completed successfully.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
