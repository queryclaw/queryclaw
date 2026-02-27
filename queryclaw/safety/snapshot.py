"""Snapshot helper — captures before/after row data for audit logging."""

from __future__ import annotations

import json
import re
from typing import Any

from queryclaw.db.base import QueryResult, SQLAdapter

MAX_SNAPSHOT_ROWS = 100
MAX_SNAPSHOT_BYTES = 50_000


def _rows_to_json(columns: list[str], rows: list[tuple], max_bytes: int = MAX_SNAPSHOT_BYTES) -> str:
    """Serialize query result to JSON, truncating if too large."""
    out: list[dict[str, Any]] = []
    size = 0
    for row in rows[:MAX_SNAPSHOT_ROWS]:
        obj = {col: _serialize_value(v) for col, v in zip(columns, row)}
        s = json.dumps(obj, default=str)
        if size + len(s) > max_bytes:
            break
        out.append(obj)
        size += len(s)
    return json.dumps(out, default=str, ensure_ascii=False)


def _serialize_value(v: Any) -> Any:
    """Serialize a value for JSON (handle bytes, datetime, etc.)."""
    if v is None:
        return None
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return "<binary>"
    return v


class SnapshotHelper:
    """Captures before/after row snapshots for DML audit logging."""

    def __init__(self, db: SQLAdapter) -> None:
        self._db = db

    async def get_before_snapshot(self, sql: str) -> str:
        """Get row snapshot before UPDATE or DELETE. Returns empty string for INSERT."""
        upper = sql.strip().upper()
        if upper.startswith("INSERT"):
            return ""

        select_sql = None
        if upper.startswith("DELETE"):
            select_sql = self._delete_to_select(sql)
        elif upper.startswith("UPDATE"):
            select_sql = self._update_to_select(sql)

        if not select_sql:
            return ""

        try:
            result = await self._db.execute(select_sql)
            return _rows_to_json(result.columns, result.rows)
        except Exception:
            return ""

    async def get_after_snapshot(
        self,
        sql: str,
        operation: str,
        before_select_sql: str | None,
    ) -> str:
        """Get row snapshot after DML. For UPDATE, re-runs the same SELECT; for DELETE, empty."""
        upper = sql.strip().upper()
        if upper.startswith("INSERT"):
            return self._insert_after_snapshot(sql)
        if upper.startswith("DELETE"):
            return ""
        if upper.startswith("UPDATE") and before_select_sql:
            try:
                result = await self._db.execute(before_select_sql)
                return _rows_to_json(result.columns, result.rows)
            except Exception:
                return ""
        return ""

    def _insert_after_snapshot(self, sql: str) -> str:
        """Extract inserted values from INSERT statement as JSON."""
        try:
            rows = self._parse_insert_values(sql)
            if rows:
                return json.dumps(rows, default=str, ensure_ascii=False)
        except Exception:
            pass
        return ""

    @staticmethod
    def _parse_insert_values(sql: str) -> list[dict[str, Any]]:
        """Parse INSERT ... VALUES (...), (...) into list of dicts. Best-effort."""
        upper = sql.strip().upper()
        if "VALUES" not in upper:
            return []

        # Find column names if present: INSERT INTO t (a, b) VALUES ...
        cols: list[str] | None = None
        col_match = re.search(
            r"INSERT\s+INTO\s+\S+\s*\(([^)]+)\)\s+VALUES",
            sql,
            re.IGNORECASE,
        )
        if col_match:
            cols = [c.strip().strip("`\"'") for c in col_match.group(1).split(",")]

        # Find VALUES (...), (...)
        values_match = re.search(r"VALUES\s+(.+)", sql, re.IGNORECASE | re.DOTALL)
        if not values_match:
            return []

        values_str = values_match.group(1).strip().rstrip(";")
        rows = _parse_values_list(values_str)
        if not rows:
            return []

        if cols and len(cols) == len(rows[0]):
            return [dict(zip(cols, r)) for r in rows[:MAX_SNAPSHOT_ROWS]]
        return [{"_row": list(r)} for r in rows[:MAX_SNAPSHOT_ROWS]]

    @staticmethod
    def _delete_to_select(sql: str, limit: int = MAX_SNAPSHOT_ROWS) -> str | None:
        match = re.match(
            r"DELETE\s+FROM\s+(\S+)(.*)",
            sql.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table = match.group(1)
            rest = match.group(2).strip().rstrip(";")
            return f"SELECT * FROM {table} {rest} LIMIT {limit}"
        return None

    @staticmethod
    def _update_to_select(sql: str, limit: int = MAX_SNAPSHOT_ROWS) -> str | None:
        match = re.match(
            r"UPDATE\s+(\S+)\s+SET\s+.*?(WHERE\s+.*)",
            sql.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table = match.group(1)
            where = match.group(2).strip().rstrip(";")
            return f"SELECT * FROM {table} {where} LIMIT {limit}"
        match_no_where = re.match(
            r"UPDATE\s+(\S+)\s+SET\s+",
            sql.strip(),
            re.IGNORECASE,
        )
        if match_no_where:
            table = match_no_where.group(1)
            return f"SELECT * FROM {table} LIMIT {limit}"
        return None

    def get_before_select_sql(self, sql: str) -> str | None:
        """Return the SELECT SQL used for before snapshot (for reuse in after for UPDATE)."""
        upper = sql.strip().upper()
        if upper.startswith("DELETE"):
            return self._delete_to_select(sql)
        if upper.startswith("UPDATE"):
            return self._update_to_select(sql)
        return None


def _parse_values_list(s: str) -> list[tuple[Any, ...]]:
    """Parse a VALUES list like (1,'a'), (2,NULL) into list of tuples. Best-effort."""
    result: list[tuple[Any, ...]] = []
    # Split by "), (" to get each row's value group (handles nested commas in strings)
    parts = _split_value_groups(s)
    for part in parts[:MAX_SNAPSHOT_ROWS]:
        values = _parse_one_row_values(part)
        if values is not None:
            result.append(values)
    return result


def _split_value_groups(s: str) -> list[str]:
    """Split ' (1,'a'), (2,NULL) ' into ['(1,'a')', '(2,NULL)']."""
    out: list[str] = []
    depth = 0
    in_str = False
    q = ""
    start = -1
    for i, c in enumerate(s):
        if in_str:
            if c == q and (i + 1 >= len(s) or s[i + 1] != q):
                in_str = False
            continue
        if c in ("'", '"'):
            in_str = True
            q = c
            continue
        if c == "(":
            if depth == 0:
                start = i
            depth += 1
            continue
        if c == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(s[start : i + 1].strip())
                start = -1
            continue
    return out


def _parse_one_row_values(part: str) -> tuple[Any, ...] | None:
    """Parse one (v1, v2, v3) into tuple. Strips outer parens."""
    part = part.strip()
    if not part.startswith("(") or not part.endswith(")"):
        return None
    inner = part[1:-1].strip()
    if not inner:
        return ()
    values: list[Any] = []
    for v in _split_values(inner):
        v = v.strip()
        if not v or v.upper() == "NULL":
            values.append(None)
        else:
            values.append(_parse_simple_value(v))
    return tuple(values)


def _split_values(inner: str) -> list[str]:
    """Split by comma, respecting quoted strings."""
    out: list[str] = []
    depth = 0
    in_str = False
    q = ""
    start = 0
    for i, c in enumerate(inner):
        if in_str:
            if c == q and (i + 1 >= len(inner) or inner[i + 1] != q):
                in_str = False
            continue
        if c in ("'", '"'):
            in_str = True
            q = c
            continue
        if c == "," and not in_str:
            out.append(inner[start:i])
            start = i + 1
    if start < len(inner):
        out.append(inner[start:])
    return out


def _parse_simple_value(v: str) -> Any:
    """Parse a simple SQL value (number, quoted string, NULL)."""
    v = v.strip()
    if not v or v.upper() == "NULL":
        return None
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1].replace("''", "'").replace('""', '"')
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v
