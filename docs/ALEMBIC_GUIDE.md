# Alembic Database Migrations Guide

We are now using **Alembic** to manage database schema changes. This ensures that everyone working on the project (and the production server) stays in sync.

## Initial Setup (On Server)
If you haven't already, run the following to prepare the database:

1. **Pull the configuration**:
   ```bash
   git pull
   ```
2. **Mark the current state as "Baseline"**:
   Since your database already includes the `resource_quantity` column, we need to tell Alembic to "start from here" without trying to recreate existing tables.
   ```bash
   docker-compose exec backend alembic stamp head
   ```

## How to make changes to the Database
From now on, **never** manually run `ALTER TABLE` or update the database directly. Follow these steps:

1. **Modify `backend/models.py`**:
   Add your new columns, tables, or constraints as usual with SQLAlchemy.

2. **Generate a Migration Script**:
   Run this command to let Alembic detect the changes and write a script:
   ```bash
   docker-compose exec backend alembic revision --autogenerate -m "Describe your change here"
   ```
   *Note: This will create a new file in `backend/alembic/versions/`.*

3. **Review the Script**:
   It's always a good idea to check the generated file in `backend/alembic/versions/` to make sure it's doing exactly what you expect.

4. **Apply the Changes**:
   Run this to update the actual database:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

## Troubleshooting
- **Missing Columns**: If Alembic doesn't detect a change, make sure your new model is imported or referenced in `backend/models.py`.
- **Merge Conflicts**: If two people create migrations at the same time, you'll need to use `alembic merge` (I can help with that if it happens!).
