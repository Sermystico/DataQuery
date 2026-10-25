"""Database seed loader for DataQuery.

Loads the deterministic synthetic dataset into the database using the dq_owner role.
- Checks if existing data is present.
- Wipes tables in FK-safe reverse order.
- Loads customers, products, orders, order_items, payments.
- Resets primary key ID sequences.
- Idempotent and deterministic.
"""

import os
import sys
from datetime import date

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg
from psycopg import sql

from app.core.config import get_settings
from seed.dataset import generate_dataset


def get_existing_row_counts(conn: psycopg.Connection) -> dict[str, int]:
    """Return dictionary of row counts for all analytics tables."""
    tables = ["payments", "order_items", "orders", "products", "customers"]
    counts = {}
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(t)))
            counts[t] = cur.fetchone()[0]
    return counts


def wipe_tables_fk_safe(conn: psycopg.Connection) -> None:
    """Wipe tables in strict foreign-key safe reverse order."""
    tables = ["payments", "order_items", "orders", "products", "customers"]
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(sql.SQL("DELETE FROM {};").format(sql.Identifier(t)))
    print("Existing table data wiped in FK-safe order.")


def load_seed_data(force: bool = False) -> dict[str, int]:
    """Load generated synthetic dataset into PostgreSQL database."""
    settings = get_settings()

    # Parse as_of reference date from settings or default to 2024-11-01
    as_of_str = settings.ANALYTICS_AS_OF_DATE.split("T")[0]
    as_of_date = date.fromisoformat(as_of_str)

    print(f"Generating deterministic dataset (seed=42, as_of={as_of_date})...")
    data = generate_dataset(seed=42, as_of=as_of_date)

    print(
        f"Connecting to {settings.DB_HOST}:{settings.DB_PORT}/{settings.POSTGRES_DB} as {settings.POSTGRES_OWNER_USER}..."
    )
    with psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_OWNER_USER,
        password=settings.POSTGRES_OWNER_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        autocommit=False,
    ) as conn:
        counts = get_existing_row_counts(conn)
        total_existing = sum(counts.values())

        if total_existing > 0:
            if not force:
                raise RuntimeError(
                    f"Target database is not empty ({total_existing} existing rows found: {counts}). "
                    "Pass force=True / --force to confirm wiping existing data."
                )
            wipe_tables_fk_safe(conn)

        with conn.cursor() as cur:
            # 1. Insert Customers
            cur.executemany(
                """
                INSERT INTO customers (id, name, email, region, signup_date)
                VALUES (%(id)s, %(name)s, %(email)s, %(region)s, %(signup_date)s);
                """,
                data["customers"],
            )

            # 2. Insert Products
            cur.executemany(
                """
                INSERT INTO products (id, name, category, unit_price)
                VALUES (%(id)s, %(name)s, %(category)s, %(unit_price)s);
                """,
                data["products"],
            )

            # 3. Insert Orders
            cur.executemany(
                """
                INSERT INTO orders (id, customer_id, order_date, status)
                VALUES (%(id)s, %(customer_id)s, %(order_date)s, %(status)s);
                """,
                data["orders"],
            )

            # 4. Insert Order Items
            cur.executemany(
                """
                INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
                VALUES (%(id)s, %(order_id)s, %(product_id)s, %(quantity)s, %(unit_price)s);
                """,
                data["order_items"],
            )

            # 5. Insert Payments
            cur.executemany(
                """
                INSERT INTO payments (id, order_id, amount, method, status, paid_at)
                VALUES (%(id)s, %(order_id)s, %(amount)s, %(method)s, %(status)s, %(paid_at)s);
                """,
                data["payments"],
            )

            # 6. Reset Primary Key Sequences
            tables_to_sync = ["customers", "products", "orders", "order_items", "payments"]
            for tbl in tables_to_sync:
                cur.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence({tbl_name}, 'id'), COALESCE(MAX(id), 1)) FROM {tbl};"
                    ).format(
                        tbl_name=sql.Literal(tbl),
                        tbl=sql.Identifier(tbl),
                    )
                )

        conn.commit()

    loaded_counts = {k: len(v) for k, v in data.items()}
    print(f"Seed dataset loaded successfully: {loaded_counts}")
    return loaded_counts


if __name__ == "__main__":
    force_wipe = "--force" in sys.argv
    try:
        load_seed_data(force=force_wipe)
    except Exception as e:
        print(f"Error loading seed data: {e}", file=sys.stderr)
        sys.exit(1)
