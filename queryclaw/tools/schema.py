"""Schema inspection tool for database structure exploration."""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import SQLAdapter
from queryclaw.tools.base import Tool


class SchemaInspectTool(Tool):
    """Inspect database schema: list tables, describe columns, indexes, foreign keys."""

    def __init__(self, db: SQLAdapter) -> None:
        self._db = db

    @property
    def name(self) -> str:
        return "schema_inspect"

    @property
    def description(self) -> str:
        return (
            "Inspect the database schema. Actions: "
            "list_tables (show all tables with row counts), "
            "describe_table (show columns for a table), "
            "list_indexes (show indexes for a table), "
            "list_foreign_keys (show foreign keys for a table)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_tables", "describe_table", "list_indexes", "list_foreign_keys"],
                    "description": "The inspection action to perform.",
                },
                "table": {
                    "type": "string",
                    "description": "Table name (required for describe_table, list_indexes, list_foreign_keys).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, table: str = "", **kwargs: Any) -> str:
        try:
            match action:
                case "list_tables":
                    return await self._list_tables()
                case "describe_table":
                    if not table:
                        return "Error: 'table' parameter is required for describe_table."
                    return await self._describe_table(table)
                case "list_indexes":
                    if not table:
                        return "Error: 'table' parameter is required for list_indexes."
                    return await self._list_indexes(table)
                case "list_foreign_keys":
                    if not table:
                        return "Error: 'table' parameter is required for list_foreign_keys."
                    return await self._list_foreign_keys(table)
                case _:
                    return f"Error: Unknown action '{action}'."
        except Exception as e:
            return f"Error: {e}"

    async def _list_tables(self) -> str:
        tables = await self._db.get_tables()
        if not tables:
            return "No tables found in the database."
        lines = [f"Tables in database ({len(tables)}):"]
        lines.append("")
        lines.append(f"{'Table':<30} {'Rows':>10} {'Engine':<10}")
        lines.append("-" * 55)
        for t in tables:
            rows = str(t.row_count) if t.row_count is not None else "?"
            engine = t.engine or "-"
            lines.append(f"{t.name:<30} {rows:>10} {engine:<10}")
        return "\n".join(lines)

    async def _describe_table(self, table: str) -> str:
        columns = await self._db.get_columns(table)
        if not columns:
            return f"No columns found for table '{table}' (table may not exist)."
        lines = [f"Columns in '{table}' ({len(columns)}):"]
        lines.append("")
        lines.append(f"{'Column':<25} {'Type':<20} {'Null':>5} {'Key':>5} {'Default':<15} {'Extra':<15}")
        lines.append("-" * 90)
        for c in columns:
            null = "YES" if c.nullable else "NO"
            key = "PRI" if c.is_primary_key else ""
            default = str(c.default) if c.default is not None else ""
            lines.append(f"{c.name:<25} {c.data_type:<20} {null:>5} {key:>5} {default:<15} {c.extra:<15}")
        return "\n".join(lines)

    async def _list_indexes(self, table: str) -> str:
        indexes = await self._db.get_indexes(table)
        if not indexes:
            return f"No indexes found for table '{table}'."
        lines = [f"Indexes on '{table}' ({len(indexes)}):"]
        lines.append("")
        lines.append(f"{'Index':<30} {'Columns':<30} {'Unique':>6} {'Type':<10}")
        lines.append("-" * 80)
        for idx in indexes:
            cols = ", ".join(idx.columns)
            unique = "YES" if idx.unique else "NO"
            lines.append(f"{idx.name:<30} {cols:<30} {unique:>6} {idx.type:<10}")
        return "\n".join(lines)

    async def _list_foreign_keys(self, table: str) -> str:
        fks = await self._db.get_foreign_keys(table)
        if not fks:
            return f"No foreign keys found for table '{table}'."
        lines = [f"Foreign keys on '{table}' ({len(fks)}):"]
        lines.append("")
        for fk in fks:
            cols = ", ".join(fk.columns)
            ref_cols = ", ".join(fk.ref_columns)
            lines.append(f"  {fk.name}: ({cols}) -> {fk.ref_table}({ref_cols})")
        return "\n".join(lines)
