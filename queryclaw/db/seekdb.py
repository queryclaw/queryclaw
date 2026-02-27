"""SeekDB database adapter.

SeekDB is an AI-native search database by OceanBase, MySQL protocol compatible.
Default port: 2881. Supports VECTOR type, l2_distance, cosine_distance, AI_EMBED.
"""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import QueryResult
from queryclaw.db.mysql import MySQLAdapter


class SeekDBAdapter(MySQLAdapter):
    """Async SeekDB adapter (extends MySQLAdapter, uses aiomysql)."""

    @property
    def db_type(self) -> str:
        return "seekdb"

    async def connect(self, **kwargs: Any) -> None:
        kwargs.setdefault("port", 2881)
        await super().connect(**kwargs)

    async def explain(self, sql: str) -> QueryResult:
        """Run EXPLAIN on SQL. SeekDB may return different format; raw result is passed through."""
        await self._ensure_connected()
        return await self.execute(f"EXPLAIN {sql}")
