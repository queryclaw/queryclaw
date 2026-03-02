"""MySQL database adapter."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from queryclaw.db.base import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    QueryResult,
    SQLAdapter,
    TableInfo,
)

_MAX_RECONNECT_ATTEMPTS = 2

# MySQL CR_* error codes that indicate the TCP connection is broken.
# Only these should trigger a close + reconnect; SQL/schema errors should not.
_MYSQL_CONNECTION_ERROR_CODES = frozenset({
    2006,  # CR_SERVER_GONE_ERROR – server went away
    2013,  # CR_SERVER_LOST – lost connection during query
    2014,  # CR_COMMANDS_OUT_OF_SYNC – out-of-sync protocol state
    2055,  # CR_SERVER_LOST_EXTENDED
})


def _is_connection_error(exc: Exception) -> bool:
    """Return True only if *exc* signals a broken TCP/MySQL connection."""
    errno = getattr(exc, "args", (None,))[0] if exc.args else None
    if isinstance(errno, int) and errno in _MYSQL_CONNECTION_ERROR_CODES:
        return True
    # aiomysql wraps some errors; check the inner cause as well
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None:
        return _is_connection_error(cause)
    return False


class MySQLAdapter(SQLAdapter):
    """Async MySQL adapter using aiomysql."""

    def __init__(self) -> None:
        self._conn: Any = None
        self._database: str = ""
        self._connect_kwargs: dict[str, Any] = {}

    @property
    def db_type(self) -> str:
        return "mysql"

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    async def connect(self, **kwargs: Any) -> None:
        import aiomysql

        self._connect_kwargs = kwargs.copy()
        self._database = kwargs.get("database", "")
        self._conn = await aiomysql.connect(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 3306),
            user=kwargs.get("user", "root"),
            password=kwargs.get("password", ""),
            db=self._database,
            autocommit=True,
            charset="utf8mb4",
            use_unicode=True,
            init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        )
        # Increase packet size for long SQL (e.g. bulk UPDATE with Chinese text)
        try:
            async with self._conn.cursor() as cur:
                await cur.execute("SET SESSION max_allowed_packet=67108864")
        except Exception:
            pass

    async def _ensure_connected(self) -> None:
        """Reconnect if the connection is lost."""
        if self.is_connected:
            try:
                async with self._conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                return
            except Exception:
                logger.warning("MySQL connection health check failed, reconnecting...")

        if not self._connect_kwargs:
            raise RuntimeError("Not connected and no stored connection parameters")

        self._close_conn()

        logger.info("Reconnecting to MySQL...")
        await self.connect(**self._connect_kwargs)

    async def close(self) -> None:
        self._close_conn()

    def _close_conn(self) -> None:
        """Close connection and clear reference."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        last_error: Exception | None = None
        for attempt in range(_MAX_RECONNECT_ATTEMPTS):
            try:
                await self._ensure_connected()
                return await self._execute_once(sql, params)
            except RuntimeError:
                raise
            except UnicodeDecodeError as e:
                last_error = e
                logger.warning(
                    "MySQL execute failed (attempt {}/{}): UTF-8 decode error - connection may be corrupted: {}",
                    attempt + 1, _MAX_RECONNECT_ATTEMPTS, e,
                )
                self._close_conn()
                await asyncio.sleep(0.5)  # Allow server to release the broken connection
            except Exception as e:
                last_error = e
                # Only retry/reconnect for actual connection-level errors.
                # SQL/schema errors (unknown column, syntax error, constraint violation, etc.)
                # leave the connection intact — retrying will always fail the same way.
                if not _is_connection_error(e):
                    raise
                logger.warning("MySQL execute failed (attempt {}/{}): {}", attempt + 1, _MAX_RECONNECT_ATTEMPTS, e)
                self._close_conn()
        raise last_error  # type: ignore[misc]

    async def _execute_once(self, sql: str, params: tuple | None = None) -> QueryResult:
        # When no params: escape literal % (e.g. in LIKE '%x%') to %% so the driver
        # does not treat them as format placeholders ("not enough arguments" error).
        if not params:
            sql = sql.replace("%", "%%")
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
        await self._ensure_connected()
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
        await self._ensure_connected()
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
        await self._ensure_connected()
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
        await self._ensure_connected()
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
        await self._ensure_connected()
        return await self.execute(f"EXPLAIN {sql}")

    async def begin_transaction(self) -> None:
        await self._ensure_connected()
        await self._conn.begin()

    async def commit(self) -> None:
        if not self.is_connected:
            raise RuntimeError("Not connected")
        async with self._conn.cursor() as cur:
            await cur.execute("COMMIT")

    async def rollback(self) -> None:
        if not self.is_connected:
            raise RuntimeError("Not connected")
        async with self._conn.cursor() as cur:
            await cur.execute("ROLLBACK")
