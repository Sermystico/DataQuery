"""Database connectivity verification script."""

import os
import sys

import psycopg
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    db_name = os.getenv("POSTGRES_DB", "dataquery_dev")
    user = os.getenv("POSTGRES_OWNER_USER", "dq_owner")
    password = os.getenv("POSTGRES_OWNER_PASSWORD", "dq_owner_dev_pw")
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))

    print(f"Attempting PostgreSQL connection to {host}:{port}/{db_name} as user '{user}'...")
    try:
        with psycopg.connect(
            dbname=db_name,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                pg_version = cur.fetchone()[0]
                cur.execute("SELECT current_user, current_database();")
                curr_user, curr_db = cur.fetchone()
                print("Connection SUCCESSFUL!")
                print(f"  PostgreSQL Version: {pg_version}")
                print(f"  Connected User:     {curr_user}")
                print(f"  Current Database:   {curr_db}")
        return 0
    except Exception as e:
        print(f"Connection FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
