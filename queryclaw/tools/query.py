"""Read-only SQL query execution tool."""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import SQLAdapter
from queryclaw.tools.base import Tool

_DISALLOWED_PREFIXES = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "RENAME",
)


class QueryExecuteTool(Tool):
    """Execute a read-only SQL query (SELECT only) and return results."""

    def __init__(self, db: SQLAdapter, max_rows: int = 100) -> None:
        self._db = db
        self._max_rows = max_rows

    @property
    def name(self) -> str:
        return "query_execute"

    @property
    def description(self) -> str:
        return (
            "Execute a read-only SQL query (SELECT statements only). "
            f"Results are limited to {self._max_rows} rows. "
            "Use this to explore data, run aggregations, or verify hypotheses."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SELECT SQL query to execute.",
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, **kwargs: Any) -> str:
        sql_stripped = sql.strip()

        rejection = self._check_readonly(sql_stripped)
        if rejection:
            return rejection

        limited_sql = self._apply_limit(sql_stripped)

        try:
            result = await self._db.execute(limited_sql)
            header = f"Query returned {result.row_count} row(s) in {result.execution_time_ms:.1f}ms"
            if result.row_count == 0:
                return f"{header}\n(no rows)"
            table = result.to_text(max_rows=self._max_rows)
            return f"{header}\n\n{table}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _check_readonly(sql: str) -> str | None:
        """Return an error message if the SQL is not read-only."""
        upper = sql.upper().lstrip()
        for prefix in _DISALLOWED_PREFIXES:
            if upper.startswith(prefix):
                return (
                    f"Error: Only SELECT queries are allowed. "
                    f"'{prefix}' statements are not permitted in read-only mode."
                )
        if not upper.startswith("SELECT") and not upper.startswith("WITH"):
            return "Error: Only SELECT (or WITH ... SELECT) queries are allowed."
        return None

    def _apply_limit(self, sql: str) -> str:
        """Append LIMIT if not already present."""
        upper = sql.upper()
        if "LIMIT" in upper:
            return sql
        return f"{sql.rstrip(';')} LIMIT {self._max_rows}"
