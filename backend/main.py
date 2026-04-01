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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select, func
import logging.handlers
import psutil
import time
from datetime import datetime

from models import Base, WorldHex
from database import engine, SessionLocal, refresh_station_cache
import heartbeat as hb

# Routers
from routes import auth, perception, agent_meta, intent, economy, missions, social, world, corp, admin, arena, debug
from logic.events import event_manager

from contextlib import asynccontextmanager

# ─────────────────────────────────────────────────────────────────────────────
# App Setup & Lifespan
# ─────────────────────────────────────────────────────────────────────────────
# Persistent Logging Setup
log_file = "app.log"
handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

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

        # ─── CRITICAL PERFORMANCE INDEXES ─────────────────────────────────────
        # Missing indexes causing full-table-scans and 2+ second API responses
        perf_indexes = [
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_agent_time ON audit_logs (agent_id, time DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_event_type ON audit_logs (event_type)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_agent ON inventory_items (agent_id)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_intents_agent ON intents (agent_id)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_intents_tick ON intents (tick_index)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agents_pitfighter ON agents (is_pitfighter)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agents_bot ON agents (is_bot, is_feral)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_timestamp ON agent_messages (timestamp DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_channel ON agent_messages (channel, timestamp DESC)",
        ]
        for idx_sql in perf_indexes:
            try:
                # CONCURRENTLY requires autocommit=True (can't run in a transaction)
                conn.execute(text("COMMIT"))
                conn.execute(text(idx_sql))
                logger.info(f"Performance index ensured: {idx_sql.split('idx_')[1].split(' ')[0]}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation skipped: {e}")
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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-API-KEY", "X-API-Key"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    try:
        response = await call_next(request)
        
        # ── Security Headers ──
        # Inject HSTS and other headers, primarily for HTTPS
        if request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
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
    """Lightweight liveness probe. Returns 200 if server is responsive."""
    return {"status": "ok"}


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
        return FileResponse(os.path.join(frontend_path, "dashboard.html"))

    @app.get("/about")
    async def get_about():
        return FileResponse(os.path.join(frontend_path, "about.html"))

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
