"""Pydantic schemas for database catalog inspection and schema context."""

from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """Schema descriptor for a single database column."""

    name: str = Field(..., description="Column identifier", examples=["region"])
    type: str = Field(..., description="SQL data type", examples=["TEXT"])
    primary_key: bool = Field(default=False, description="Whether this column is a primary key")
    nullable: bool = Field(default=False, description="Whether null values are permitted")
    description: str = Field(default="", description="Human-readable business explanation")
    references: str | None = Field(
        default=None,
        description="Foreign key target in 'table.column' format if applicable",
        examples=["customers.id"],
    )


class TableSchema(BaseModel):
    """Schema descriptor for an analytics database table."""

    name: str = Field(..., description="Table name", examples=["customers"])
    description: str = Field(..., description="Table business domain summary")
    columns: list[ColumnSchema] = Field(
        default_factory=list,
        description="Ordered list of column definitions",
    )


class SchemaResponse(BaseModel):
    """Complete schema context response returned by the schema explorer endpoint."""

    database: str = Field(..., description="Database identifier", examples=["dataquery_dev"])
    as_of_date: str = Field(
        ...,
        description="Canonical analytical reference date (ISO-8601)",
        examples=["2024-11-01T00:00:00Z"],
    )
    tables: list[TableSchema] = Field(
        default_factory=list,
        description="Allowed business analytics tables",
    )
    business_definitions: dict[str, str] = Field(
        default_factory=dict,
        description="Standardized domain metric formulas and rules",
    )
