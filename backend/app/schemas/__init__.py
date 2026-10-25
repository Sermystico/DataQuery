"""Pydantic schemas package for DataQuery API requests and responses."""

from app.schemas.errors import ErrorDetail, ErrorEnvelope
from app.schemas.examples import CategoryExamples, ExampleQuestion, ExamplesResponse
from app.schemas.health import HealthResponse
from app.schemas.history import HistoryItem, HistoryListResponse
from app.schemas.query import ChartHint, QueryRequest, QueryResponse
from app.schemas.schema import ColumnSchema, SchemaResponse, TableSchema
from app.schemas.sql import SQLValidateRequest, SQLValidateResponse

__all__ = [
    "CategoryExamples",
    "ChartHint",
    "ColumnSchema",
    "ErrorDetail",
    "ErrorEnvelope",
    "ExampleQuestion",
    "ExamplesResponse",
    "HealthResponse",
    "HistoryItem",
    "HistoryListResponse",
    "QueryRequest",
    "QueryResponse",
    "SQLValidateRequest",
    "SQLValidateResponse",
    "SchemaResponse",
    "TableSchema",
]
