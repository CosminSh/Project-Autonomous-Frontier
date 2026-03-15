# Shipping & Maintenance Guide

This document serves as a checklist for deploying updates and performing maintenance on the **Terminal Frontier** project.

## 🔒 Security & Secrets
*   **NEVER** hardcode API keys or credentials in diagnostic scripts or source code.
*   Always use `.env` files for local development secrets.
*   Ensure `.env` is included in `.gitignore` (which it is in this project).
*   For diagnostic scripts, use `python-dotenv` or manual `.env` parsing to retrieve keys.

## 🚀 Frontend Deployment (Cache Busting)
When pushing updates to `renderer.js`, `ui.js`, or other frontend modules, ensure you perform **Full Cache Busting**.

1.  **Update index.html**: Bump the version in the meta comment and the CSS link.
2.  **Update app.js**: Update the version strings in the `import` statements at the top of the file.
    *   *Note*: Modules are imported with `?v=X.X.X`. If you don't bump these, the browser will likely serve a cached, broken version of the logic.
3.  **Mandatory Hard Refresh**: Users often need to press `Ctrl + F5` (or `Cmd + Shift + R`) to clear their browser's local script cache even after a version bump.

> [!IMPORTANT]
> **Current Version: 0.5.6**
> If you see `app.js?v=0.5.2` in the browser console while `ui.js` is `v=0.5.5`, the UI will CRASH. Ensure `app.js` is bumped together with all modules.

## 🐳 Backend Operations (Docker)
All database scripts and seeding commands **MUST** be run inside the running backend container on the cloud server.

### Running Scripts
To run a script like `seed_world.py`:
```bash
docker exec -it project-autonomous-frontier_backend_1 python seed_world.py
```

### Feral Recovery (Magnetic Pole Bug)
If ferals converge at (0,0) due to distance calculation errors, run:
```bash
docker exec -it project-autonomous-frontier_backend_1 python scripts/fix_feral_positions.py
```

### Database Integrity
Before running a world reset:
*   Ensure the script includes a **Migration Block** to handle the strict PostgreSQL transaction requirements.
*   Always use `conn.rollback()` if a column check fails, otherwise Postgres will block all subsequent queries in that session.

### 🏢 Guilds & Upgrades Migration
The system uses "Safe Startup Migrations" in `backend/main.py`. These run automatically whenever the backend starts.
*   **Columns handled**: `daily_missions.reward_xp`, `corporations.upgrades`, `agents.corp_role`, etc.
*   **Action Required**: Simply restart the backend service.
*   **Alembic**: Not strictly required for these small updates as they are handled by the startup block.

### 🛠️ Manual Migration (If Auto-Migration Fails)
If you need to force a migration or check for missing columns manually:
```bash
docker exec -it project-autonomous-frontier_backend_1 python scripts/migrate_db.py
```
*Note: The script is designed to be idempotent and handles PostgreSQL transaction rollbacks automatically.*

## 🔄 Live Reset Workflow
1.  **Git Pull** on the host.
2.  `docker-compose up -d --build` (to sync code changes).
3.  `docker exec ... python seed_world.py` (to update world layout).
4.  `docker-compose restart backend` (to refresh the station cache).

## 📱 Mobile Interaction Model
The map now uses a **Unified Interaction Model** (v0.5.3+).
*   **One Tap**: Select hex/object (updates scanner).
*   **Double Tap**: Open context menu.
*   **Right Click**: Select + Open menu (PC shortcut).
