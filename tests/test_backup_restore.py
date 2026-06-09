import sqlite3
import uuid
from pathlib import Path

from scripts.backup_restore import backup_sqlite, restore_sqlite, verify_sqlite


def test_sqlite_backup_restore_and_integrity_check():
    tmp_path = Path("tmp") / f"backup_restore_test_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"

    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("INSERT INTO agents (name) VALUES (?)", ("Backup Pilot",))
        db.commit()

    backup_sqlite(f"sqlite:///{source.as_posix()}", backup)
    assert verify_sqlite(f"sqlite:///{backup.as_posix()}") == "ok"

    restore_sqlite(f"sqlite:///{restored.as_posix()}", backup)
    assert verify_sqlite(f"sqlite:///{restored.as_posix()}") == "ok"

    with sqlite3.connect(restored) as db:
        row = db.execute("SELECT name FROM agents").fetchone()
    assert row == ("Backup Pilot",)
