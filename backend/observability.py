from collections import Counter, deque
from datetime import datetime, timedelta, timezone
import time

import psutil
from sqlalchemy import func, select

from models import AuditLog, GlobalState


SLOW_REQUEST_THRESHOLD_SECONDS = 1.0
SLOW_REQUESTS = deque(maxlen=100)
RATE_LIMIT_REJECTIONS = Counter()
RATE_LIMIT_ACTIVE_BUCKETS = 0


def record_slow_request(method: str, path: str, duration_seconds: float, status_code: int | None):
    if duration_seconds < SLOW_REQUEST_THRESHOLD_SECONDS:
        return
    SLOW_REQUESTS.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "path": path,
        "duration_ms": round(duration_seconds * 1000, 2),
        "status_code": status_code,
    })


def record_rate_limit_rejection(path: str):
    RATE_LIMIT_REJECTIONS[path] += 1


def record_rate_limit_bucket_count(count: int):
    global RATE_LIMIT_ACTIVE_BUCKETS
    RATE_LIMIT_ACTIVE_BUCKETS = count


def build_metrics_snapshot(db, *, engine, event_manager):
    process = psutil.Process()
    memory = process.memory_info()
    state = db.execute(select(GlobalState)).scalars().first()
    now = datetime.now(timezone.utc)
    heartbeat_updated_at = None
    heartbeat_age_seconds = None
    if state and state.updated_at:
        heartbeat_updated_at = state.updated_at
        if heartbeat_updated_at.tzinfo is None:
            heartbeat_updated_at = heartbeat_updated_at.replace(tzinfo=timezone.utc)
        heartbeat_age_seconds = max(0, int((now - heartbeat_updated_at).total_seconds()))

    since = now - timedelta(hours=1)
    failed_intents = db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.time >= since,
            AuditLog.event_type.like("%FAILED%"),
        )
    ).scalar() or 0
    heartbeat_errors = db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.time >= since,
            AuditLog.event_type.in_(["HEARTBEAT_ERROR", "TICK_ERROR"]),
        )
    ).scalar() or 0

    return {
        "status": "ok",
        "generated_at": now.isoformat(),
        "tick": state.tick_index if state else 0,
        "phase": state.phase if state else None,
        "heartbeat": {
            "updated_at": heartbeat_updated_at.isoformat() if heartbeat_updated_at else None,
            "age_seconds": heartbeat_age_seconds,
            "healthy": heartbeat_age_seconds is not None and heartbeat_age_seconds < 120,
        },
        "simulation": {
            "actions_processed_total": state.actions_processed if state and state.actions_processed else 0,
            "failed_intents_last_hour": failed_intents,
            "heartbeat_errors_last_hour": heartbeat_errors,
        },
        "http": {
            "slow_request_threshold_ms": int(SLOW_REQUEST_THRESHOLD_SECONDS * 1000),
            "recent_slow_requests": list(SLOW_REQUESTS),
            "rate_limit_rejections": dict(RATE_LIMIT_REJECTIONS),
            "active_rate_limit_buckets": RATE_LIMIT_ACTIVE_BUCKETS,
        },
        "websocket": {
            "active_connections": len(event_manager.active_connections),
        },
        "database": {
            "dialect": engine.dialect.name,
            "pool": engine.pool.status() if hasattr(engine.pool, "status") else str(engine.pool),
        },
        "process": {
            "memory_rss_mb": round(memory.rss / (1024 * 1024), 2),
            "memory_vms_mb": round(memory.vms / (1024 * 1024), 2),
            "cpu_percent": process.cpu_percent(interval=None),
            "uptime_seconds": int(time.time() - process.create_time()),
        },
    }
