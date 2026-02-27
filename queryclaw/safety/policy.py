"""Safety policy configuration for database operations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SafetyPolicy:
    """Configurable safety rules governing what operations are allowed.

    Defaults to read-only mode (Phase 1 behavior). Set ``read_only=False``
    to enable write operations through the safety pipeline.
    """

    read_only: bool = True
    max_affected_rows: int = 1000
    require_confirmation: bool = True
    allowed_tables: list[str] | None = None
    blocked_patterns: list[str] = field(default_factory=lambda: [
        "DROP DATABASE",
        "DROP SCHEMA",
    ])
    audit_enabled: bool = True

    def allows_write(self) -> bool:
        return not self.read_only

    def is_table_allowed(self, table: str) -> bool:
        if self.allowed_tables is None:
            return True
        return table.lower() in {t.lower() for t in self.allowed_tables}

    def requires_confirmation_for(self, affected_rows: int) -> bool:
        if not self.require_confirmation:
            return False
        return affected_rows > self.max_affected_rows
