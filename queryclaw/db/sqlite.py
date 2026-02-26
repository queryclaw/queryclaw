"""SQLite database adapter."""

from __future__ import annotations

import time
from typing import Any

import aiosqlite

from queryclaw.db.base import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    QueryResult,
    SQLAdapter,
    TableInfo,
)


class SQLiteAdapter(SQLAdapter):
    """Async SQLite adapter using aiosqlite."""

    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None
        self._db_path: str = ""

    @property
    def db_type(self) -> str:
        return "sqlite"

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    async def connect(self, **kwargs: Any) -> None:
        database = kwargs.get("database", "")
        if not database:
            raise ValueError("SQLite requires a 'database' path")
        self._db_path = database
        self._conn = await aiosqlite.connect(database)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        start = time.monotonic()
        cursor = await self._conn.execute(sql, params or ())
        description = cursor.description
        columns = [d[0] for d in description] if description else []
        rows = [tuple(r) for r in await cursor.fetchall()]
        elapsed = (time.monotonic() - start) * 1000
        return QueryResult(
            columns=columns,
            rows=rows,
            affected_rows=cursor.rowcount if cursor.rowcount >= 0 else 0,
            execution_time_ms=round(elapsed, 2),
        )

    async def get_tables(self) -> list[TableInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = await self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        rows = await cursor.fetchall()
        tables: list[TableInfo] = []
        for row in rows:
            name = row[0]
            count_cursor = await self._conn.execute(f"SELECT COUNT(*) FROM [{name}]")
            count_row = await count_cursor.fetchone()
            tables.append(TableInfo(name=name, row_count=count_row[0] if count_row else 0))
        return tables

    async def get_columns(self, table: str) -> list[ColumnInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = await self._conn.execute(f"PRAGMA table_info([{table}])")
        rows = await cursor.fetchall()
        return [
            ColumnInfo(
                name=row[1],
                data_type=row[2] or "TEXT",
                nullable=not row[3],
                default=row[4],
                is_primary_key=bool(row[5]),
            )
            for row in rows
        ]

    async def get_indexes(self, table: str) -> list[IndexInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = await self._conn.execute(f"PRAGMA index_list([{table}])")
        index_rows = await cursor.fetchall()
        indexes: list[IndexInfo] = []
        for row in index_rows:
            idx_name = row[1]
            unique = bool(row[2])
            col_cursor = await self._conn.execute(f"PRAGMA index_info([{idx_name}])")
            col_rows = await col_cursor.fetchall()
            columns = [cr[2] for cr in col_rows]
            indexes.append(IndexInfo(name=idx_name, columns=columns, unique=unique, type="BTREE"))
        return indexes

    async def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = await self._conn.execute(f"PRAGMA foreign_key_list([{table}])")
        rows = await cursor.fetchall()
        fk_map: dict[int, ForeignKeyInfo] = {}
        for row in rows:
            fk_id = row[0]
            if fk_id not in fk_map:
                fk_map[fk_id] = ForeignKeyInfo(
                    name=f"fk_{table}_{fk_id}",
                    ref_table=row[2],
                )
            fk_map[fk_id].columns.append(row[3])
            fk_map[fk_id].ref_columns.append(row[4])
        return list(fk_map.values())

    async def explain(self, sql: str) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        return await self.execute(f"EXPLAIN QUERY PLAN {sql}")
