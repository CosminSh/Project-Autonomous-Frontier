FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies and curl for the Docker healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the entire project (including backend/ and frontend/)
COPY . .

# Set environment variables
ENV PORT=8001
ENV DATABASE_URL=sqlite:///./demo_cloud.db
ENV PYTHONPATH=/app/backend

WORKDIR /app/backend

# Liveness probe: if the app hangs, Docker marks it unhealthy
# Requires: restart: on-failure in docker-compose (or --restart on-failure in docker run)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/health || exit 1

# Start with concurrency cap and short keep-alive to limit idle RAM usage
CMD uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --limit-concurrency 40 \
    --timeout-keep-alive 5
