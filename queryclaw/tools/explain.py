"""SQL execution plan analysis tool."""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import SQLAdapter
from queryclaw.tools.base import Tool


class ExplainPlanTool(Tool):
    """Show execution plan for a SQL query using EXPLAIN."""

    def __init__(self, db: SQLAdapter) -> None:
        self._db = db

    @property
    def name(self) -> str:
        return "explain_plan"

    @property
    def description(self) -> str:
        return (
            "Show the execution plan for a SQL query using EXPLAIN. "
            "Use this to understand how the database will execute a query, "
            "identify potential performance issues, and verify index usage."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to analyze with EXPLAIN.",
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, **kwargs: Any) -> str:
        sql_stripped = sql.strip().rstrip(";")
        if not sql_stripped:
            return "Error: Empty SQL statement."

        try:
            result = await self._db.explain(sql_stripped)
            if result.row_count == 0:
                return "EXPLAIN returned no results."
            header = f"Execution plan for: {sql_stripped[:80]}{'...' if len(sql_stripped) > 80 else ''}"
            table = result.to_text()
            return f"{header}\n\n{table}"
        except Exception as e:
            return f"Error: {e}"
