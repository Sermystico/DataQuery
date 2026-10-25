from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable
from app.core.logging import get_logger
from app.db.engines import get_readonly_conn
from app.schemas.errors import ErrorEnvelope
from app.schemas.health import HealthResponse

logger = get_logger("app.api.v1.health")

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Readiness Check",
    description=(
        "Verifies operational readiness of the FastAPI application and executes "
        "a live 'SELECT 1' test probe against PostgreSQL using the dq_readonly engine."
    ),
    responses={
        200: {
            "description": "Application and database are healthy and connected.",
            "model": HealthResponse,
        },
        503: {
            "description": "Database connectivity check failed.",
            "model": ErrorEnvelope,
        },
    },
)
def check_health(
    conn: Annotated[Connection, Depends(get_readonly_conn)],
) -> HealthResponse:
    """Execute live database probe and return service status."""
    try:
        conn.execute(sa.text("SELECT 1"))
    except Exception as ex:
        logger.error("Health check failed on database probe: %s", ex)
        raise DatabaseUnavailable(
            message="Database connectivity check failed.",
            details={"component": "database", "probe": "SELECT 1"},
        ) from ex

    settings = get_settings()
    return HealthResponse(
        status="ok",
        database="connected",
        version="1.0.0",
        as_of_date=settings.ANALYTICS_AS_OF_DATE,
    )
