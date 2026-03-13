# Shipping & Maintenance Guide

This document serves as a checklist for deploying updates and performing maintenance on the **Terminal Frontier** project.

## 🚀 Frontend Deployment (Cache Busting)
When pushing updates to `renderer.js`, `ui.js`, or other frontend modules, ensure you perform **Full Cache Busting**.

1.  **Update index.html**: Bump the version in the meta comment and the CSS link.
2.  **Update app.js**: Update the version strings in the `import` statements at the top of the file.
    *   *Note*: Modules are imported with `?v=X.X.X`. If you don't bump these, the browser will likely serve a cached, broken version of the logic.

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
