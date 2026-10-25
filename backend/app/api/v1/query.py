"""Natural language query endpoint stub (implemented in Phase 5)."""

from fastapi import APIRouter

from app.core.errors import FeatureNotImplemented
from app.schemas.errors import ErrorEnvelope
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(tags=["Query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=200,
    summary="Execute Natural Language Query (Implemented in Phase 5)",
    description=(
        "Translates natural language questions into safe SQL, validates via AST policy engine, "
        "executes under the restricted dq_readonly role, and returns tabular results with an explanation.\n\n"
        "**Pipeline Status: Implemented in Phase 5.** In Phase 3, this endpoint validates "
        "the incoming request schema and returns HTTP 501 NOT_IMPLEMENTED using the standard error envelope."
    ),
    responses={
        200: {
            "description": "Query executed successfully and explanation generated.",
            "model": QueryResponse,
        },
        400: {
            "description": "Query failed security validation or is outside domain scope.",
            "model": ErrorEnvelope,
        },
        422: {
            "description": "Request validation failed (blank, too short, or too long question).",
            "model": ErrorEnvelope,
        },
        501: {
            "description": "Intentional Phase 3 stub: full pipeline implemented in Phase 5.",
            "model": ErrorEnvelope,
        },
    },
)
def execute_query(payload: QueryRequest) -> QueryResponse:
    """Validate query input and return intentional 501 stub."""
    raise FeatureNotImplemented(
        message="The natural language query execution pipeline will be implemented in Phase 5.",
        details={"question": payload.question, "pipeline_stage": "Phase 5"},
    )
