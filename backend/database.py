"""
database.py — Database engine, session factory, and shared global state.
Imported by all other modules that need DB access or the station cache.
"""
import os
import logging

from sqlalchemy import create_engine, event, select
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

from models import WorldHex

logger = logging.getLogger("heartbeat")

import sys
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("CRITICAL ERROR: DATABASE_URL environment variable is not set!")
    # We don't sys.exit here to allow Sphinx/Alembic/Local tests to potentially mock it if they don't import early, 
    # but for the main app it will fail at engine creation below.
    # For extra safety:
    DATABASE_URL = "sqlite:///:memory:" 
    # Actually, let's enforce it more strictly for the real engine if we are running the server.

# NullPool: good for SQLite (single-file, no TCP overhead)
# Default pool: required for PostgreSQL (each new connection has TCP handshake cost)
_pool_kwargs = {"poolclass": NullPool} if "sqlite" in DATABASE_URL else {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 10,       # fail fast instead of hanging 30s
    "pool_recycle": 300,      # recycle connections every 5 min to avoid stale handles
    "pool_pre_ping": True,    # validates connection before use; catches stale connections
}

if not os.getenv("DATABASE_URL") and not "pytest" in sys.modules:
    print("\n" + "!"*80)
    print("! CRITICAL: DATABASE_URL environment variable not set.")
    print("! The application cannot start without a valid database connection string.")
    print("!"*80 + "\n")
    sys.exit(1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    **_pool_kwargs
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
