import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("migration")

DB_PATH = "game.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check columns in corporations
    cursor.execute("PRAGMA table_info(corporations)")
    columns = [col[1] for col in cursor.fetchall()]

    if "upgrades" not in columns:
        logger.info("Adding column 'upgrades' to table 'corporations'...")
        try:
            cursor.execute("ALTER TABLE corporations ADD COLUMN upgrades JSON")
            conn.commit()
            logger.info("SUCCESS: Added column 'upgrades' to table 'corporations'.")
        except Exception as e:
            logger.error(f"FAILED to add column 'upgrades': {e}")
    else:
        logger.info("Column 'upgrades' already exists in table 'corporations'.")

    conn.close()
    logger.info("Migration complete.")

if __name__ == "__main__":
    migrate()
