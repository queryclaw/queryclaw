"""MySQL database adapter."""

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


class MySQLAdapter(SQLAdapter):
    """Async MySQL adapter using aiomysql."""

    def __init__(self) -> None:
        self._conn: Any = None
        self._database: str = ""

    @property
    def db_type(self) -> str:
        return "mysql"

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    async def connect(self, **kwargs: Any) -> None:
        import aiomysql

        self._database = kwargs.get("database", "")
        self._conn = await aiomysql.connect(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 3306),
            user=kwargs.get("user", "root"),
            password=kwargs.get("password", ""),
            db=self._database,
            autocommit=True,
            charset="utf8mb4",
        )

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        start = time.monotonic()
        async with self._conn.cursor() as cur:
            await cur.execute(sql, params or ())
            description = cur.description
            columns = [d[0] for d in description] if description else []
            rows = [tuple(r) for r in await cur.fetchall()] if description else []
            elapsed = (time.monotonic() - start) * 1000
            return QueryResult(
                columns=columns,
                rows=rows,
                affected_rows=cur.rowcount if cur.rowcount >= 0 else 0,
                execution_time_ms=round(elapsed, 2),
            )

    async def get_tables(self) -> list[TableInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        result = await self.execute(
            "SELECT TABLE_NAME, TABLE_ROWS, ENGINE "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_NAME",
            (self._database,),
        )
        return [
            TableInfo(
                name=row[0],
                schema=self._database,
                row_count=row[1],
                engine=row[2],
            )
            for row in result.rows
        ]

    async def get_columns(self, table: str) -> list[ColumnInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        result = await self.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (self._database, table),
        )
        return [
            ColumnInfo(
                name=row[0],
                data_type=row[1],
                nullable=row[2] == "YES",
                default=row[3],
                is_primary_key=row[4] == "PRI",
                extra=row[5] or "",
            )
            for row in result.rows
        ]

    async def get_indexes(self, table: str) -> list[IndexInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        result = await self.execute(
            "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE "
            "FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX",
            (self._database, table),
        )
        idx_map: dict[str, IndexInfo] = {}
        for row in result.rows:
            idx_name = row[0]
            if idx_name not in idx_map:
                idx_map[idx_name] = IndexInfo(
                    name=idx_name,
                    unique=not bool(row[2]),
                    type=row[3] or "BTREE",
                )
            idx_map[idx_name].columns.append(row[1])
        return list(idx_map.values())

    async def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        if not self._conn:
            raise RuntimeError("Not connected")
        result = await self.execute(
            "SELECT CONSTRAINT_NAME, COLUMN_NAME, "
            "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "AND REFERENCED_TABLE_NAME IS NOT NULL "
            "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION",
            (self._database, table),
        )
        fk_map: dict[str, ForeignKeyInfo] = {}
        for row in result.rows:
            fk_name = row[0]
            if fk_name not in fk_map:
                fk_map[fk_name] = ForeignKeyInfo(name=fk_name, ref_table=row[2])
            fk_map[fk_name].columns.append(row[1])
            fk_map[fk_name].ref_columns.append(row[3])
        return list(fk_map.values())

    async def explain(self, sql: str) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Not connected")
        return await self.execute(f"EXPLAIN {sql}")
