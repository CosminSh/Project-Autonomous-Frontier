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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heartbeat")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    from models import Base
    from seed_world import seed_world
    from sqlalchemy import text
    
    Base.metadata.create_all(engine)
    
    # Safe column migrations: add new columns to existing tables without dropping data.
    # We use a robust try-except approach to handle different DB backends.
    safe_migrations = [
        ("agents", "health", "INTEGER DEFAULT 100"),
        ("agents", "max_health", "INTEGER DEFAULT 100"),
        ("agents", "energy", "INTEGER DEFAULT 100"),
        ("agents", "armor", "INTEGER DEFAULT 5"),
        ("agents", "damage", "INTEGER DEFAULT 10"),
        ("agents", "accuracy", "INTEGER DEFAULT 15"),
        ("agents", "overclock", "INTEGER DEFAULT 10"),
        ("agents", "max_mass", "FLOAT DEFAULT 100.0"),
        ("agents", "storage_capacity", "FLOAT DEFAULT 500.0"),
        ("agents", "last_daily_reward", "DATETIME"),
        ("agents", "is_pitfighter", "BOOLEAN DEFAULT FALSE"),
        ("agents", "is_aggressive", "BOOLEAN DEFAULT FALSE"),
        ("agents", "wear_and_tear", "FLOAT DEFAULT 0.0"),
        ("agents", "overclock_ticks", "INTEGER DEFAULT 0"),
        ("agents", "heat", "INTEGER DEFAULT 0"),
        ("agents", "unlocked_recipes", "JSON"),
        ("agents", "squad_id", "INTEGER"),
        ("agents", "pending_squad_invite", "INTEGER"),
        ("agents", "corporation_id", "INTEGER"),
        ("agents", "last_faction_change_tick", "INTEGER DEFAULT 0"),
        ("agents", "last_attacked_tick", "INTEGER DEFAULT 0"),
        ("agents", "is_in_anarchy_zone", "BOOLEAN DEFAULT FALSE"),
        ("agents", "arena_losses", "INTEGER DEFAULT 0"),
        ("arena_profiles", "daily_opponents", "JSON"),
        ("agents", "mining_yield", "INTEGER DEFAULT 10"),
        ("agents", "experience", "INTEGER DEFAULT 0"),
        ("agents", "level", "INTEGER DEFAULT 1"),
        ("agents", "speed", "INTEGER DEFAULT 10"),
        ("world_hexes", "resource_quantity", "INTEGER DEFAULT 0"),
        ("world_hexes", "expires_tick", "BIGINT"),
        ("global_state", "actions_processed", "INTEGER DEFAULT 0"),
        ("bounties", "claimed_by", "INTEGER REFERENCES agents(id)"),
        ("bounties", "claim_tick", "BIGINT"),
        ("bounties", "created_at", "DATETIME"),
        ("auction_house", "created_at", "DATETIME"),
        ("market_pickups", "created_at", "DATETIME"),
        ("intents", "created_at", "DATETIME"),
        ("daily_missions", "created_at", "DATETIME"),
        ("daily_missions", "reward_xp", "INTEGER DEFAULT 100"),
        ("corporations", "created_at", "DATETIME"),
        ("corporations", "vault_capacity", "FLOAT DEFAULT 5000.0"),
        ("corporations", "credit_vault", "INTEGER DEFAULT 0"),
        ("corporations", "tax_rate", "FLOAT DEFAULT 0.0"),
        ("api_key_revocations", "revoked_at", "DATETIME"),
        ("agents", "corp_role", "VARCHAR DEFAULT 'MEMBER'"),
        ("corporations", "join_policy", "VARCHAR DEFAULT 'OPEN'"),
        ("corporations", "motd", "TEXT"),
        ("corporations", "upgrades", "JSON"),
    ]
    
    with engine.connect() as conn:
        for table, col, col_type in safe_migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Migration: Added column {col} to {table}.")
            except Exception as e:
                # IMPORTANT for Postgres: Rollback the failed statement so the transaction can continue
                conn.rollback()
                err_str = str(e).lower()
                if "duplicate column" in err_str or "already exists" in err_str:
                    logger.debug(f"Migration: Column {col} already exists in {table}.")
                else:
                    logger.error(f"CRITICAL MIGRATION ERROR on {table}.{col}: {e}")
                    # In a real production environment, we might want to raise here
                    # raise e 
        
        # Tag existing pitfighters if they aren't tagged yet
        try:
            conn.execute(text("UPDATE agents SET is_pitfighter = TRUE WHERE name LIKE '%-PitFighter'"))
            conn.commit()
            logger.info("Migration: Tagged existing Pit Fighters.")
        except Exception:
            pass # Table or column might not exist yet if migrations failed

    with SessionLocal() as db:
        hex_count = db.execute(select(func.count(WorldHex.id))).scalar()

    if hex_count == 0:
        logger.info("World empty. Seeding for first time...")
        seed_world()
    else:
        logger.info(f"World already seeded ({hex_count} hexes). Skipping auto-seed.")

    refresh_station_cache()

    # Inject the shared WebSocket manager into heartbeat module
    hb.manager = event_manager
    asyncio.create_task(hb.heartbeat_loop())
    
    # Start Leaderboard Generation loop - Non-blocking background task
    async def _safe_leaderboard_init():
        try:
            from logic.leaderboard_manager import start_leaderboard_loop, generate_leaderboards
            with SessionLocal() as db_lb:
                generate_leaderboards(db_lb) # Initial generation
            await start_leaderboard_loop()
        except Exception as e:
            logger.error(f"Leaderboard task error: {e}")

    asyncio.create_task(_safe_leaderboard_init())
    
    yield
    # Shutdown logic (if any) could go here

app = FastAPI(
    title="TERMINAL FRONTIER API",
    description="Backend API for Terminal Frontier agent-centric industrial RPG",
    version="0.1.0",
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
        await websocket.accept() # Accept to send close code properly
        await websocket.close(code=4001)
        return

    from database import SessionLocal
    from models import Agent
    from sqlalchemy import select

    with SessionLocal() as db:
        agent = db.execute(select(Agent).where(Agent.api_key == token)).scalar_one_or_none()
        if not agent:
            await websocket.accept()
            await websocket.close(code=4001)
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
            "version": "0.2.2",
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
            "version": "0.1.4",
            "note": f"Frontend directory not found at {frontend_path}."
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
