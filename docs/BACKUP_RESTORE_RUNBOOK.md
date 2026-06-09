# Backup And Restore Runbook

Use `scripts/backup_restore.py` for launch backups and restore drills. Always test a restore into a disposable database before trusting a backup.

## SQLite Local Smoke

```powershell
& 'C:\Users\cosmi\AppData\Local\Python\bin\python.exe' scripts\backup_restore.py backup --database-url "sqlite:///tmp/local_server.db" --file "tmp/backups/local_server.db"
& 'C:\Users\cosmi\AppData\Local\Python\bin\python.exe' scripts\backup_restore.py verify --database-url "sqlite:///tmp/backups/local_server.db"
& 'C:\Users\cosmi\AppData\Local\Python\bin\python.exe' scripts\backup_restore.py restore --database-url "sqlite:///tmp/restore_drill.db" --file "tmp/backups/local_server.db" --yes
& 'C:\Users\cosmi\AppData\Local\Python\bin\python.exe' scripts\backup_restore.py verify --database-url "sqlite:///tmp/restore_drill.db"
```

## PostgreSQL Production

Run these from a machine with `pg_dump`, `pg_restore`, and `psql` installed and network access to the production database.

```bash
python scripts/backup_restore.py backup --database-url "$DATABASE_URL" --file "backups/terminal_frontier_$(date -u +%Y%m%dT%H%M%SZ).dump"
python scripts/backup_restore.py verify --database-url "$DATABASE_URL"
python scripts/backup_restore.py restore --database-url "$RESTORE_DRILL_DATABASE_URL" --file "backups/terminal_frontier_YYYYMMDDTHHMMSSZ.dump" --yes
python scripts/backup_restore.py verify --database-url "$RESTORE_DRILL_DATABASE_URL"
```

Never run `restore` against production unless you are intentionally performing disaster recovery and have taken a fresh backup first.
