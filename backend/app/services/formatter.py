"""Data result formatting and chart recommendation service for DataQuery.

================================================================================
DECIMAL CONVERSION POLICY & PRECISION RATIONALE:
================================================================================
PostgreSQL drivers (psycopg) return arbitrary-precision `decimal.Decimal` objects
for NUMERIC/DECIMAL SQL types. However:
1. RFC 8259 (JSON specification) has no native Decimal data type.
2. Web browsers and frontend charting libraries (Recharts, Chart.js, Vega-Lite)
   expect native numerical floats for mathematical axes and series scaling.
3. Converting `Decimal` to Python `float` preserves double-precision floating point
   (53 bits of significand, ~15-17 significant decimal digits), which comfortably
   exceeds e-commerce financial totals without rounding error.
4. If exact sub-penny accounting auditing were required, strings would be mandated;
   for business intelligence dashboards and visualization, `float` is the optimal choice.
================================================================================
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.schemas.query import ChartHint


def format_value(val: Any) -> Any:
    """Convert raw database types into standardized, JSON-serializable Python types."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, (int, float, bool, str)):
        return val
    return str(val)


def format_rows(raw_rows: list[list[Any]]) -> list[list[Any]]:
    """Format all rows and columns to ensure complete JSON safety."""
    return [[format_value(val) for val in row] for row in raw_rows]


def _is_column_numeric(values: list[Any]) -> bool:
    """Check if all non-null values in a column are numbers."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return False
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null)


def _is_column_date(col_name: str, values: list[Any]) -> bool:
    """Check if a column represents a date, month, or timestamp."""
    name_lower = col_name.lower()
    if any(k in name_lower for k in ("date", "month", "year", "day", "time")):
        return True
    non_null = [v for v in values if v is not None]
    if not non_null:
        return False
    # Check if string values match ISO-8601 date formats (YYYY-MM-DD or YYYY-MM)
    date_regex = re.compile(r"^\d{4}-\d{2}(-\d{2})?")
    return all(isinstance(v, str) and bool(date_regex.match(v)) for v in non_null)


def _is_column_text(col_name: str, values: list[Any]) -> bool:
    """Check if a column contains text labels (and is not a date)."""
    if _is_column_date(col_name, values):
        return False
    non_null = [v for v in values if v is not None]
    if not non_null:
        return False
    return all(isinstance(v, str) for v in non_null)


def generate_chart_hint(columns: list[str], rows: list[list[Any]]) -> ChartHint:
    """Determine visual chart layout based on column types, row counts, and strict precedence.

    Rules & Precedence:
    1. Line Chart:
       First column is a date/month AND there is at least one numeric column.
    2. Bar Chart:
       Otherwise, when there is exactly 1 text column + 1 numeric column AND <= 20 rows.
    3. None:
       All other shapes (scalar values, wide tables, >20 rows with text, missing columns).
    """
    if not columns or not rows:
        return ChartHint(type="none", x_key=None, y_key=None)

    col_values: list[list[Any]] = [
        [row[i] for row in rows if i < len(row)] for i in range(len(columns))
    ]

    is_num = [_is_column_numeric(vals) for vals in col_values]
    is_dt = [_is_column_date(columns[i], vals) for i, vals in enumerate(col_values)]
    is_txt = [_is_column_text(columns[i], vals) for i, vals in enumerate(col_values)]

    # Rule 1 (Precedence 1): Line chart when first column is date/month and there is a numeric column
    if is_dt[0]:
        for j in range(1, len(columns)):
            if is_num[j]:
                return ChartHint(type="line", x_key=columns[0], y_key=columns[j])

    # Rule 2 (Precedence 2): Bar chart when 1 text column + 1 numeric column and <= 20 rows
    if len(rows) <= 20 and len(columns) == 2:
        if is_txt[0] and is_num[1]:
            return ChartHint(type="bar", x_key=columns[0], y_key=columns[1])
        if is_txt[1] and is_num[0]:
            return ChartHint(type="bar", x_key=columns[1], y_key=columns[0])

    # Rule 3: Otherwise none
    return ChartHint(type="none", x_key=None, y_key=None)


def format_result(
    columns: list[str],
    raw_rows: list[list[Any]],
) -> tuple[list[list[Any]], ChartHint]:
    """Format raw database query outputs into JSON-safe rows and compute visualization hints."""
    formatted = format_rows(raw_rows)
    hint = generate_chart_hint(columns, formatted)
    return formatted, hint
