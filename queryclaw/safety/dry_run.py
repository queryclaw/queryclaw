"""Dry-run engine — estimate impact before executing write operations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from queryclaw.db.base import SQLAdapter


@dataclass
class DryRunResult:
    """Result of a dry-run analysis."""

    estimated_rows: int = 0
    explain_plan: str = ""
    warnings: list[str] = field(default_factory=list)


class DryRunEngine:
    """Estimates the impact of write SQL by running EXPLAIN and COUNT queries."""

    def __init__(self, db: SQLAdapter) -> None:
        self._db = db

    async def analyze(self, sql: str) -> DryRunResult:
        """Analyze a write statement without executing it."""
        upper = sql.strip().upper()

        result = DryRunResult()

        try:
            explain_result = await self._db.explain(sql)
            result.explain_plan = explain_result.to_text()
        except Exception as e:
            result.warnings.append(f"EXPLAIN failed: {e}")

        if upper.startswith("UPDATE") or upper.startswith("DELETE"):
            count = await self._estimate_affected_rows(sql)
            result.estimated_rows = count
            if count > 1000:
                result.warnings.append(f"High impact: {count} rows will be affected")
            if count == 0:
                result.warnings.append("No rows match the condition (0 rows affected)")

        elif upper.startswith("INSERT"):
            result.estimated_rows = self._count_insert_rows(sql)

        return result

    async def _estimate_affected_rows(self, sql: str) -> int:
        """Convert UPDATE/DELETE to SELECT COUNT(*) with the same WHERE."""
        upper = sql.strip().upper()

        try:
            if upper.startswith("DELETE"):
                count_sql = self._delete_to_count(sql)
            elif upper.startswith("UPDATE"):
                count_sql = self._update_to_count(sql)
            else:
                return 0

            if count_sql:
                result = await self._db.execute(count_sql)
                if result.rows:
                    return int(result.rows[0][0])
        except Exception:
            pass
        return 0

    @staticmethod
    def _delete_to_count(sql: str) -> str | None:
        match = re.match(
            r"DELETE\s+FROM\s+(\S+)(.*)",
            sql.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table = match.group(1)
            rest = match.group(2).strip().rstrip(";")
            return f"SELECT COUNT(*) FROM {table} {rest}"
        return None

    @staticmethod
    def _update_to_count(sql: str) -> str | None:
        match = re.match(
            r"UPDATE\s+(\S+)\s+SET\s+.*?(WHERE\s+.*)",
            sql.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table = match.group(1)
            where = match.group(2).strip().rstrip(";")
            return f"SELECT COUNT(*) FROM {table} {where}"
        match_no_where = re.match(
            r"UPDATE\s+(\S+)\s+SET\s+",
            sql.strip(),
            re.IGNORECASE,
        )
        if match_no_where:
            table = match_no_where.group(1)
            return f"SELECT COUNT(*) FROM {table}"
        return None

    @staticmethod
    def _count_insert_rows(sql: str) -> int:
        upper = sql.strip().upper()
        if "VALUES" in upper:
            return upper.count("(") - 1
        if "SELECT" in upper:
            return -1
        return 1
