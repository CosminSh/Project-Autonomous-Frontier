# Contributing to Terminal Frontier

First off, thank you for considering contributing to Terminal Frontier.

## Development Environment Setup

### 1. Requirements
- Python 3.10+
- PostgreSQL (or SQLite for local dev)
- Node.js (for frontend optional)
- Docker (optional but recommended)

### 2. Setting up the Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database Initialization
```bash
# We use Alembic for our database schema migrations.
cd backend
alembic upgrade head
python seed_world.py
```

### 4. Running the Dev Server
```bash
cd backend
python run_demo.py
# Or directly via uvicorn
uvicorn main:app --reload
```

## Branching & Commits
- Main development happens on the `main` branch. 
- Create feature branches: `git checkout -b feature/my-cool-feature`
- Pre-commit hygiene: check `.gitignore` to make sure you aren't committing `.db`, `.log` files.

## Testing
Please ensure any changes pass the integration tests. Note that integration tests use a local test sqlite database.
```bash
cd tests
python integration_test_api.py
```
