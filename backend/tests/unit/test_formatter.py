"""Unit tests for formatter.py type conversions, JSON safety, and chart hint precedence."""

import json
from datetime import date, datetime
from decimal import Decimal

from app.services.formatter import (
    format_result,
    format_rows,
    format_value,
    generate_chart_hint,
)


class CustomObject:
    """Mock object for testing conversion of unknown/exotic types."""

    def __str__(self) -> str:
        return "custom_str_repr"


def test_format_value_decimal_to_float():
    """Decimal values are converted to float with double precision."""
    val = Decimal("123.456")
    res = format_value(val)
    assert isinstance(res, float)
    assert res == 123.456


def test_format_value_date_and_datetime_to_iso():
    """date and datetime objects are converted to ISO 8601 strings."""
    d = date(2024, 1, 15)
    dt = datetime(2024, 1, 15, 14, 30, 0)
    assert format_value(d) == "2024-01-15"
    assert format_value(dt) == "2024-01-15T14:30:00"


def test_format_value_none_preserved():
    """None is preserved for JSON null serialization."""
    assert format_value(None) is None


def test_format_value_primitives_preserved():
    """Standard primitives (int, float, bool, str) remain untouched."""
    assert format_value(42) == 42
    assert isinstance(format_value(42), int)
    assert format_value(3.14) == 3.14
    assert isinstance(format_value(3.14), float)
    assert format_value(True) is True
    assert format_value("hello") == "hello"


def test_format_value_unknown_types_converted_to_str():
    """Unknown types fall back to their string representations."""
    obj = CustomObject()
    res = format_value(obj)
    assert res == "custom_str_repr"
    assert isinstance(res, str)


def test_format_rows_json_serializable():
    """format_rows returns clean lists that serialize via standard json.dumps without error."""
    raw = [
        [Decimal("99.99"), date(2024, 3, 1), None, CustomObject()],
        [Decimal("150.00"), datetime(2024, 3, 2, 10, 0), "test", 123],
    ]
    formatted = format_rows(raw)
    json_str = json.dumps(formatted)
    assert "99.99" in json_str
    assert "2024-03-01" in json_str
    assert "null" in json_str
    assert "custom_str_repr" in json_str


def test_chart_hint_line_when_first_column_date_and_numeric_present():
    """Line chart hint is produced when first column is date/month and a numeric column exists."""
    cols = ["order_date", "daily_revenue"]
    rows = [
        ["2024-01-01", 1200.0],
        ["2024-01-02", 1550.0],
        ["2024-01-03", 980.0],
    ]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "line"
    assert hint.x_key == "order_date"
    assert hint.y_key == "daily_revenue"


def test_chart_hint_bar_when_one_text_one_numeric_and_under_20_rows():
    """Bar chart hint is produced when 1 text column + 1 numeric column and <= 20 rows."""
    cols = ["region", "total_revenue"]
    rows = [
        ["North America", 150000.0],
        ["EMEA", 120000.0],
        ["APAC", 95000.0],
    ]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "bar"
    assert hint.x_key == "region"
    assert hint.y_key == "total_revenue"


def test_chart_hint_bar_handles_numeric_first_column():
    """Bar chart properly maps text to x_key and numeric to y_key regardless of column order."""
    cols = ["total_revenue", "region"]
    rows = [
        [150000.0, "North America"],
        [120000.0, "EMEA"],
    ]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "bar"
    assert hint.x_key == "region"
    assert hint.y_key == "total_revenue"


def test_chart_hint_precedence_line_over_bar():
    """Precedence: When first col is date and second is numeric (even <= 20 rows), line takes precedence."""
    cols = ["month", "revenue"]
    rows = [
        ["2024-01", 50000.0],
        ["2024-02", 60000.0],
    ]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "line"
    assert hint.x_key == "month"
    assert hint.y_key == "revenue"


def test_chart_hint_none_when_bar_exceeds_20_rows():
    """If 1 text + 1 numeric has > 20 rows, chart hint must be none."""
    cols = ["product_name", "units_sold"]
    rows = [[f"Product {i}", float(i * 10)] for i in range(25)]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "none"
    assert hint.x_key is None
    assert hint.y_key is None


def test_chart_hint_none_for_scalar_single_cell():
    """Single scalar values (1 column, 1 row) produce none."""
    cols = ["total_revenue"]
    rows = [[1250000.50]]
    hint = generate_chart_hint(cols, rows)
    assert hint.type == "none"


def test_chart_hint_none_for_empty_rows_or_columns():
    """Empty query results produce chart hint none."""
    assert generate_chart_hint([], []).type == "none"
    assert generate_chart_hint(["col1"], []).type == "none"


def test_format_result_convenience_function():
    """format_result formats both rows and calculates chart hint."""
    cols = ["category", "count"]
    raw_rows = [["Books", Decimal("12")], ["Electronics", Decimal("8")]]
    formatted, hint = format_result(cols, raw_rows)
    assert formatted == [["Books", 12.0], ["Electronics", 8.0]]
    assert hint.type == "bar"
    assert hint.x_key == "category"
    assert hint.y_key == "count"


def test_column_type_checks_with_all_none():
    """Verify that helper methods return False when column values are all None."""
    from app.services.formatter import _is_column_date, _is_column_numeric, _is_column_text

    all_none = [None, None]
    assert _is_column_numeric(all_none) is False
    assert _is_column_date("arbitrary_col", all_none) is False
    assert _is_column_text("arbitrary_col", all_none) is False

