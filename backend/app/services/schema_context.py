"""Schema context service for DataQuery.

Provides the approved schema catalog and business domain definitions.
Constructed strictly from the centralized security policy allowlist rather
than introspecting PostgreSQL internal system catalogs.
"""

from app.core.config import get_settings
from app.schemas.schema import ColumnSchema, SchemaResponse, TableSchema
from app.security.policy import APPROVED_SCHEMA_METADATA, BUSINESS_DEFINITIONS


def get_schema_context() -> SchemaResponse:
    """Return the approved database schema and standardized business definitions."""
    settings = get_settings()

    tables: list[TableSchema] = []
    for table_name, table_meta in APPROVED_SCHEMA_METADATA.items():
        columns = [
            ColumnSchema(
                name=col["name"],
                type=col["type"],
                primary_key=col["primary_key"],
                nullable=col["nullable"],
                description=col["description"],
                references=col["references"],
            )
            for col in table_meta["columns"]
        ]
        tables.append(
            TableSchema(
                name=table_name,
                description=table_meta["description"],
                columns=columns,
            )
        )

    return SchemaResponse(
        database=settings.POSTGRES_DB,
        as_of_date=settings.ANALYTICS_AS_OF_DATE,
        tables=tables,
        business_definitions=BUSINESS_DEFINITIONS,
    )
