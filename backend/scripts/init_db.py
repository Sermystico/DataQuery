"""Safe database initialization and bootstrap script for DataQuery.

Orchestrates container startup safely:
1. Waits for PostgreSQL database readiness.
2. Applies pending schema migrations (Alembic upgrade head).
3. Hardens permissions and provisions roles (bootstrap_roles).
4. Checks existing table counts: if empty, loads deterministic seed data.
   If data already exists, preserves it without wiping or dropping anything.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from scripts.bootstrap_roles import bootstrap_roles  # noqa: E402
from seed.load import get_existing_row_counts, load_seed_data  # noqa: E402


def wait_for_database(max_retries: int = 30, delay_sec: float = 1.0) -> None:
    """Poll database connection until ready or timeout."""
    settings = get_settings()
    print(f"Waiting for database at {settings.DB_HOST}:{settings.DB_PORT}/{settings.POSTGRES_DB}...")

    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg.connect(
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_OWNER_USER,
                password=settings.POSTGRES_OWNER_PASSWORD.get_secret_value(),
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                connect_timeout=3,
            )
            conn.close()
            print(f"Database connection verified (attempt {attempt}/{max_retries}).")
            return
        except Exception as ex:
            if attempt == max_retries:
                print(f"Failed to connect to database after {max_retries} attempts: {ex}")
                raise
            time.sleep(delay_sec)


def run_migrations() -> None:
    """Run Alembic migrations to upgrade database schema to head."""
    print("Running database migrations (Alembic upgrade head)...")
    alembic_ini = BACKEND_DIR / "alembic.ini"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"Migration error: {result.stderr}")
        raise RuntimeError(f"Alembic migration failed with code {result.returncode}: {result.stderr}")
    print(f"Migrations complete.\n{result.stdout.strip()}")


def safe_seed_load() -> None:
    """Load deterministic synthetic dataset if tables are currently empty."""
    settings = get_settings()
    with psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_OWNER_USER,
        password=settings.POSTGRES_OWNER_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    ) as conn:
        counts = get_existing_row_counts(conn)
        total_rows = sum(counts.values())

    if total_rows > 0:
        print(f"Existing dataset detected ({total_rows} total rows: {counts}). Skipping seed loading to preserve data.")
    else:
        print("Database is empty. Loading initial deterministic seed dataset...")
        loaded_counts = load_seed_data(force=False)
        print(f"Seed loading complete: {loaded_counts}")


def main() -> None:
    """Main entrypoint for safe database initialization."""
    print("=== DataQuery Safe Database Initialization Started ===")
    wait_for_database()
    run_migrations()
    print("Bootstrapping database roles and permissions...")
    bootstrap_roles()
    safe_seed_load()
    print("=== DataQuery Safe Database Initialization Succeeded ===")


if __name__ == "__main__":
    main()
