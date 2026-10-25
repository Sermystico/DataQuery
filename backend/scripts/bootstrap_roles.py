"""Database role provisioning script for DataQuery.

Creates and configures the three-tier database role architecture:
1. dq_owner: Migration owner and schema administrator (pre-provisioned by container).
2. dq_readonly: Strictly limited to SELECT queries on approved analytics tables only.
3. dq_app: Limited to the internal 'app' schema for operational metadata.

Idempotent: safe to run multiple times.
"""

import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg
from psycopg import sql

from app.core.config import get_settings


def bootstrap_roles() -> None:
    settings = get_settings()
    db_name = settings.POSTGRES_DB
    owner_user = settings.POSTGRES_OWNER_USER
    readonly_user = settings.POSTGRES_READONLY_USER
    readonly_pw = settings.POSTGRES_READONLY_PASSWORD
    app_user = settings.POSTGRES_APP_USER
    app_pw = settings.POSTGRES_APP_PASSWORD
    timeout_ms = settings.QUERY_TIMEOUT_MS

    print(f"Connecting to {settings.DB_HOST}:{settings.DB_PORT}/{db_name} as {owner_user}...")
    with psycopg.connect(
        dbname=db_name,
        user=owner_user,
        password=settings.POSTGRES_OWNER_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            # ------------------------------------------------------------------
            # 1. Hardening PUBLIC permissions
            # ------------------------------------------------------------------
            # In PostgreSQL 15+, CREATE on schema public is revoked from PUBLIC,
            # but we explicitly enforce this to ensure no non-owner creates tables.
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC;")

            # ------------------------------------------------------------------
            # 2. Provision dq_readonly
            # ------------------------------------------------------------------
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (readonly_user,))
            if cur.fetchone() is None:
                print(f"Creating role '{readonly_user}'...")
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {role} WITH LOGIN PASSWORD {pw} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
                    ).format(
                        role=sql.Identifier(readonly_user),
                        pw=sql.Literal(readonly_pw),
                    )
                )
            else:
                print(f"Role '{readonly_user}' exists; updating password and attributes...")
                cur.execute(
                    sql.SQL(
                        "ALTER ROLE {role} WITH LOGIN PASSWORD {pw} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
                    ).format(
                        role=sql.Identifier(readonly_user),
                        pw=sql.Literal(readonly_pw),
                    )
                )

            # Strip all broad database privileges except CONNECT
            # Why: Ensures dq_readonly cannot create temporary tables or alter the database.
            cur.execute(
                sql.SQL("REVOKE ALL ON DATABASE {db} FROM {role};").format(
                    db=sql.Identifier(db_name),
                    role=sql.Identifier(readonly_user),
                )
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {db} TO {role};").format(
                    db=sql.Identifier(db_name),
                    role=sql.Identifier(readonly_user),
                )
            )

            # Public schema permissions:
            # Why: USAGE is required to resolve table names in 'public', but CREATE is revoked
            # so the role cannot create tables, functions, or views.
            cur.execute(
                sql.SQL("REVOKE ALL ON SCHEMA public FROM {role};").format(
                    role=sql.Identifier(readonly_user)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {role};").format(
                    role=sql.Identifier(readonly_user)
                )
            )

            # Table permissions:
            # Why: Start with a clean slate by revoking all privileges on public tables,
            # then grant SELECT exclusively on the 5 approved analytics tables.
            cur.execute(
                sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role};").format(
                    role=sql.Identifier(readonly_user)
                )
            )
            cur.execute(
                sql.SQL(
                    "GRANT SELECT ON customers, products, orders, order_items, payments TO {role};"
                ).format(role=sql.Identifier(readonly_user))
            )

            # Isolation from 'app' schema:
            # Why: dq_readonly must never see internal query history, tokens, or app telemetry.
            cur.execute(
                sql.SQL("REVOKE ALL ON SCHEMA app FROM {role};").format(
                    role=sql.Identifier(readonly_user)
                )
            )

            # Prevent default privilege leakage:
            # Why: Ensure any future tables created by dq_owner in public or app do NOT
            # automatically grant permissions to dq_readonly.
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public REVOKE ALL ON TABLES FROM {role};"
                ).format(
                    owner=sql.Identifier(owner_user),
                    role=sql.Identifier(readonly_user),
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app REVOKE ALL ON TABLES FROM {role};"
                ).format(
                    owner=sql.Identifier(owner_user),
                    role=sql.Identifier(readonly_user),
                )
            )

            # Role-level configuration constraints:
            # Why: Database-enforced read-only transaction state and statement timeout.
            # Even if an attacker bypasses application AST validation, PostgreSQL itself rejects mutations
            # and kills long-running queries exceeding QUERY_TIMEOUT_MS.
            cur.execute(
                sql.SQL("ALTER ROLE {role} SET default_transaction_read_only = on;").format(
                    role=sql.Identifier(readonly_user)
                )
            )
            cur.execute(
                sql.SQL("ALTER ROLE {role} SET statement_timeout = {timeout};").format(
                    role=sql.Identifier(readonly_user),
                    timeout=sql.Literal(f"{timeout_ms}ms"),
                )
            )

            # ------------------------------------------------------------------
            # 3. Provision dq_app
            # ------------------------------------------------------------------
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (app_user,))
            if cur.fetchone() is None:
                print(f"Creating role '{app_user}'...")
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {role} WITH LOGIN PASSWORD {pw} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
                    ).format(
                        role=sql.Identifier(app_user),
                        pw=sql.Literal(app_pw),
                    )
                )
            else:
                print(f"Role '{app_user}' exists; updating password and attributes...")
                cur.execute(
                    sql.SQL(
                        "ALTER ROLE {role} WITH LOGIN PASSWORD {pw} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
                    ).format(
                        role=sql.Identifier(app_user),
                        pw=sql.Literal(app_pw),
                    )
                )

            # Strip all database privileges except CONNECT
            cur.execute(
                sql.SQL("REVOKE ALL ON DATABASE {db} FROM {role};").format(
                    db=sql.Identifier(db_name),
                    role=sql.Identifier(app_user),
                )
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {db} TO {role};").format(
                    db=sql.Identifier(db_name),
                    role=sql.Identifier(app_user),
                )
            )

            # Public schema isolation:
            # Why: dq_app is the operational backend user for query logging, NOT analytics queries.
            # It has no access to customer analytics data.
            cur.execute(
                sql.SQL("REVOKE ALL ON SCHEMA public FROM {role};").format(
                    role=sql.Identifier(app_user)
                )
            )
            cur.execute(
                sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role};").format(
                    role=sql.Identifier(app_user)
                )
            )

            # 'app' schema access:
            # Why: Grant USAGE on schema app so dq_app can access tables placed there (e.g., query_history).
            # Do NOT grant CREATE on schema app (migrations run as dq_owner; dq_app cannot create DDL).
            cur.execute(
                sql.SQL("REVOKE ALL ON SCHEMA app FROM {role};").format(
                    role=sql.Identifier(app_user)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA app TO {role};").format(
                    role=sql.Identifier(app_user)
                )
            )

            # Default privileges:
            # Why: Prevent automatic privilege escalation on new tables.
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public REVOKE ALL ON TABLES FROM {role};"
                ).format(
                    owner=sql.Identifier(owner_user),
                    role=sql.Identifier(app_user),
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app REVOKE ALL ON TABLES FROM {role};"
                ).format(
                    owner=sql.Identifier(owner_user),
                    role=sql.Identifier(app_user),
                )
            )

    print("Database roles bootstrapped successfully.")


if __name__ == "__main__":
    try:
        bootstrap_roles()
    except Exception as e:
        print(f"Error bootstrapping roles: {e}", file=sys.stderr)
        sys.exit(1)
