import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TMP = ROOT / "tmp"
TMP.mkdir(exist_ok=True)

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{(TMP / 'pytest.db').as_posix()}")
os.environ.setdefault("LOG_FILE", str(TMP / "pytest_app.log"))

from database import engine  # noqa: E402
from models import Base  # noqa: E402
from sqlalchemy import text  # noqa: E402


def pytest_sessionstart(session):
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for table, column, column_type in [
            ("agent_state", "is_banned", "BOOLEAN DEFAULT FALSE"),
            ("agent_state", "muted_until", "TIMESTAMP"),
            ("agent_state", "moderation_note", "VARCHAR"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
                conn.commit()
            except Exception:
                conn.rollback()
