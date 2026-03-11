🔒 Security Audit: Terminal Frontier
I've reviewed your codebase and identified several security issues ranging from critical to medium. Here's the detailed assessment:

🔴 CRITICAL ISSUES
1. CORS Misconfiguration (Critical)
Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ ALLOWS EVERYONE
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
✅ **FIXED**: Restricted to specific domains + limited methods/headers.
Problem:

allow_origins=["*"] with allow_credentials=True is dangerous
Allows any website to make authenticated requests on behalf of users
Combined with API keys in headers = cross-site request forgery (CSRF) vulnerability
Risk: Malicious website can call /api/chat, /api/market, /api/intent as the user without their knowledge.

Fix:

Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://terminal-frontier.pixek.xyz", "http://localhost:3000"],  # Whitelist only
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Be specific
    allow_headers=["Content-Type", "Authorization"],  # Be specific
)
2. Hardcoded Default Database Credentials
Python
# From migrations/migrate.py & database.py
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@db:5432/terminal_frontier")
✅ **FIXED**: Hardcoded fallback removed; app now exits if env var is missing.
Problem:

Default username: admin
Default password: password
If environment variable not set, falls back to hardcoded weak credentials
Anyone who finds this in the code can access your database
Risk: Database breach, full data exfiltration.

Fix:

Python
import sys
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set!")
    sys.exit(1)
3. Debugging Routes Exposed in Production
From your imports in main.py:

Python
from routes import auth, perception, agent_meta, intent, economy, missions, social, world, corp, admin, arena, debug
✅ **FIXED**: Debug router is now conditionally included (skipped in production).
The debug router is mounted in production. This likely exposes:

Internal state information
Game logic internals
Possible admin endpoints
Risk: Information disclosure, potential administrative bypass.

Fix:

Python
# In main.py
if not os.getenv("ENVIRONMENT") == "production":
    app.include_router(debug.router)
4. Insecure SQL Migration Execution
Python
# From migrations/migrate.py
conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
✅ **FIXED**: Added proper error handling and re-raising for critical failures.
Problem:

Dynamic SQL construction (though table/col names come from code, not user input)
Errors are silently caught and passed
Could mask permission issues, making schema migrations fail silently
Risk: Schema inconsistencies, data loss.

Fix:

Python
try:
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
    conn.commit()
    logger.info(f"Migration: Added column {col} to {table}.")
except sqlalchemy.exc.ArgumentError as e:
    logger.error(f"CRITICAL: Migration failed for {col}: {e}")
    raise  # Don't swallow critical errors
except Exception as e:
    if "duplicate column" in str(e).lower():
        logger.debug(f"Column {col} already exists (expected).")
    else:
        logger.error(f"Unexpected error: {e}")
🟠 HIGH SEVERITY ISSUES
5. Rate Limiting Depends on Redis (No Fallback)
Python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    try:
        # ... rate limiting code ...
    except Exception:
        pass  # If Redis is down, don't block requests ← PROBLEM
✅ **FIXED**: Now "fails closed" (503 error) if Redis is unavailable.
Problem:

If Redis goes down, rate limiting is completely disabled
Attackers can perform unlimited requests (brute force, DDoS)
Risk: Denial of service, brute force attacks.

Fix:

Python
except Exception as e:
    logger.error(f"Rate limiter error: {e} - FAILING CLOSED")
    # Option 1: Block request
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": "Service unavailable"})
    
    # Option 2: Use in-memory fallback
    if client_ip not in memory_limit_tracker:
        memory_limit_tracker[client_ip] = {"count": 0, "reset_at": time.time() + RATE_LIMIT_WINDOW}
6. API Key Not Rotated on Account Changes
From routes/auth.py:

Python
@router.post("/auth/rotate_key")
async def rotate_api_key(agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    new_key = str(uuid.uuid4())
    agent.api_key = new_key
    db.commit()
✅ **FIXED**: Old key is now moved to `api_key_revocations` table during rotation.
Problem:

API key rotation works, but no audit log of which key was used when
If account is compromised, you don't know what damage was done
Old API key is immediately invalidated (good), but no revocation list
Risk: Unauthorized actions, no forensics.

Fix:

Python
class APIKeyRevocation(Base):
    __tablename__ = "api_key_revocations"
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    revoked_key = Column(String, unique=True)
    revoked_at = Column(DateTime(timezone=True), default=func.now())
    reason = Column(String)  # "rotation", "compromised", etc.

# On key rotation:
db.add(APIKeyRevocation(agent_id=agent.id, revoked_key=agent.api_key, reason="rotation"))
agent.api_key = new_key
db.commit()
7. Google OAuth Token Not Verified for Expiration
From routes/auth.py:

Python
idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
email = idinfo["email"]
✅ **FIXED**: Added check for `iat` (issued at) to reject tokens older than 1 hour.
Problem:

Google library handles verification, but no check for token age
If token is old (days/weeks), could be replayed
No aud (audience) validation beyond CLIENT_ID
Risk: Stale token reuse.

Fix:

Python
import time
idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)

# Verify token not too old (Google usually does this, but belt-and-suspenders)
token_age = time.time() - idinfo.get("iat", 0)
if token_age > 3600:  # Token older than 1 hour
    raise HTTPException(status_code=401, detail="Token expired")

email = idinfo["email"]
🟡 MEDIUM SEVERITY ISSUES
8. No Rate Limiting on Login Endpoint
Python
@router.post("/auth/login")
async def login(request: Request):
    # NO rate limiting, no brute force protection
Problem:

Attackers can brute force Google token verification
Even though Google tokens are hard to forge, the endpoint itself is unprotected
Risk: Brute force attacks.

Fix:

Python
@app.post("/auth/login")
async def login(request: Request):
    client_ip = request.client.host
    # Check rate limit for this IP's login attempts
    # Allow 5 attempts per minute
9. WebSocket Connections Not Authenticated
From main.py:

Python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)  # ← NO AUTH CHECK
✅ **FIXED**: Added mandatory API key verification via token query parameter.
    try:
        while True:
            await websocket.receive_text()
Problem:

Anyone can connect to /ws without authentication
Can listen to broadcasts meant only for authenticated players
Could spam fake events
Risk: Information leakage, chat hijacking.

Fix:

Python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    # Verify API key from query param
    db = SessionLocal()
    agent = db.execute(select(Agent).where(Agent.api_key == token)).scalar_one_or_none()
    if not agent:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await manager.connect(websocket, agent_id=agent.id)
10. No Input Validation on Chat Messages
Python
@router.post("/api/chat")
async def send_chat(req: ChatRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    message = req.message.strip()
    # ← Only checks if empty, no length limit, no XSS sanitization
✅ **FIXED**: Added Pydantic length validation (500 chars) and HTML entity escaping.
Problem:

Messages can be arbitrarily long (DoS vector)
No sanitization of special characters
If frontend renders as HTML, XSS possible
No rate limiting on chat messages
Risk: Denial of service, cross-site scripting, spam.

Fix:

Python
from html import escape
from pydantic import Field

class ChatRequest(BaseModel):
    channel: str = "GLOBAL"
    message: str = Field(..., min_length=1, max_length=500)  # Limit length

@router.post("/api/chat")
async def send_chat(req: ChatRequest, agent: Agent = Depends(verify_api_key), db: Session = Depends(get_db)):
    message = escape(req.message.strip())  # Sanitize HTML
    # Also add per-player chat rate limiting (e.g., 1 message per 2 seconds)
11. No HTTPS Enforcement
Python
# No security headers for HTTPS
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
✅ **FIXED**: Added middleware to inject HSTS, X-Frame, and X-Content headers.
Problem:

If deployed without HTTPS, API keys sent in plain text
No HSTS header to force HTTPS on return visits
Session hijacking possible
Risk: Man-in-the-middle attacks.

Fix:

Python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if not request.url.scheme == "http":  # Only on HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
12. No Protection Against Timestamp Manipulation
From combat/actions:

Python
target.last_attacked_tick = tick_count
Problem:

tick_count comes from server state but is readable from /api/global_stats
Client could theoretically manipulate timing (clock skew attacks)
No server-side verification
Risk: Timing-based exploits.

Fix:

Python
# Use server timestamp, not client-provided tick
target.last_attacked_tick = int(datetime.now(timezone.utc).timestamp())
🟢 LOW SEVERITY ISSUES
13. Verbose Error Messages
Python
except Exception as e:
    import traceback
    traceback.print_exc()
    return {"status": "error", "message": f"Server Error: {str(e)}"}
Problem:

Stack traces printed to console (leaked to logs)
Error messages contain internal implementation details
Could help attackers find vulnerabilities
Risk: Information disclosure.

Fix:

Python
except ValueError as e:
    logger.error(f"Login validation error: {e}")  # Log internally
    return {"status": "error", "message": "Invalid credentials"}  # Generic response
14. Missing Content-Type Validation
Python
data = await request.json()  # Trusts Content-Type header
Problem:

No explicit validation of Content-Type: application/json
Server assumes JSON but doesn't enforce it
Risk: Low, but could cause parsing errors.

Fix:

Python
if request.headers.get("content-type") != "application/json":
    raise HTTPException(status_code=400, detail="Invalid Content-Type")
15. No Audit Log for Sensitive Actions
Good: Some actions logged to AuditLog (COMBAT_HIT, MARKET_CANCEL, etc.)
Bad: Other sensitive actions missing (LOGIN, API_KEY_ROTATION, etc.)
✅ **FIXED**: Added audit logging for SUCCESSFUL_LOGIN and API_KEY_ROTATION.

Fix:

Python
@router.post("/auth/login")
async def login(request: Request):
    # ... after successful login ...
    with SessionLocal() as db:
        db.add(AuditLog(agent_id=agent.id, event_type="LOGIN", details={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": get_client_ip(request)
        }))
        db.commit()
📋 Priority Fix List
Priority	Issue	Effort	Impact
🔴 [DONE]	Fix CORS misconfiguration	5 min	Prevents CSRF attacks
🔴 [DONE]	Remove hardcoded DB credentials	10 min	Prevents DB breach
🔴 [DONE]	Disable debug routes in production	5 min	Prevents info disclosure
🟠 [DONE]	Fix rate limiter fallback	20 min	Prevents DDoS
🟠 [DONE]	Add API key revocation log	30 min	Improves forensics
� [DONE]	Insecure SQL Migrations	15 min	Prevents schema masks
🟠 [DONE]	Verify Google Token Age	10 min	Prevents replay attacks
🟡 [DONE]	Authenticate WebSockets	20 min	Prevents hijacking
🟡 [DONE]	Sanitize Chat Inputs	15 min	Prevents XSS
🟢 [DONE]	Add HTTPS / Security Headers	10 min	Improves defense
🟢 [DONE]	Audit Sensitive Actions	30 min	Improves forensics
🟡 P2	Add rate limiting to login	15 min	Prevents brute force
🎯 Immediate Actions (Do These First)
1: Fix CORS to whitelist only your domain
2: Move DB credentials to environment variables
3: Disable debug router in production
4: Rate limit login + fix redis fallback

Your code is generally well-structured, but these fixes will dramatically improve security. The CORS + hardcoded creds issues are critical because they'd allow attackers to compromise accounts and data.