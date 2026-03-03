import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import DATABASE_URL

logger = logging.getLogger("migrate_squads")
logging.basicConfig(level=logging.INFO)

def migrate():
    logger.info(f"Connecting to database at {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if the pending_squad_invite column exists
        check_col_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='agents' and column_name='pending_squad_invite';
        """)
        
        # PostgreSQL specific check vs SQLite
        if engine.name == 'sqlite':
            check_col_query = text("PRAGMA table_info(agents);")
            result = session.execute(check_col_query)
            columns = [row[1] for row in result]
            if 'pending_squad_invite' in columns:
                logger.info("'pending_squad_invite' column already exists in 'agents' table (SQLite).")
                return
        else:
            result = session.execute(check_col_query).fetchone()
            if result:
                logger.info("'pending_squad_invite' column already exists in 'agents' table (PostgreSQL).")
                return

        # Add the column
        logger.info("Adding 'pending_squad_invite' to 'agents' table...")
        alt_query = text("ALTER TABLE agents ADD COLUMN pending_squad_invite INTEGER NULL;")
        session.execute(alt_query)
        session.commit()
        logger.info("Migration completed successfully.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
