"""Repository for managing application query execution history in the 'app' schema.

Uses the application engine (dq_app role) with strictly bound SQL parameters.
Ensures history-write failures do not interrupt customer query responses.
"""

from typing import Any

import sqlalchemy as sa

from app.core.logging import get_logger
from app.db.engines import app_engine

logger = get_logger("app.db.history_repo")


def record_query_history(
    request_id: str,
    question: str,
    status: str,
    sql: str | None = None,
    row_count: int | None = None,
    error_code: str | None = None,
    duration_ms: float | None = None,
) -> int | None:
    """Record an analytics query outcome into app.query_history using dq_app engine.

    Never stores result rows, secrets, or API keys.
    Truncates question to 500 characters.
    Returns the generated history ID, or None if logging failed.
    """
    safe_question = question[:500] if question else ""

    stmt = sa.text(
        """
        INSERT INTO app.query_history (
            request_id, question, status, sql, row_count, error_code, duration_ms
        ) VALUES (
            :request_id, :question, :status, :sql, :row_count, :error_code, :duration_ms
        ) RETURNING id;
        """
    )

    try:
        with app_engine.connect() as conn:
            with conn.begin():
                result = conn.execute(
                    stmt,
                    {
                        "request_id": request_id,
                        "question": safe_question,
                        "status": status,
                        "sql": sql,
                        "row_count": row_count,
                        "error_code": error_code,
                        "duration_ms": duration_ms,
                    },
                )
                row = result.fetchone()
                if row:
                    return int(row[0])
    except Exception as ex:
        # History write failure must NEVER break user requests
        logger.error(
            "[request_id=%s] Failed to record query history in app.query_history: %s",
            request_id,
            ex,
        )
        return None

    return None


def get_query_history(
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Retrieve paginated query history records, sorted newest first."""
    clamped_limit = max(1, min(limit, 100))
    clamped_offset = max(0, offset)

    count_stmt = sa.text("SELECT COUNT(*) FROM app.query_history;")
    select_stmt = sa.text(
        """
        SELECT id, request_id, created_at, question, status, sql, row_count, error_code, duration_ms
        FROM app.query_history
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset;
        """
    )

    with app_engine.connect() as conn:
        total = conn.execute(count_stmt).scalar() or 0
        rows = (
            conn.execute(
                select_stmt,
                {"limit": clamped_limit, "offset": clamped_offset},
            )
            .mappings()
            .all()
        )

        items = [dict(row) for row in rows]
        return items, int(total)


def get_query_history_by_id(history_id: int) -> dict[str, Any] | None:
    """Retrieve a single query history record by its primary key."""
    stmt = sa.text(
        """
        SELECT id, request_id, created_at, question, status, sql, row_count, error_code, duration_ms
        FROM app.query_history
        WHERE id = :id;
        """
    )

    with app_engine.connect() as conn:
        row = conn.execute(stmt, {"id": history_id}).mappings().first()
        return dict(row) if row else None
