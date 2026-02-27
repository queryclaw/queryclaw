"""Audit logger — records all write operations to an audit table."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from queryclaw.db.base import SQLAdapter


AUDIT_TABLE = "_queryclaw_audit_log"

_CREATE_AUDIT_TABLE_SQLITE = f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT DEFAULT '',
    operation_type TEXT NOT NULL,
    sql_text TEXT NOT NULL,
    affected_rows INTEGER DEFAULT 0,
    execution_time_ms REAL DEFAULT 0,
    before_snapshot TEXT DEFAULT '',
    after_snapshot TEXT DEFAULT '',
    user_message TEXT DEFAULT '',
    status TEXT DEFAULT 'success',
    metadata TEXT DEFAULT ''
)
"""

# MySQL 5.7+ strict mode: TEXT/BLOB cannot have DEFAULT; omit DEFAULT for TEXT columns.
# Avoid reserved word "timestamp" by using "logged_at".
_CREATE_AUDIT_TABLE_MYSQL = f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    logged_at DATETIME(3) NOT NULL,
    session_id VARCHAR(255) DEFAULT '',
    operation_type VARCHAR(50) NOT NULL,
    sql_text TEXT NOT NULL,
    affected_rows INT DEFAULT 0,
    execution_time_ms DOUBLE DEFAULT 0,
    before_snapshot TEXT,
    after_snapshot TEXT,
    user_message TEXT,
    status VARCHAR(20) DEFAULT 'success',
    metadata TEXT
)
"""

_CREATE_AUDIT_TABLE_PG = f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    session_id TEXT DEFAULT '',
    operation_type TEXT NOT NULL,
    sql_text TEXT NOT NULL,
    affected_rows INT DEFAULT 0,
    execution_time_ms DOUBLE PRECISION DEFAULT 0,
    before_snapshot TEXT DEFAULT '',
    after_snapshot TEXT DEFAULT '',
    user_message TEXT DEFAULT '',
    status TEXT DEFAULT 'success',
    metadata TEXT DEFAULT ''
)
"""


@dataclass
class AuditEntry:
    """One audit log entry."""

    operation_type: str
    sql_text: str
    affected_rows: int = 0
    execution_time_ms: float = 0
    before_snapshot: str = ""
    after_snapshot: str = ""
    user_message: str = ""
    status: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


class AuditLogger:
    """Records write operations to an in-database audit table."""

    def __init__(self, db: SQLAdapter, session_id: str = "") -> None:
        self._db = db
        self._session_id = session_id
        self._initialized = False

    async def ensure_table(self) -> None:
        """Create the audit table if it doesn't exist."""
        if self._initialized:
            return

        db_type = self._db.db_type
        if db_type == "sqlite":
            ddl = _CREATE_AUDIT_TABLE_SQLITE
        elif db_type in ("mysql", "seekdb"):
            # SeekDB is MySQL protocol compatible (OceanBase)
            ddl = _CREATE_AUDIT_TABLE_MYSQL
        elif db_type == "postgresql":
            ddl = _CREATE_AUDIT_TABLE_PG
        else:
            ddl = _CREATE_AUDIT_TABLE_SQLITE

        try:
            await self._db.execute(ddl)
            self._initialized = True
        except Exception:
            pass

    async def log(self, entry: AuditEntry) -> None:
        """Write an audit entry to the database."""
        await self.ensure_table()

        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(entry.metadata, default=str) if entry.metadata else ""

        db_type = self._db.db_type
        if db_type == "postgresql":
            await self._db.execute(
                f"INSERT INTO {AUDIT_TABLE} "
                "(timestamp, session_id, operation_type, sql_text, affected_rows, "
                "execution_time_ms, before_snapshot, after_snapshot, user_message, status, metadata) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
                (
                    now,
                    entry.session_id or self._session_id,
                    entry.operation_type,
                    entry.sql_text,
                    entry.affected_rows,
                    entry.execution_time_ms,
                    entry.before_snapshot,
                    entry.after_snapshot,
                    entry.user_message,
                    entry.status,
                    meta_json,
                ),
            )
        elif db_type in ("mysql", "seekdb"):
            # MySQL/SeekDB use logged_at (avoids reserved word "timestamp") and %s placeholders
            placeholder = "%s"
            sql = (
                f"INSERT INTO {AUDIT_TABLE} "
                "(logged_at, session_id, operation_type, sql_text, affected_rows, "
                "execution_time_ms, before_snapshot, after_snapshot, user_message, status, metadata) "
                f"VALUES ({', '.join([placeholder] * 11)})"
            )
            await self._db.execute(
                sql,
                (
                    now,
                    entry.session_id or self._session_id,
                    entry.operation_type,
                    entry.sql_text,
                    entry.affected_rows,
                    entry.execution_time_ms,
                    entry.before_snapshot,
                    entry.after_snapshot,
                    entry.user_message,
                    entry.status,
                    meta_json,
                ),
            )
        else:
            # SQLite and others: timestamp column, ? placeholders
            sql = (
                f"INSERT INTO {AUDIT_TABLE} "
                "(timestamp, session_id, operation_type, sql_text, affected_rows, "
                "execution_time_ms, before_snapshot, after_snapshot, user_message, status, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            await self._db.execute(
                sql,
                (
                    now,
                    entry.session_id or self._session_id,
                    entry.operation_type,
                    entry.sql_text,
                    entry.affected_rows,
                    entry.execution_time_ms,
                    entry.before_snapshot,
                    entry.after_snapshot,
                    entry.user_message,
                    entry.status,
                    meta_json,
                ),
            )
