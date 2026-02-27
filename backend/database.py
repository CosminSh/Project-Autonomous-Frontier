"""
database.py — Database engine, session factory, and shared global state.
Imported by all other modules that need DB access or the station cache.
"""
import os
import logging

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from models import WorldHex

logger = logging.getLogger("heartbeat")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Enable SQLite WAL Mode for performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─────────────────────────────────────────────────────────────────────────────
# Global Station Cache
# ─────────────────────────────────────────────────────────────────────────────
STATION_CACHE = []


def refresh_station_cache():
    """Initializes/refreshes the global station cache for performance."""
    global STATION_CACHE
    with SessionLocal() as db:
        stations = db.execute(select(WorldHex).where(WorldHex.is_station == True)).scalars().all()
        STATION_CACHE.clear()
        STATION_CACHE.extend([{"station_type": s.station_type, "q": s.q, "r": s.r} for s in stations])
    logger.info(f"Station cache initialized with {len(STATION_CACHE)} stations.")


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
