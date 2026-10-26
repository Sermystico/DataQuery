"""0002 query history table and role permissions

Revision ID: 0002_query_history
Revises: 0001_initial_schema
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_query_history"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create table app.query_history
    op.create_table(
        "query_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        schema="app",
    )

    op.create_index("ix_query_history_created_at", "query_history", ["created_at"], schema="app")
    op.create_index("ix_query_history_request_id", "query_history", ["request_id"], schema="app")

    # 2. Grant permissions: dq_app has INSERT and SELECT only. dq_readonly is explicitly barred.
    op.execute("GRANT INSERT, SELECT ON TABLE app.query_history TO dq_app;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO dq_app;")
    op.execute("REVOKE ALL ON TABLE app.query_history FROM dq_readonly;")


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE app.query_history FROM dq_app;")
    op.drop_index("ix_query_history_request_id", table_name="query_history", schema="app")
    op.drop_index("ix_query_history_created_at", table_name="query_history", schema="app")
    op.drop_table("query_history", schema="app")
