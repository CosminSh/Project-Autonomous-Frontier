# Terminal Frontier Launch Readiness Issues

Last reviewed: 2026-06-10

This file tracks the launch blockers and missing work found during repository analysis. Items marked confirmed were verified against the current worktree or with local commands. Items marked needs verification are plausible risks that still need runtime or browser confirmation.

## Confirmed Launch Blockers

- [x] Root Docker deployment is broken: the root `Dockerfile` starts `uvicorn backend.main:app`, but backend modules import `models`, `database`, and other modules as top-level imports. Importing `backend.main` from the repository root currently fails with `ModuleNotFoundError: No module named 'models'`.
- [x] Runtime dependencies are inconsistent: root `requirements.txt` is missing backend dependencies such as `psutil`; backend webhook code imports `aiohttp`, but `backend/requirements.txt` does not declare it.
- [x] Deployment secrets are unsafe in defaults/config examples: `docker-compose.yml` contains `POSTGRES_PASSWORD=password`, a database URL with `admin:password`, and a placeholder admin key. `backend/routes/admin.py` also defaults to `change-me-in-production`.
- [x] Frontend WebSocket auth is broken: `frontend/api.js` reads `sv_token`, but auth stores `sv_api_key`.
- [x] Market UI response shape is inconsistent: `/api/market` returns `qty`, while multiple frontend render paths use `quantity`.
- [x] Market buy form sends `price` for BUY intents, while the backend buy handler expects `max_price`.
- [x] Market order adjustment uses `POST` in the frontend while the backend exposes `PATCH /api/market/orders/{order_id}`.
- [x] Contract UI and backend schemas do not match. The frontend posts `type`, `item`, and `target_station_id`, while the backend expects `contract_type`, `item_type`, `target_station_q`, and `target_station_r`. The frontend also renders fields the backend does not return.
- [x] Mission dashboard response shape is inconsistent: the backend returns `type`, `target`, and `progress`; the dashboard renders `title`, `current_quantity`, and `required_quantity`.
- [x] `frontend/ui.js` defined `updateMissionsUI` twice, so the stale later renderer overrode the schema-aligned renderer and tried to turn in missions through a queued `TURN_IN` intent. The stale override was removed, and pytest now guards that the frontend uses the current mission schema and `game.api.turnInMission`.
- [x] Webhook settings do not match: frontend posts JSON `{webhook_url}`, while backend expects a query parameter named `url`.
- [x] Test tooling is incomplete: `/api/wiki/manual` is fixed, and `requirements-dev.txt` now declares `pytest` plus backend requirements.
- [x] Browser smoke found guest login returned 422 because `frontend/auth.js` posted `/auth/guest` without a JSON body.
- [x] Import-time file logging could crash tests or deployments when `app.log` was locked or not writable. `LOG_FILE` now controls the path, and file logging is skipped if the handler cannot be opened.
- [x] Lifetime performance stat updates called `flag_modified` on the `Agent` association proxy instead of the progression row, causing SQLAlchemy errors during flush.
- [x] `/dashboard` served a non-existent `frontend/dashboard.html`; it now serves the current `index.html` entry point with no-cache headers.

## Security And Operations

- [x] Require a real `ADMIN_KEY` in production and fail startup or skip admin routes if it is missing.
- [x] Gate or remove always-mounted `/api/debug/auth` in production.
- [x] Add production rate limiting for auth, intent, chat, and high-volume read endpoints.
- [x] Gate guest login in production or constrain it with strict rate limits and lifecycle cleanup. Production guest login is now disabled unless `ALLOW_GUEST_LOGIN=true` is explicitly set.
- [x] Audit frontend `innerHTML` render paths for player-controlled data: names, corp names, contracts, chat, logs, and market data. Toasts, telemetry chat/log entries, terminal output, storage rows, contract cards, market rows/depth, arena gear/logs, bounties, missions, leaderboards, squad members, navigation signatures, and corporation roster/invites/MOTD now escape or sanitize player-controlled content. Remaining `innerHTML` use is either static UI copy, server-defined recipe/wiki/config content, or pre-sanitized terminal output.
- [x] Validate webhook URLs beyond `https://` to reduce SSRF risk. The server now rejects local/private IP targets, local hostnames, embedded credentials, non-443 ports, control characters, and overlong URLs.
- [x] Add health checks that verify database connectivity, heartbeat freshness, and migration/schema readiness, not only HTTP liveness.
- [x] Add backup/restore verification for the production database. `scripts/backup_restore.py` supports SQLite backup/restore/verify locally and PostgreSQL backup/restore/verify through `pg_dump`, `pg_restore`, and `psql`; `docs/BACKUP_RESTORE_RUNBOOK.md` documents the restore drill, and pytest verifies a SQLite backup/restore integrity cycle.

## Missing Or Incomplete Launch Features

- [x] Automated market sniping/trader tooling is listed as planned in the GDD but was not implemented beyond a read-only starter script. `agent_toolkit/example_trader.py` now provides a dry-run-first trader scanner with capped BUY execution, and `bot_client.py` includes market depth, buy/sell, adjust, cancel, and pickup helpers covered by pytest.
- [x] Player contracts need tests. Cancellation, expiry refunds, station validation, fulfillment, unsupported types, and normalized response schema are covered by pytest.
- [x] Replace browser-loaded Tailwind CDN before production launch. Tailwind is now generated locally through `npm run build:css`, `frontend/tailwind.generated.css` is referenced by active HTML entry points, and pytest guards against reintroducing the CDN.
- [ ] Mayday webhook needs real outbound end-to-end verification with a Discord/Slack URL. Local coverage now verifies settings URL validation, status endpoint shape, trigger payload posting, HTTP failure audit logging, unsafe stored URL skipping, and user-facing latest delivery status through `/api/settings/webhook/status` and `/api/my_agent`.
- [x] New player onboarding needs a verified happy path: guest/tutorial/login, mine, smelt, craft/equip, sell/claim, and repair. `tests/test_onboarding_happy_path.py` now creates a guest, verifies starter gear, mines, smelts, crafts/equips `SCRAP_FRAME`, sells into a BUY order, buys/claims a pickup at a MARKET, repairs at a REPAIR station, and confirms the authenticated agent endpoint.
- [x] Arena season reset needs a production-safe scheduler/runbook and audit trail if it is not externally automated. Resets are now idempotent per UTC ISO week, write global and per-fighter audit logs, can be manually triggered through `/api/admin/arena/reset_season`, and are documented in `docs/ARENA_OPERATIONS_RUNBOOK.md`.
- [x] Moderation/admin tools need production workflows: user lookup, mute/ban, economy correction, forced rescue, and audit review. Admin endpoints and `/admin` dashboard now cover these workflows, with ban enforcement in API-key auth and mute enforcement in chat.
- [x] Observability needs launch dashboards for tick duration, failed intents, DB pool health, websocket counts, heartbeat errors, slow endpoints, and memory. `/api/admin/metrics` plus `/admin` now expose heartbeat freshness, processed/failed actions, websocket count, rate-limit pressure, DB pool status, slow requests, memory, CPU, and uptime.
- [x] The official agent toolkit should be validated against the current API routes and response schemas. Contract and corporation helper methods now match current backend routes, and pytest covers the generated requests.

## Code Quality And Maintainability

- [ ] Large frontend files should be split after blockers are fixed: `frontend/ui.js`, `frontend/index.html`, `frontend/renderer.js`, and `frontend/terminal.js`. The terminal command registry was moved to `frontend/terminal-commands.js`; shared escaping helpers were moved to `frontend/ui-utils.js`; private log rendering was moved to `frontend/ui-logs.js`; market listings, depth, trade controls, and order list rendering were moved to `frontend/ui-market.js`; and mojibake in visible `ui.js` icon/status/reward text was normalized to ASCII. The remaining large UI, renderer, and HTML files still need a broader decomposition pass.
- [x] Add API schema tests so frontend expectations cannot drift from backend responses. Player contract, mission alias, wiki/manual, auth hardening, webhook, toolkit mapping, command-reference, market, agent, storage, corp, admin metrics, and arena response bodies are now covered.
- [ ] Add browser smoke coverage for login/guest, world view, terminal commands, market, missions, contracts, corp, arena, and wiki. The in-app browser runtime is available again, and foreground Uvicorn startup was healthy. A browser session rendered the local app shell with the terminal and webhook status present, but authenticated smoke coverage remains blocked because detached Uvicorn processes exit before opening `127.0.0.1:8001`, and a Node-spawned Python server cannot open SQLite database files in this desktop environment. I am not certain whether the hidden guest button seen in that partially initialized browser session is a frontend state issue or an artifact of the blocked server/session setup; API and `TestClient` guest flows are covered separately.
- [x] Align `/api/commands`, terminal help, GDD, and the actual intent/API handlers. Stale `FIELD_TRADE` and `ARENA_REGISTER` terminal commands were removed, refueler bots now queue `TRANSFER`, `/api/commands` distinguishes immediate endpoint commands, `/api/wiki/commands` is projected from the live command reference, terminal examples match current recipe IDs, and the GDD market/arena command references now match current routes and config.
- [x] Remove or archive stale demo files that shadow current app behavior and security posture. Tracked legacy demo entry points `backend/scripts/demo_app.py`, `backend/scripts/main_demo.py`, and `frontend/old_index.html` were removed; ignored local demo artifacts were left alone.

## Verification Notes

- `python -m pytest tests -q` passed with 45 tests and the known SQLAlchemy deprecation warning plus a `.pytest_cache` warning. The command used `C:\Users\cosmi\AppData\Local\Python\bin\python.exe` because the Windows `python` app alias was inaccessible.
- `node --check` passed for main frontend JavaScript modules including `frontend/terminal-commands.js`, `frontend/ui-utils.js`, `frontend/ui-logs.js`, and `frontend/ui-market.js`; the inline script in `frontend/admin.html` previously parsed successfully with Node.
- `python -m compileall -q backend tests` passed.
- Importing `main` from the `backend` directory works with a test SQLite URL.
- Importing `backend.main` from the repository root fails.
- `/api/wiki/data`, `/api/wiki/commands`, and `/api/wiki/manual` return 200 under `TestClient` with a temporary SQLite file database.
- Browser smoke on `http://127.0.0.1:8001` verified guest login succeeds after cache-busting to frontend version `0.9.8`.
- `TF_BASE_URL=http://127.0.0.1:8001 python tests/integration_test_api.py` passed against the local server.
- Latest browser automation setup succeeded, and one local browser pass rendered the app shell with terminal and webhook status elements present. Full authenticated browser smoke remains blocked because detached Uvicorn processes exit before opening `127.0.0.1:8001`; foreground startup with the same command reached `Application startup complete` before the command timeout stopped it, and Node-spawned Python hit SQLite `unable to open database file` errors even for direct SQLite connection checks.
- `git diff --check` passed with CRLF normalization warnings only.
