FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project (including backend/ and frontend/)
COPY . .

# Set environment variables
ENV PORT=8001
ENV DATABASE_URL=sqlite:///./demo_cloud.db

# Start the application using the backend.main module
CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT
