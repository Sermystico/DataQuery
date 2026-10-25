"""Inspect database tables and schemas."""

import os

import psycopg
from dotenv import load_dotenv


def inspect() -> None:
    load_dotenv()
    with psycopg.connect(
        dbname=os.getenv("POSTGRES_DB", "dataquery_dev"),
        user=os.getenv("POSTGRES_OWNER_USER", "dq_owner"),
        password=os.getenv("POSTGRES_OWNER_PASSWORD", "dq_owner_dev_pw"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5434")),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name;
            """)
            schemas = cur.fetchall()
            print("User schemas found:")
            for s in schemas:
                print(f"  - {s[0]}")

            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name;
            """)
            tables = cur.fetchall()
            print(f"\nNon-system tables found: {len(tables)}")
            for schema, name in tables:
                print(f"  - {schema}.{name}")


if __name__ == "__main__":
    inspect()
