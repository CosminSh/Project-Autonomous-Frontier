"""
Database backup, restore, and integrity verification helpers.

SQLite is handled with the standard library backup API. PostgreSQL uses the
official pg_dump/pg_restore CLIs when they are available on the operator host.
"""
import argparse
import shutil
import sqlite3
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse


def sqlite_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError("DATABASE_URL is not a sqlite URL")
    if parsed.netloc and parsed.netloc != "":
        raise ValueError("Only local sqlite file URLs are supported")
    path = unquote(parsed.path)
    if path.startswith("/") and len(path) > 3 and path[2] == ":":
        path = path[1:]
    elif path.startswith("/") and not database_url.startswith("sqlite:////"):
        path = path[1:]
    return Path(path)


def backup_sqlite(database_url: str, output_path: Path):
    source_path = sqlite_path_from_url(database_url)
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database does not exist: {source_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(output_path) as target:
        source.backup(target)


def restore_sqlite(database_url: str, input_path: Path):
    target_path = sqlite_path_from_url(database_url)
    if not input_path.exists():
        raise FileNotFoundError(f"Backup file does not exist: {input_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(input_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)


def verify_sqlite(database_url: str) -> str:
    db_path = sqlite_path_from_url(database_url)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database does not exist: {db_path}")
    with sqlite3.connect(db_path) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {result}")
    return result


def require_executable(name: str):
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} is required for PostgreSQL backup/restore but was not found on PATH")


def backup_postgres(database_url: str, output_path: Path):
    require_executable("pg_dump")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pg_dump", "--format=custom", "--file", str(output_path), database_url], check=True)


def restore_postgres(database_url: str, input_path: Path):
    require_executable("pg_restore")
    if not input_path.exists():
        raise FileNotFoundError(f"Backup file does not exist: {input_path}")
    subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", database_url, str(input_path)], check=True)


def verify_postgres(database_url: str) -> str:
    require_executable("psql")
    result = subprocess.run(
        ["psql", database_url, "--tuples-only", "--no-align", "--command", "SELECT 1"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if value != "1":
        raise RuntimeError(f"PostgreSQL verification failed: expected 1, got {value!r}")
    return "ok"


def database_kind(database_url: str) -> str:
    scheme = urlparse(database_url).scheme
    if scheme == "sqlite":
        return "sqlite"
    if scheme in {"postgresql", "postgres"}:
        return "postgres"
    raise ValueError(f"Unsupported database URL scheme: {scheme}")


def main():
    parser = argparse.ArgumentParser(description="Backup, restore, or verify the Terminal Frontier database.")
    parser.add_argument("action", choices=["backup", "restore", "verify"])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--file", type=Path, help="Backup file for backup/restore actions.")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive restore operation.")
    args = parser.parse_args()

    kind = database_kind(args.database_url)

    if args.action in {"backup", "restore"} and not args.file:
        parser.error("--file is required for backup and restore")
    if args.action == "restore" and not args.yes:
        parser.error("restore is destructive; pass --yes to confirm")

    if kind == "sqlite":
        if args.action == "backup":
            backup_sqlite(args.database_url, args.file)
        elif args.action == "restore":
            restore_sqlite(args.database_url, args.file)
        else:
            verify_sqlite(args.database_url)
    else:
        if args.action == "backup":
            backup_postgres(args.database_url, args.file)
        elif args.action == "restore":
            restore_postgres(args.database_url, args.file)
        else:
            verify_postgres(args.database_url)

    print(f"{args.action} {kind}: ok")


if __name__ == "__main__":
    main()
