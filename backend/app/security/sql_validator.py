"""SQL syntax and security policy validator using SQLGlot AST inspection.

================================================================================
SECURITY ARCHITECTURE & KNOWN LIMITATIONS
================================================================================
This module serves as the primary AST-level security boundary (Layer 2 in DataQuery's
defense-in-depth model). It enforces strict allowlists on tables, schemas, columns,
functions, and statement structures before any SQL reaches the database.

Known Limitations & Rationale for Defense-in-Depth:
1. Parser Differential:
   SQLGlot's PostgreSQL dialect parser closely mirrors PostgreSQL grammar, but subtle
   dialect discrepancies or exotic syntax constructs may exist. The validator rejects
   any ambiguous or unsupported AST node conservatively.
2. Semantic Correctness Not Guaranteed:
   A query may be 100% syntactically valid and security-compliant according to policy,
   yet semantically incorrect (e.g. joining on the wrong foreign key or applying unintended
   WHERE filters). Semantic validation is handled by downstream evaluation suites.
3. Expensive-but-Legal Queries:
   Certain syntactically valid queries (e.g. multi-table Cartesian CROSS JOINs) cannot
   be fully eliminated by AST structure alone without solving the Halting Problem.
4. Database Kernel Permissions Remain Essential:
   Because no AST validator is omniscient, database-layer controls (PostgreSQL role
   dq_readonly, default_transaction_read_only = on, SET LOCAL statement_timeout = 3000ms,
   REVOKE on system catalogs and app schema) remain the non-negotiable backstop.
================================================================================
"""

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from app.security.policy import (
    ALLOWED_FUNCTIONS,
    ALLOWED_SCHEMAS,
    ALLOWED_TABLES,
    BANNED_FUNCTIONS,
    BANNED_TABLES,
    TABLE_COLUMNS,
)

# Private sentinel token to ensure ValidatedSQL cannot be constructed outside this module
_VALIDATION_TOKEN = object()

# Schema column dictionary formatted for sqlglot.optimizer.qualify
_QUALIFY_SCHEMA: dict[str, dict[str, str]] = {
    table: dict.fromkeys(cols, "text") for table, cols in TABLE_COLUMNS.items()
}

# Forbidden SQLGlot AST node types (DML, DDL, administrative, transaction control)
_FORBIDDEN_AST_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Grant,
    exp.Revoke,
    exp.Merge,
    exp.Command,
    exp.Into,
    exp.Lock,
    exp.Copy,
    exp.Commit,
    exp.Rollback,
    exp.Transaction,
    exp.Set,
    exp.Analyze,
    exp.Pragma,
    exp.Fetch,
)

# Mapping of SQLGlot built-in function classes to standardized uppercase names
_FUNCTION_CLASS_MAP: dict[type[exp.Expression], str] = {
    exp.Sum: "SUM",
    exp.Count: "COUNT",
    exp.Avg: "AVG",
    exp.Min: "MIN",
    exp.Max: "MAX",
    exp.Round: "ROUND",
    exp.Coalesce: "COALESCE",
    exp.Nullif: "NULLIF",
    exp.TimestampTrunc: "DATE_TRUNC",
    exp.DateTrunc: "DATE_TRUNC",
    exp.Extract: "EXTRACT",
    exp.Cast: "CAST",
    exp.TryCast: "CAST",
    exp.Lower: "LOWER",
    exp.Upper: "UPPER",
    exp.Abs: "ABS",
    exp.RowNumber: "ROW_NUMBER",
    exp.Rank: "RANK",
    exp.DenseRank: "DENSE_RANK",
    exp.Lag: "LAG",
    exp.Lead: "LEAD",
}


class ValidatedSQL:
    """Opaque trusted token containing normalized, validated SQL.

    Cannot be instantiated directly by callers with raw SQL strings.
    Only `validate_sql()` can construct and return ValidatedSQL.
    """

    __slots__ = ("_sql",)

    def __init__(self, sql: str, *, _token: object) -> None:
        if _token is not _VALIDATION_TOKEN:
            raise PermissionError(
                "ValidatedSQL cannot be instantiated directly. Use validate_sql() to generate validated queries."
            )
        self._sql = sql

    @property
    def sql(self) -> str:
        """Return the validated and normalized SQL string."""
        return self._sql

    def __str__(self) -> str:
        return self._sql

    def __repr__(self) -> str:
        return f"ValidatedSQL({self._sql!r})"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of SQL AST inspection and security validation."""

    valid: bool
    reasons: list[str] = field(default_factory=list)
    normalized_sql: str | None = None
    validated_sql: ValidatedSQL | None = None


def validate_sql(sql: str, max_rows: int = 100) -> ValidationResult:
    """Validate a raw SQL query string against syntax and security policies.

    Enforces:
    - Length between 1 and 5000 characters, non-empty, no null bytes.
    - Exactly one SQL statement.
    - Root statement is SELECT or UNION of SELECTs, with read-only CTEs.
    - Prohibits all DML, DDL, administrative commands, SELECT INTO, and FOR UPDATE/SHARE.
    - All table references are in ALLOWED_TABLES (under ALLOWED_SCHEMAS or unqualified).
    - Prohibits system catalogs (pg_*, information_schema) and app metadata schema.
    - Every column resolves against TABLE_COLUMNS via SQLGlot qualification.
    - All functions are in ALLOWED_FUNCTIONS.
    - Injects or clamps LIMIT to max_rows + 1.
    - Returns normalized SQL stripped of all comments.
    """
    reasons: list[str] = []

    # 1. Basic string safety & length constraints
    if not isinstance(sql, str):
        return ValidationResult(valid=False, reasons=["Query must be a string."])

    cleaned = sql.strip()
    if not cleaned:
        return ValidationResult(valid=False, reasons=["Query is empty or whitespace-only."])

    if len(cleaned) > 5000:
        return ValidationResult(
            valid=False,
            reasons=[f"Query length ({len(cleaned)}) exceeds 5000 character maximum limit."],
        )

    if "\x00" in cleaned:
        return ValidationResult(
            valid=False,
            reasons=["Null bytes (\\x00) are strictly prohibited."],
        )

    # Dollar-quoting ($$...$$ or $tag$...$tag$) is prohibited in analytics queries
    if "$$" in cleaned or re.search(r"\$[a-zA-Z0-9_]*\$", cleaned):
        return ValidationResult(
            valid=False,
            reasons=["Dollar-quoting ($$) is prohibited."],
        )

    # 2. Parse using SQLGlot Postgres dialect
    try:
        statements = sqlglot.parse(cleaned, read="postgres")
    except Exception as ex:
        return ValidationResult(
            valid=False,
            reasons=[f"SQL syntax or tokenization error: {ex}"],
        )

    # Filter out empty statements (e.g. standalone semicolons)
    non_empty_stmts = [s for s in statements if s is not None]
    if len(non_empty_stmts) == 0:
        return ValidationResult(valid=False, reasons=["No valid SQL statements found."])
    if len(non_empty_stmts) > 1:
        return ValidationResult(
            valid=False,
            reasons=[
                f"Multiple statements detected ({len(non_empty_stmts)}). Only single queries are permitted."
            ],
        )

    ast = non_empty_stmts[0]

    # Check for semicolon followed by non-whitespace/non-comment content
    raw_without_trailing = cleaned.rstrip().rstrip(";").strip()
    if ";" in raw_without_trailing and len(statements) > 1:
        return ValidationResult(
            valid=False,
            reasons=["Multiple statements separated by semicolon are strictly prohibited."],
        )

    # 3. Root Statement Type Check
    if not isinstance(ast, (exp.Select, exp.Union)):
        return ValidationResult(
            valid=False,
            reasons=[
                f"Root statement type '{type(ast).__name__}' is not permitted. Only SELECT queries are allowed."
            ],
        )

    # 4. AST Traversal: Check for Forbidden Nodes anywhere in the tree
    for node in ast.walk():
        if isinstance(node, _FORBIDDEN_AST_NODES):
            reasons.append(
                f"Forbidden SQL operation detected: '{type(node).__name__}'. Only read-only SELECT queries are permitted."
            )
            break

    # 5. Check for SELECT INTO and row locks (FOR UPDATE / FOR SHARE)
    if ast.find(exp.Into):
        reasons.append("SELECT INTO clauses are strictly prohibited.")

    if ast.find(exp.Lock):
        reasons.append("Row-locking clauses (FOR UPDATE, FOR SHARE) are strictly prohibited.")

    # 6. Validate CTEs (WITH clauses)
    for cte in ast.find_all(exp.CTE):
        if not isinstance(cte.this, (exp.Select, exp.Union)):
            reasons.append(
                f"CTE '{cte.alias_or_name}' must be a read-only SELECT or UNION query, not a data modification."
            )
        # Check for forbidden nodes inside CTE body
        for subnode in cte.this.walk():
            if isinstance(subnode, _FORBIDDEN_AST_NODES):
                reasons.append(
                    f"Forbidden operation '{type(subnode).__name__}' inside CTE '{cte.alias_or_name}'."
                )

    # 7. Validate Table and Schema References
    cte_names = {cte.alias_or_name.lower() for cte in ast.find_all(exp.CTE) if cte.alias_or_name}

    for table in ast.find_all(exp.Table):
        t_name = table.name.lower()
        schema_name = table.db.lower() if table.db else None

        # Check schema qualification
        if schema_name is not None:
            if schema_name not in ALLOWED_SCHEMAS:
                reasons.append(
                    f"Access to schema '{schema_name}' is not permitted. Only 'public' or unqualified tables are allowed."
                )
            if schema_name in {"pg_catalog", "information_schema", "app"} or schema_name.startswith(
                "pg_"
            ):
                reasons.append(
                    f"Access to restricted schema '{schema_name}' is strictly forbidden."
                )

        # Check table name
        if t_name in cte_names:
            continue

        if t_name in BANNED_TABLES or t_name.startswith("pg_") or t_name == "information_schema":
            reasons.append(f"Access to restricted table '{t_name}' is strictly forbidden.")
        elif t_name not in ALLOWED_TABLES:
            reasons.append(f"Table '{t_name}' is not permitted. Only analytics tables are allowed.")

    # 8. Validate Functions
    for func in ast.find_all(exp.Func):
        if isinstance(func, (exp.Case, exp.If, exp.Exists, exp.Connector)):
            continue

        if isinstance(func, exp.Anonymous):
            fname = func.name.upper()
        elif type(func) in _FUNCTION_CLASS_MAP:
            fname = _FUNCTION_CLASS_MAP[type(func)]
        else:
            fname = getattr(func, "key", type(func).__name__).upper()

        if fname in BANNED_FUNCTIONS or fname.lower() in BANNED_FUNCTIONS:
            reasons.append(f"Function '{fname}' is explicitly forbidden.")
        elif fname not in ALLOWED_FUNCTIONS:
            reasons.append(
                f"Function '{fname}' is not permitted. Allowed functions: {sorted(ALLOWED_FUNCTIONS)}."
            )

    # If any fundamental structural errors occurred, return early
    if reasons:
        return ValidationResult(valid=False, reasons=reasons)

    # 9. Validate Columns via SQLGlot Qualification & AST Check
    try:
        # Create a deep copy for qualification so original AST is preserved if needed
        qualified_ast = qualify(
            ast.copy(),
            schema=_QUALIFY_SCHEMA,
            dialect="postgres",
            validate_qualify_columns=True,
            identify=False,
        )
    except Exception as ex:
        reasons.append(f"Column resolution error: {ex}")
        return ValidationResult(valid=False, reasons=reasons)

    # Defense-in-depth: Inspect qualified column nodes
    for col in qualified_ast.find_all(exp.Column):
        col_name = col.name.lower()
        if col.table:
            t_name = col.table.lower()
            if t_name in TABLE_COLUMNS and col_name not in TABLE_COLUMNS[t_name]:
                reasons.append(f"Unknown column '{col_name}' on table '{t_name}'.")

    if reasons:
        return ValidationResult(valid=False, reasons=reasons)

    # 10. Clamp or Inject LIMIT Clause
    # We fetch one extra row (max_rows + 1) so the executor can detect whether the
    # result was truncated beyond max_rows without running a separate expensive COUNT(*) query.
    target_limit = max_rows + 1
    limit_node = qualified_ast.args.get("limit")

    if limit_node is None:
        qualified_ast.limit(target_limit, copy=False)
    else:
        try:
            val = int(limit_node.expression.this)
            if val > target_limit or val <= 0:
                qualified_ast.limit(target_limit, copy=False)
        except Exception:
            qualified_ast.limit(target_limit, copy=False)

    # 11. Generate Normalized SQL from AST (strips all comments)
    normalized_sql = qualified_ast.sql(dialect="postgres", comments=False)
    validated_token = ValidatedSQL(normalized_sql, _token=_VALIDATION_TOKEN)

    return ValidationResult(
        valid=True,
        reasons=[],
        normalized_sql=normalized_sql,
        validated_sql=validated_token,
    )
