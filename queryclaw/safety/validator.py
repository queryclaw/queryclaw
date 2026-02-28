"""SQL validation using AST analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of SQL validation."""

    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    operation_type: str = "unknown"
    tables_affected: list[str] = field(default_factory=list)


_DESTRUCTIVE_KEYWORDS = {"DROP", "TRUNCATE"}

# Always blocked — cannot be overridden by config (security-critical)
_ALWAYS_BLOCKED = [
    "ALTER USER",
    "SET PASSWORD",
    "CREATE USER",
    "IDENTIFIED BY",
    "GRANT ",
]

_WRITE_PREFIXES = {
    "INSERT": "insert",
    "UPDATE": "update",
    "DELETE": "delete",
    "DROP": "ddl_drop",
    "ALTER": "ddl_alter",
    "CREATE": "ddl_create",
    "TRUNCATE": "ddl_truncate",
}


class QueryValidator:
    """Validates SQL statements against safety rules.

    Uses sqlglot for AST parsing when available, falls back to
    keyword-based analysis for resilience.
    """

    def __init__(self, blocked_patterns: list[str] | None = None) -> None:
        user_blocked = [p.upper() for p in (blocked_patterns or [])]
        # Merge: always-blocked (security-critical) + user config
        seen = set()
        merged = []
        for p in _ALWAYS_BLOCKED + user_blocked:
            if p not in seen:
                seen.add(p)
                merged.append(p)
        self._blocked = merged

    def validate(self, sql: str, dialect: str = "mysql") -> ValidationResult:
        """Validate a SQL statement and return a structured result."""
        sql_stripped = sql.strip().rstrip(";")
        upper = sql_stripped.upper()

        result = ValidationResult()

        for pattern in self._blocked:
            if pattern in upper:
                result.allowed = False
                result.warnings.append(f"Blocked pattern detected: {pattern}")
                return result

        result.operation_type = self._detect_operation(upper)
        result.tables_affected = self._extract_tables(sql_stripped, dialect)

        if result.operation_type.startswith("ddl_drop"):
            result.requires_confirmation = True
            result.warnings.append("DROP operation requires confirmation")

        if result.operation_type == "ddl_truncate":
            result.requires_confirmation = True
            result.warnings.append("TRUNCATE will remove all rows")

        if result.operation_type in ("delete", "update"):
            if not self._has_where_clause(upper):
                result.requires_confirmation = True
                result.warnings.append(
                    f"{result.operation_type.upper()} without WHERE clause — all rows will be affected"
                )

        return result

    @staticmethod
    def _detect_operation(upper_sql: str) -> str:
        for prefix, op_type in _WRITE_PREFIXES.items():
            if upper_sql.startswith(prefix):
                return op_type
        if upper_sql.startswith("SELECT") or upper_sql.startswith("WITH"):
            return "select"
        return "unknown"

    def _extract_tables(self, sql: str, dialect: str) -> list[str]:
        """Try sqlglot first, fall back to simple regex."""
        try:
            return self._extract_tables_sqlglot(sql, dialect)
        except Exception:
            return self._extract_tables_fallback(sql)

    @staticmethod
    def _extract_tables_sqlglot(sql: str, dialect: str) -> list[str]:
        import sqlglot

        tables: list[str] = []
        try:
            parsed = sqlglot.parse_one(sql, dialect=dialect)
        except sqlglot.errors.ParseError:
            return []

        for table in parsed.find_all(sqlglot.exp.Table):
            name = table.name
            if name:
                tables.append(name)
        return tables

    @staticmethod
    def _extract_tables_fallback(sql: str) -> list[str]:
        import re

        tables: list[str] = []
        for m in re.finditer(
            r"(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+[`\"']?(\w+)[`\"']?",
            sql,
            re.IGNORECASE,
        ):
            tables.append(m.group(1))
        return tables

    @staticmethod
    def _has_where_clause(upper_sql: str) -> bool:
        return "WHERE" in upper_sql
