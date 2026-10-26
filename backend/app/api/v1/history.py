"""Query execution history endpoints."""

from fastapi import APIRouter, Path, Query

from app.core.errors import NotFound
from app.db.history_repo import get_query_history, get_query_history_by_id
from app.schemas.errors import ErrorEnvelope
from app.schemas.history import HistoryResponse, QueryHistoryItem

router = APIRouter(prefix="/history", tags=["History"])


@router.get(
    "",
    response_model=HistoryResponse,
    status_code=200,
    summary="List Query History",
    description=(
        "Retrieve a paginated list of historical analytics query executions, ordered newest first.\n\n"
        "Records execution metadata including question, status, generated SQL, row count, error codes, "
        "and latency. For security and privacy, raw result rows and credentials are never stored."
    ),
    responses={
        200: {
            "description": "Paginated historical records successfully retrieved.",
            "model": HistoryResponse,
        },
        422: {
            "description": "Invalid pagination parameters (limit out of bounds 1-100 or negative offset).",
            "model": ErrorEnvelope,
        },
    },
)
def list_history(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of query history records to return (1 to 100).",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of query history records to skip.",
    ),
) -> HistoryResponse:
    """List historical queries with pagination."""
    items, total = get_query_history(limit=limit, offset=offset)
    return HistoryResponse(
        items=[QueryHistoryItem.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id}",
    response_model=QueryHistoryItem,
    status_code=200,
    summary="Get Query History Item",
    description=(
        "Retrieve detailed execution metadata for a specific query history record by its primary key ID."
    ),
    responses={
        200: {
            "description": "Query history record details.",
            "model": QueryHistoryItem,
        },
        404: {
            "description": "Query history record with the specified ID was not found.",
            "model": ErrorEnvelope,
        },
        422: {
            "description": "Invalid query history ID parameter.",
            "model": ErrorEnvelope,
        },
    },
)
def get_history_item(
    id: int = Path(
        ...,
        ge=1,
        description="Unique primary key identifier of the query history entry.",
    ),
) -> QueryHistoryItem:
    """Retrieve details of a single query history record."""
    item = get_query_history_by_id(id)
    if item is None:
        raise NotFound(
            message=f"Query history record with id {id} not found.",
            details={"id": id},
        )
    return QueryHistoryItem.model_validate(item)
