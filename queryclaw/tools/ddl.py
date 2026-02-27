"""DDL execution tool — CREATE / ALTER / DROP with safety checks."""

from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from queryclaw.db.base import SQLAdapter
from queryclaw.safety.audit import AuditEntry, AuditLogger
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.validator import QueryValidator
from queryclaw.tools.base import Tool

ConfirmationCallback = Callable[[str, str], Awaitable[bool]]


class DDLExecuteTool(Tool):
    """Execute DDL statements (CREATE, ALTER, DROP, etc.) with safety checks.

    DROP operations always require confirmation.
    After execution, signals that schema cache should be invalidated.
    """

    def __init__(
        self,
        db: SQLAdapter,
        policy: SafetyPolicy,
        validator: QueryValidator | None = None,
        audit: AuditLogger | None = None,
        confirmation_callback: ConfirmationCallback | None = None,
        on_schema_change: Callable[[], None] | None = None,
    ) -> None:
        self._db = db
        self._policy = policy
        self._validator = validator or QueryValidator(blocked_patterns=policy.blocked_patterns)
        self._audit = audit or AuditLogger(db)
        self._confirm = confirmation_callback
        self._on_schema_change = on_schema_change

    @property
    def name(self) -> str:
        return "ddl_execute"

    @property
    def description(self) -> str:
        return (
            "Execute a DDL statement (CREATE TABLE, ALTER TABLE, DROP TABLE, "
            "CREATE INDEX, etc.). DROP operations require confirmation. "
            "The schema cache is refreshed after successful execution."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The DDL SQL statement to execute.",
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, **kwargs: Any) -> str:
        sql_stripped = sql.strip()

        if not self._policy.allows_write():
            return "Error: Write operations are disabled (read_only mode). Change safety.read_only to false in config."

        upper = sql_stripped.upper().lstrip()
        if not any(upper.startswith(p) for p in ("CREATE", "ALTER", "DROP", "TRUNCATE")):
            return "Error: ddl_execute only accepts DDL statements (CREATE, ALTER, DROP, TRUNCATE). Use data_modify for DML."

        dialect = self._db.db_type if self._db.db_type != "postgresql" else "postgres"
        validation = self._validator.validate(sql_stripped, dialect=dialect)
        if not validation.allowed:
            return f"Error: SQL blocked by safety policy. {'; '.join(validation.warnings)}"

        for table in validation.tables_affected:
            if not self._policy.is_table_allowed(table):
                return f"Error: Table '{table}' is not in the allowed_tables list."

        if validation.requires_confirmation and self._policy.require_confirmation:
            if self._confirm is None:
                return (
                    f"Error: This operation requires confirmation but no confirmation handler is available.\n"
                    f"Operation: {validation.operation_type}\n"
                    f"Warnings: {'; '.join(validation.warnings)}\n"
                    f"SQL: {sql_stripped[:200]}"
                )

            confirm_msg = (
                f"The following DDL operation requires confirmation:\n\n"
                f"SQL: {sql_stripped[:300]}\n"
                f"Type: {validation.operation_type}\n"
                f"Warnings: {'; '.join(validation.warnings)}"
            )
            confirmed = await self._confirm(sql_stripped, confirm_msg)
            if not confirmed:
                await self._audit.log(AuditEntry(
                    operation_type=validation.operation_type,
                    sql_text=sql_stripped,
                    status="rejected",
                ))
                return (
                    "Operation cancelled by user. Do NOT retry this operation. "
                    "Inform the user that the operation was declined and suggest alternatives if needed."
                )

        start = time.monotonic()
        try:
            result = await self._db.execute(sql_stripped)
            elapsed = (time.monotonic() - start) * 1000
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            try:
                if self._policy.audit_enabled:
                    await self._audit.log(AuditEntry(
                        operation_type=validation.operation_type,
                        sql_text=sql_stripped,
                        status="error",
                        execution_time_ms=round(elapsed, 2),
                        metadata={"error": str(e)},
                    ))
            except Exception:
                pass
            return f"Error: {e}"

        try:
            if self._policy.audit_enabled:
                await self._audit.log(AuditEntry(
                    operation_type=validation.operation_type,
                    sql_text=sql_stripped,
                    execution_time_ms=round(elapsed, 2),
                    status="success",
                ))
        except Exception:
            pass

        if self._on_schema_change:
            self._on_schema_change()

        return (
            f"Success: DDL executed in {round(elapsed, 2)}ms "
            f"({validation.operation_type})"
        )
