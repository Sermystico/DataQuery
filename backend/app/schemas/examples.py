"""Pydantic schemas for curated example questions."""

from pydantic import BaseModel, Field


class ExampleQuestion(BaseModel):
    """A single curated example prompt."""

    title: str = Field(..., description="Short title for prompt card", examples=["Total Revenue"])
    question: str = Field(
        ...,
        description="Full natural language query string",
        examples=["What is the total revenue across all completed orders?"],
    )


class CategoryExamples(BaseModel):
    """A group of curated prompts belonging to an analytical category."""

    category: str = Field(
        ...,
        description="Category identifier slug",
        examples=["aggregation"],
    )
    title: str = Field(
        ...,
        description="Human-readable category title",
        examples=["Aggregations & Totals"],
    )
    description: str = Field(
        ...,
        description="Summary of query patterns in this category",
        examples=["Queries calculating sums, averages, and counts across business entities."],
    )
    examples: list[ExampleQuestion] = Field(
        default_factory=list,
        description="List of sample questions in this category",
    )


class ExamplesResponse(BaseModel):
    """Complete collection of curated example prompts."""

    total_count: int = Field(
        ...,
        description="Total number of example prompts returned across all categories",
        examples=[24],
    )
    categories: list[CategoryExamples] = Field(
        default_factory=list,
        description="Categorized example question sets",
    )
