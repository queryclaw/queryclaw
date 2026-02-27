"""Data modification tool — INSERT / UPDATE / DELETE with safety pipeline."""

from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from queryclaw.db.base import SQLAdapter
from queryclaw.safety.audit import AuditEntry, AuditLogger
from queryclaw.safety.dry_run import DryRunEngine
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.snapshot import SnapshotHelper
from queryclaw.safety.validator import QueryValidator
from queryclaw.tools.base import Tool

ConfirmationCallback = Callable[[str, str], Awaitable[bool]]


class DataModifyTool(Tool):
    """Execute INSERT / UPDATE / DELETE with safety checks.

    Pipeline: policy check -> validate -> dry-run -> confirm (if needed) -> execute -> audit.
    """

    def __init__(
        self,
        db: SQLAdapter,
        policy: SafetyPolicy,
        validator: QueryValidator | None = None,
        audit: AuditLogger | None = None,
        confirmation_callback: ConfirmationCallback | None = None,
    ) -> None:
        self._db = db
        self._policy = policy
        self._validator = validator or QueryValidator(blocked_patterns=policy.blocked_patterns)
        self._dry_run = DryRunEngine(db)
        self._audit = audit or AuditLogger(db)
        self._snapshot = SnapshotHelper(db)
        self._confirm = confirmation_callback

    @property
    def name(self) -> str:
        return "data_modify"

    @property
    def description(self) -> str:
        return (
            "Execute a data modification SQL statement (INSERT, UPDATE, or DELETE). "
            "The statement goes through safety validation, dry-run impact analysis, "
            "and optional human confirmation before execution. "
            "Returns the number of affected rows and execution time."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The INSERT, UPDATE, or DELETE SQL statement to execute.",
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, **kwargs: Any) -> str:
        sql_stripped = sql.strip()

        if not self._policy.allows_write():
            return "Error: Write operations are disabled (read_only mode). Change safety.read_only to false in config."

        upper = sql_stripped.upper().lstrip()
        if not any(upper.startswith(p) for p in ("INSERT", "UPDATE", "DELETE")):
            return "Error: data_modify only accepts INSERT, UPDATE, or DELETE statements. Use ddl_execute for DDL."

        # Map db_type to sqlglot dialect (seekdb is MySQL-compatible)
        dialect = (
            "postgres" if self._db.db_type == "postgresql"
            else "mysql" if self._db.db_type in ("mysql", "seekdb")
            else self._db.db_type
        )
        validation = self._validator.validate(sql_stripped, dialect=dialect)
        if not validation.allowed:
            return f"Error: SQL blocked by safety policy. {'; '.join(validation.warnings)}"

        for table in validation.tables_affected:
            if not self._policy.is_table_allowed(table):
                return f"Error: Table '{table}' is not in the allowed_tables list."

        dry_result = await self._dry_run.analyze(sql_stripped)

        needs_confirm = self._policy.require_confirmation and (
            validation.requires_confirmation
            or self._policy.requires_confirmation_for(dry_result.estimated_rows)
        )

        if needs_confirm:
            if self._confirm is None:
                warnings = validation.warnings + dry_result.warnings
                summary = (
                    f"Confirmation required but no confirmation handler available.\n"
                    f"Estimated affected rows: {dry_result.estimated_rows}\n"
                    f"Warnings: {'; '.join(warnings) if warnings else 'none'}\n"
                    f"SQL: {sql_stripped[:200]}"
                )
                return f"Error: {summary}"

            confirm_msg = self._build_confirm_message(sql_stripped, dry_result, validation.warnings)
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
        status = "success"
        before_snapshot = ""
        after_snapshot = ""
        before_select_sql: str | None = None

        try:
            await self._db.begin_transaction()

            # Capture before snapshot (for UPDATE/DELETE) within transaction
            if self._policy.audit_enabled:
                before_snapshot = await self._snapshot.get_before_snapshot(sql_stripped)
                before_select_sql = self._snapshot.get_before_select_sql(sql_stripped)

            result = await self._db.execute(sql_stripped)

            # Capture after snapshot (for UPDATE: re-run SELECT; for INSERT: parse values)
            if self._policy.audit_enabled:
                after_snapshot = await self._snapshot.get_after_snapshot(
                    sql_stripped,
                    validation.operation_type,
                    before_select_sql,
                )

            await self._db.commit()
            elapsed = (time.monotonic() - start) * 1000
        except Exception as e:
            status = "error"
            elapsed = (time.monotonic() - start) * 1000
            try:
                await self._db.rollback()
            except Exception:
                # Rollback failed — connection is likely broken.
                # Force-close so the adapter can reconnect on next use.
                try:
                    await self._db.close()
                except Exception:
                    pass

            try:
                if self._policy.audit_enabled:
                    await self._audit.log(AuditEntry(
                        operation_type=validation.operation_type,
                        sql_text=sql_stripped,
                        status=status,
                        execution_time_ms=round(elapsed, 2),
                        metadata={"error": str(e)},
                        before_snapshot=before_snapshot,
                        after_snapshot=after_snapshot,
                    ))
            except Exception:
                pass
            return f"Error: {e}"

        if self._policy.audit_enabled:
            await self._audit.log(AuditEntry(
                operation_type=validation.operation_type,
                sql_text=sql_stripped,
                affected_rows=result.affected_rows,
                execution_time_ms=round(elapsed, 2),
                status=status,
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
            ))

        return (
            f"Success: {result.affected_rows} row(s) affected "
            f"in {round(elapsed, 2)}ms "
            f"({validation.operation_type})"
        )

    @staticmethod
    def _build_confirm_message(sql: str, dry_result: Any, warnings: list[str]) -> str:
        lines = ["The following operation requires confirmation:", ""]
        lines.append(f"SQL: {sql[:300]}")
        lines.append(f"Estimated affected rows: {dry_result.estimated_rows}")
        if dry_result.warnings or warnings:
            lines.append(f"Warnings: {'; '.join(dry_result.warnings + warnings)}")
        if dry_result.explain_plan:
            lines.append(f"\nExecution plan:\n{dry_result.explain_plan[:500]}")
        return "\n".join(lines)
