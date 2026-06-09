# Wiki update trigger
"""
main.py — Application entry point.
Sets up FastAPI, CORS, WebSocket, mounts routers, and starts the heartbeat.
All business logic lives in: config.py, database.py, game_helpers.py,
                              heartbeat.py, routes_auth.py, routes_agent.py, routes_world.py
"""
import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select, func, text
import logging.handlers
import psutil
import time
from collections import defaultdict, deque
from datetime import datetime

from models import Base, GlobalState, WorldHex
from database import engine, SessionLocal, refresh_station_cache
import heartbeat as hb

# Routers
from routes import auth, perception, agent_meta, intent, economy, missions, social, world, corp, admin, arena, debug
from logic.events import event_manager
from observability import record_rate_limit_bucket_count, record_rate_limit_rejection, record_slow_request

from contextlib import asynccontextmanager

# ─────────────────────────────────────────────────────────────────────────────
# App Setup & Lifespan
# ─────────────────────────────────────────────────────────────────────────────
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Persistent Logging Setup
log_file = os.getenv("LOG_FILE", "app.log")
if log_file:
    try:
        handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    except OSError as exc:
        root_logger.warning("File logging disabled; could not open %s: %s", log_file, exc)

# Console logging remains for convenience
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger("heartbeat")

async def monitor_resources():
    """Background task to log RAM and CPU usage every minute."""
    process = psutil.Process(os.getpid())
    while True:
        try:
            mem_info = process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            cpu_usage = psutil.cpu_percent(interval=None)
            sys_mem = psutil.virtual_memory()
            
            log_msg = f"[RESOURCES] Process RAM: {rss_mb:.2f} MB | CPU: {cpu_usage}% | System RAM: {sys_mem.percent}% used"
            
            if sys_mem.percent > 90:
                logger.warning(f"CRITICAL: System Memory usage is extremely high! ({sys_mem.percent}%)")
            
            logger.info(log_msg)
        except Exception as e:
            logger.error(f"Error in resource monitor: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    from models import Base
    from seed_world import seed_world
    from sqlalchemy import text
    
    Base.metadata.create_all(engine)
    
    with engine.connect() as conn:
        
        # Tag existing pitfighters if they aren't tagged yet
        try:
            conn.execute(text("UPDATE agents SET is_pitfighter = TRUE WHERE name LIKE '%-PitFighter'"))
            # HEAL: Also fix any Pit Fighters with 0 max_health from broken season resets
            conn.execute(text("UPDATE agents SET max_health = 100, health = 50 WHERE is_pitfighter = TRUE AND max_health <= 0"))
            conn.commit()
            # Tag existing guests
            conn.execute(text("UPDATE agents SET owner = 'guest' WHERE user_email LIKE '%@local.test' AND owner = 'player'"))
            conn.commit()
            logger.info("Migration: Tagged and Healed existing Pit Fighters.")
        except Exception:
            pass # Table or column might not exist yet if migrations failed

        is_postgres = engine.dialect.name == "postgresql"
        runtime_migrations = [
            ("bounties", "claimed_by", "INTEGER"),
            ("bounties", "claim_tick", "BIGINT"),
            ("agent_state", "is_banned", "BOOLEAN DEFAULT FALSE"),
            ("agent_state", "muted_until", "TIMESTAMP"),
            ("agent_state", "moderation_note", "VARCHAR"),
        ]
        for table_name, column_name, column_type in runtime_migrations:
            if is_postgres:
                migration_sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
            else:
                migration_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            try:
                conn.execute(text(migration_sql))
                conn.commit()
                logger.info(f"Runtime migration ensured: {table_name}.{column_name}")
            except Exception as e:
                conn.rollback()
                err_str = str(e).lower()
                if "duplicate column" not in err_str and "already exists" not in err_str:
                    logger.warning(f"Runtime migration skipped for {table_name}.{column_name}: {e}")

        # ─── CRITICAL PERFORMANCE INDEXES ─────────────────────────────────────
        # Missing indexes causing full-table-scans and 2+ second API responses
        perf_indexes = [
            ("idx_audit_agent_time", "audit_logs", "agent_id, time DESC"),
            ("idx_audit_event_type", "audit_logs", "event_type"),
            ("idx_inventory_agent", "inventory_items", "agent_id"),
            ("idx_intents_agent", "intents", "agent_id"),
            ("idx_intents_tick", "intents", "tick_index"),
            ("idx_agent_state_pitfighter", "agent_state", "is_pitfighter"),
            ("idx_agent_state_bot", "agent_state", "is_bot, is_feral"),
            ("idx_messages_timestamp", "agent_messages", "timestamp DESC"),
            ("idx_messages_channel", "agent_messages", "channel, timestamp DESC"),
        ]
        is_postgres = engine.dialect.name == "postgresql"
        index_conn = conn.execution_options(isolation_level="AUTOCOMMIT") if is_postgres else conn
        for index_name, table_name, columns in perf_indexes:
            concurrently = "CONCURRENTLY " if is_postgres else ""
            idx_sql = f"CREATE INDEX {concurrently}IF NOT EXISTS {index_name} ON {table_name} ({columns})"
            try:
                index_conn.execute(text(idx_sql))
                logger.info(f"Performance index ensured: {index_name}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation skipped: {e}")
        if not is_postgres:
            conn.commit()
        # ──────────────────────────────────────────────────────────────────────

    with SessionLocal() as db:
        hex_count = db.execute(select(func.count(WorldHex.id))).scalar()

    if hex_count == 0:
        logger.info("World empty. Seeding for first time...")
        seed_world()
    else:
        logger.info(f"World already seeded ({hex_count} hexes). Skipping auto-seed.")

    try:
        # 1. Sync station cache
        refresh_station_cache()

        # Inject the shared WebSocket manager into heartbeat module
        hb.manager = event_manager
        asyncio.create_task(hb.heartbeat_loop())
        
        # Start Leaderboard Generation loop - Non-blocking background task
        async def _safe_leaderboard_init():
            logger.info("[INIT] Waiting 15s for database/heartbeat to stabilize before leaderboard init...")
            await asyncio.sleep(15)
            try:
                from logic.leaderboard_manager import start_leaderboard_loop
                logger.info("[INIT] Starting leaderboard background loop...")
                await start_leaderboard_loop()
            except Exception as e:
                msg = f"[INIT] CRITICAL Leaderboard task error: {e}"
                logger.error(msg)
                with open("startup_error.log", "a") as f:
                    f.write(f"{datetime.now()}: {msg}\n")

        asyncio.create_task(_safe_leaderboard_init())
        asyncio.create_task(monitor_resources())
        
        yield
    except Exception as e:
        import traceback
        error_msg = f"FATAL LIFESPAN ERROR: {e}\n{traceback.format_exc()}"
        logger.error(error_msg)
        with open("startup_error.log", "a") as f:
            f.write(f"{datetime.now()}: {error_msg}\n")
        raise e
    # Shutdown logic (if any) could go here

# Load version from centralized json
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version_file = os.path.join(base_dir, "version.json")
try:
    with open(version_file, "r") as f:
        import json
        VERSION = json.load(f).get("version", "0.7.8")
except:
    VERSION = "0.7.8"

app = FastAPI(
    title="TERMINAL FRONTIER API",
    description="Backend API for Terminal Frontier agent-centric industrial RPG",
    version=VERSION,
    lifespan=lifespan
)

# Strict CORS for production, more relaxed for local dev
allowed_origins = [
    "https://terminal-frontier.pixek.xyz",
    "https://auth.terminal-frontier.pixek.xyz",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if os.getenv("ENVIRONMENT") == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-API-KEY", "X-API-Key"],
)

_rate_limit_windows = defaultdict(deque)
_rate_limits = [
    (("/auth/login", "/auth/guest", "/auth/rotate_key"), 20, 60),
    (("/api/intent",), 60, 60),
    (("/api/chat",), 90, 60),
    (("/state", "/api/my_agent", "/api/perception", "/api/agent_logs", "/api/market"), 180, 60),
]


def _rate_limit_for_path(path: str):
    for prefixes, max_requests, window_seconds in _rate_limits:
        if any(path.startswith(prefix) for prefix in prefixes):
            return max_requests, window_seconds
    return None


@app.middleware("http")
async def rate_limit_requests(request: Request, call_next):
    limit = _rate_limit_for_path(request.url.path)
    if not limit or os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false":
        return await call_next(request)

    max_requests, window_seconds = limit
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
    api_key = request.headers.get("x-api-key", "")
    identity = api_key or client_ip
    bucket_key = (identity, request.url.path)
    now = time.monotonic()
    bucket = _rate_limit_windows[bucket_key]

    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    record_rate_limit_bucket_count(sum(1 for active_bucket in _rate_limit_windows.values() if active_bucket))

    if len(bucket) >= max_requests:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        from fastapi.responses import JSONResponse
        record_rate_limit_rejection(request.url.path)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded."},
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    started_at = time.monotonic()
    try:
        response = await call_next(request)
        record_slow_request(
            request.method,
            request.url.path,
            time.monotonic() - started_at,
            response.status_code,
        )
        
        # ── Security Headers ──
        # Inject HSTS and other headers, primarily for HTTPS
        if request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # ── Cache Bashing for API Routes ──
        # Prevents CDNs (Cloudflare) or Browsers from caching the tick/state,
        # which was causing a 1-2 minute UI delay (6 ticks lag).
        if request.url.path.startswith("/api") or request.url.path == "/state":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
    except Exception as e:
        import traceback
        logger.error(f"CRASH in {request.method} {request.url.path}: {str(e)}")
        logger.error(traceback.format_exc())
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": "Internal server crash"})

# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Standard upgrade
    token = websocket.query_params.get("token")
    if not token:
        try:
            await websocket.accept()
            await websocket.close(code=4001)
        except Exception:
            pass
        return

    from database import SessionLocal
    from models import Agent
    from sqlalchemy import select

    with SessionLocal() as db:
        agent = db.execute(select(Agent).where(Agent.api_key == token)).scalar_one_or_none()
        if not agent:
            try:
                await websocket.accept()
                await websocket.close(code=4001)
            except Exception:
                pass
            return
        agent_id = agent.id

    await event_manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)
    except Exception:
        event_manager.disconnect(websocket)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────
from routes import perception, world, economy, agent_meta, auth, social, missions, arena, admin, corp, contracts, wiki

app.include_router(auth.router)
app.include_router(perception.router)
app.include_router(agent_meta.router)
app.include_router(intent.router)
app.include_router(economy.router)
app.include_router(missions.router)
app.include_router(social.router)
app.include_router(world.router)
app.include_router(corp.router)
app.include_router(admin.router)
app.include_router(arena.router)
app.include_router(contracts.router)
app.include_router(wiki.router)

if os.getenv("ENVIRONMENT") != "production":
    app.include_router(debug.router)

# ─────────────────────────────────────────────────────────────────────────────
# Auth Debug Endpoint
# ─────────────────────────────────────────────────────────────────────────────
if os.getenv("ENVIRONMENT") != "production":
    @app.get("/api/debug/auth", tags=["System"])
    async def debug_auth(request: Request):
        """Diagnose Origin and Auth headers for local dev friction."""
        return {
            "origin": request.headers.get("origin"),
            "host": request.headers.get("host"),
            "referer": request.headers.get("referer"),
            "env": os.getenv("ENVIRONMENT", "development"),
            "allowed_origins": allowed_origins if os.getenv("ENVIRONMENT") == "production" else "*"
        }


# ─────────────────────────────────────────────────────────────────────────────
# Health Check (used by Docker HEALTHCHECK)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health_check():
    """Readiness probe for HTTP, database, schema, and heartbeat freshness."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            hex_count = db.execute(select(func.count(WorldHex.id))).scalar() or 0
            state = db.execute(select(GlobalState)).scalars().first()
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "error", "database": str(e)})

    if not state:
        raise HTTPException(status_code=503, detail={"status": "error", "heartbeat": "missing"})

    updated_at = state.updated_at
    heartbeat_age = None
    if updated_at:
        now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.utcnow()
        heartbeat_age = max(0.0, (now - updated_at).total_seconds())

    max_heartbeat_age = int(os.getenv("HEALTH_MAX_HEARTBEAT_AGE_SECONDS", "180"))
    if heartbeat_age is not None and heartbeat_age > max_heartbeat_age:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "heartbeat": "stale",
                "heartbeat_age_seconds": heartbeat_age,
                "max_heartbeat_age_seconds": max_heartbeat_age,
            },
        )

    return {
        "status": "ok",
        "database": "ok",
        "world_hexes": hex_count,
        "heartbeat": {
            "tick": state.tick_index,
            "phase": state.phase,
            "age_seconds": heartbeat_age,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GDD Page
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/gdd")
async def get_gdd_page():
    gdd_path = os.path.join(os.getcwd(), "docs", "GDD.md")
    if not os.path.exists(gdd_path):
        return HTMLResponse("<h1>GDD Not Found</h1>", status_code=404)
    with open(gdd_path, "r", encoding="utf-8") as f:
        content = f.read()
    safe_content = content.replace("`", "\\`").replace("${", "\\${")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terminal Frontier: GDD</title>
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            :root {{ --bg: #050507; --accent: #38bdf8; --text: #cbd5e1; --panel: #0f172a; }}
            body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 40px; line-height: 1.6; }}
            .container {{ max-width: 900px; margin: 0 auto; background: var(--panel); padding: 60px; border-radius: 24px; border: 1px solid #1e293b; box-shadow: 0 25px 50px -12px rgba(0,0,0,.5); }}
            h1, h2, h3, h4 {{ font-family: 'Orbitron', sans-serif; color: var(--accent); letter-spacing: .1em; margin-top: 2em; }}
            h1 {{ border-bottom: 2px solid var(--accent); padding-bottom: 10px; margin-top: 0; }}
            code {{ background: #000; padding: 2px 6px; border-radius: 4px; color: #fca5a5; }}
            pre {{ background: #000; padding: 20px; border-radius: 12px; overflow-x: auto; border: 1px solid #334155; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #334155; padding: 12px; text-align: left; }}
            th {{ background: #1e293b; }}
            a {{ color: var(--accent); text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <a href="/" style="font-family:Orbitron,sans-serif;font-size:10px;color:#475569">&larr; Return to Dashboard</a>
        <div class="container" id="content"></div>
        <script>document.getElementById('content').innerHTML = marked.parse(`{safe_content}`);</script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ─────────────────────────────────────────────────────────────────────────────
# Static Frontend
# ─────────────────────────────────────────────────────────────────────────────
# Look for frontend in /frontend (Docker mount) or ../frontend (Local)
if os.path.exists("/frontend"):
    frontend_path = "/frontend"
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_path = os.path.join(base_dir, "frontend")

logger.info(f"Frontend path resolved to: {frontend_path} (Exists: {os.path.exists(frontend_path)})")

if os.path.exists(frontend_path):
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        fav = os.path.join(frontend_path, "favicon.ico")
        if os.path.exists(fav):
            return FileResponse(fav)
        return HTMLResponse(content="", status_code=204)

    @app.get("/dashboard")
    async def get_dashboard():
        resp = FileResponse(os.path.join(frontend_path, "index.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/about")
    async def get_about():
        return FileResponse(os.path.join(frontend_path, "about.html"))

    @app.get("/admin", include_in_schema=False)
    async def get_admin_dashboard():
        resp = FileResponse(os.path.join(frontend_path, "admin.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/api/metadata")
    async def get_metadata():
        return {
            "version": VERSION,
            "features": ["continuous_mining", "pilot_console_compat", "enhanced_ui"]
        }

    @app.get("/")
    async def read_index():
        resp = FileResponse(os.path.join(frontend_path, "index.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    app.mount("/", StaticFiles(directory=frontend_path), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to the Terminal Frontier API",
            "status": "online",
            "version": "0.9.7",
            "note": f"Frontend directory not found at {frontend_path}."
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
