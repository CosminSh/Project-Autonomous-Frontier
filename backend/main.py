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
from routes_auth import router as auth_router
from routes_agent import router as agent_router
from routes_world import router as world_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heartbeat")

# ─────────────────────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TERMINAL FRONTIER API",
    description="Backend API for Terminal Frontier agent-centric industrial RPG",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    try:
        response = await call_next(request)
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response
    except Exception as e:
        import traceback
        logger.error(f"CRASH in {request.method} {request.url.path}: {str(e)}")
        logger.error(traceback.format_exc())
        raise e


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                continue


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(world_router)


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    from models import Base
    from seed_world import seed_world

    logger.info("Initializing database...")
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if db.execute(select(func.count(WorldHex.id))).scalar() == 0:
            logger.info("World empty. Seeding...")
            seed_world()
        else:
            logger.info("World already seeded.")

    refresh_station_cache()

    # Inject the shared WebSocket manager into heartbeat module
    hb.manager = manager

    asyncio.create_task(hb.heartbeat_loop())


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
    @app.get("/dashboard")
    async def get_dashboard():
        return FileResponse(os.path.join(frontend_path, "dashboard.html"))

    @app.get("/about")
    async def get_about():
        return FileResponse(os.path.join(frontend_path, "about.html"))

    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    app.mount("/", StaticFiles(directory=frontend_path), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to the Terminal Frontier API",
            "status": "online",
            "version": "0.1.3",
            "note": f"Frontend directory not found at {frontend_path}."
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
