"""PostgreSQL database adapter."""

from __future__ import annotations

import time
from typing import Any

from queryclaw.db.base import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    QueryResult,
    SQLAdapter,
    TableInfo,
)


class PostgreSQLAdapter(SQLAdapter):
    """Async PostgreSQL adapter using asyncpg."""

    def __init__(self) -> None:
        self._conn: Any = None
        self._database: str = ""

    @property
    def db_type(self) -> str:
        return "postgresql"

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed()

    async def connect(self, **kwargs: Any) -> None:
        import asyncpg

        self._database = kwargs.get("database", "")
        self._conn = await asyncpg.connect(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 5432),
            user=kwargs.get("user", "postgres"),
            password=kwargs.get("password", ""),
            database=self._database,
        )

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        start = time.monotonic()
        stmt = await self._conn.prepare(sql)
        columns = [attr.name for attr in stmt.get_attributes()] if stmt.get_attributes() else []

        if columns:
            records = await stmt.fetch(*(params or ()))
            rows = [tuple(r) for r in records]
            affected_rows = len(rows)
        else:
            result_status = await self._conn.execute(sql, *(params or ()))
            rows = []
            try:
                affected_rows = int(result_status.split()[-1])
            except (ValueError, IndexError, AttributeError):
                affected_rows = 0

        elapsed = (time.monotonic() - start) * 1000
        return QueryResult(
            columns=columns,
            rows=rows,
            affected_rows=affected_rows,
            execution_time_ms=round(elapsed, 2),
        )

    async def get_tables(self) -> list[TableInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        records = await self._conn.fetch(
            "SELECT c.relname AS table_name, "
            "       c.reltuples::bigint AS row_estimate "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' "
            "ORDER BY c.relname"
        )
        return [
            TableInfo(
                name=r["table_name"],
                schema="public",
                row_count=max(r["row_estimate"], 0),
                engine="PostgreSQL",
            )
            for r in records
        ]

    async def get_columns(self, table: str) -> list[ColumnInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        records = await self._conn.fetch(
            "SELECT c.column_name, c.data_type, c.is_nullable, c.column_default, "
            "       CASE WHEN tc.constraint_type = 'PRIMARY KEY' THEN true ELSE false END AS is_pk, "
            "       COALESCE(c.character_maximum_length::text, '') AS extra "
            "FROM information_schema.columns c "
            "LEFT JOIN information_schema.key_column_usage kcu "
            "  ON kcu.table_schema = c.table_schema "
            "  AND kcu.table_name = c.table_name "
            "  AND kcu.column_name = c.column_name "
            "LEFT JOIN information_schema.table_constraints tc "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "  AND tc.constraint_type = 'PRIMARY KEY' "
            "WHERE c.table_schema = 'public' AND c.table_name = $1 "
            "ORDER BY c.ordinal_position",
            table,
        )
        return [
            ColumnInfo(
                name=r["column_name"],
                data_type=r["data_type"],
                nullable=r["is_nullable"] == "YES",
                default=r["column_default"],
                is_primary_key=bool(r["is_pk"]),
                extra=r["extra"] or "",
            )
            for r in records
        ]

    async def get_indexes(self, table: str) -> list[IndexInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        records = await self._conn.fetch(
            "SELECT i.relname AS index_name, "
            "       a.attname AS column_name, "
            "       ix.indisunique AS is_unique, "
            "       am.amname AS index_type "
            "FROM pg_index ix "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "JOIN pg_am am ON am.oid = i.relam "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey) "
            "WHERE n.nspname = 'public' AND t.relname = $1 "
            "ORDER BY i.relname, a.attnum",
            table,
        )
        idx_map: dict[str, IndexInfo] = {}
        for r in records:
            idx_name = r["index_name"]
            if idx_name not in idx_map:
                idx_map[idx_name] = IndexInfo(
                    name=idx_name,
                    unique=bool(r["is_unique"]),
                    type=r["index_type"] or "btree",
                )
            idx_map[idx_name].columns.append(r["column_name"])
        return list(idx_map.values())

    async def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        records = await self._conn.fetch(
            "SELECT tc.constraint_name, kcu.column_name, "
            "       ccu.table_name AS ref_table, ccu.column_name AS ref_column "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON kcu.constraint_name = tc.constraint_name "
            "  AND kcu.table_schema = tc.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON ccu.constraint_name = tc.constraint_name "
            "  AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_schema = 'public' AND tc.table_name = $1 "
            "ORDER BY tc.constraint_name, kcu.ordinal_position",
            table,
        )
        fk_map: dict[str, ForeignKeyInfo] = {}
        for r in records:
            fk_name = r["constraint_name"]
            if fk_name not in fk_map:
                fk_map[fk_name] = ForeignKeyInfo(name=fk_name, ref_table=r["ref_table"])
            fk_map[fk_name].columns.append(r["column_name"])
            fk_map[fk_name].ref_columns.append(r["ref_column"])
        return list(fk_map.values())

    async def explain(self, sql: str) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        records = await self._conn.fetch(f"EXPLAIN {sql}")
        columns = ["QUERY PLAN"]
        rows = [tuple(r) for r in records]
        return QueryResult(columns=columns, rows=rows)
