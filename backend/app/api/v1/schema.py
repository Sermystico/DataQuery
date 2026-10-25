"""Schema context endpoint exposing approved database catalog."""

from fastapi import APIRouter

from app.schemas.schema import SchemaResponse
from app.services.schema_context import get_schema_context

router = APIRouter(tags=["Schema"])


@router.get(
    "/schema",
    response_model=SchemaResponse,
    summary="Analytics Database Schema Context",
    description=(
        "Returns the approved analytics database schema tables, columns, constraints, "
        "foreign keys, and standardized domain business definitions for the frontend Schema Explorer. "
        "Constructed strictly from the centralized security allowlist without introspecting system catalogs."
    ),
    responses={
        200: {
            "description": "Approved database schema metadata and domain definitions.",
            "model": SchemaResponse,
        },
    },
)
def get_schema() -> SchemaResponse:
    """Return approved analytics tables, columns, and metric definitions."""
    return get_schema_context()
