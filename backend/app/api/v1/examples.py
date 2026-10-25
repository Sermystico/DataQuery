"""Curated example questions endpoint."""

from fastapi import APIRouter

from app.schemas.examples import ExamplesResponse
from app.services.examples import get_curated_examples

router = APIRouter(tags=["Examples"])


@router.get(
    "/examples",
    response_model=ExamplesResponse,
    summary="Curated Example Prompts",
    description=(
        "Returns categorized natural language business questions covering aggregations, "
        "groupings, top-N rankings, date-based queries, filtering conditions, and table joins. "
        "All questions are verified to be answerable against the approved schema."
    ),
    responses={
        200: {
            "description": "Categorized sample questions for quick testing and UI discovery.",
            "model": ExamplesResponse,
        },
    },
)
def get_examples() -> ExamplesResponse:
    """Return categorized collection of sample natural language queries."""
    return get_curated_examples()
