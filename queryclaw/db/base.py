"""Database adapter abstract base classes and data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryResult:
    """Result of a database query."""

    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    affected_rows: int = 0
    execution_time_ms: float = 0

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_text(self, max_rows: int = 100) -> str:
        """Format as a readable text table."""
        if not self.columns:
            return f"(no columns, {self.affected_rows} rows affected)"
        lines = [" | ".join(self.columns)]
        lines.append("-+-".join("-" * max(len(c), 4) for c in self.columns))
        for row in self.rows[:max_rows]:
            lines.append(" | ".join(str(v) for v in row))
        if len(self.rows) > max_rows:
            lines.append(f"... ({len(self.rows) - max_rows} more rows)")
        return "\n".join(lines)


@dataclass
class ColumnInfo:
    """Column metadata."""

    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None
    is_primary_key: bool = False
    extra: str = ""


@dataclass
class TableInfo:
    """Table metadata."""

    name: str
    schema: str = ""
    row_count: int | None = None
    engine: str | None = None


@dataclass
class IndexInfo:
    """Index metadata."""

    name: str
    columns: list[str] = field(default_factory=list)
    unique: bool = False
    type: str = "BTREE"


@dataclass
class ForeignKeyInfo:
    """Foreign key metadata."""

    name: str
    columns: list[str] = field(default_factory=list)
    ref_table: str = ""
    ref_columns: list[str] = field(default_factory=list)


class DatabaseAdapter(ABC):
    """Base adapter interface for all database types."""

    @abstractmethod
    async def connect(self, **kwargs: Any) -> None:
        """Establish connection to the database."""

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""

    @abstractmethod
    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        """Execute a SQL statement and return results."""

    @abstractmethod
    async def get_tables(self) -> list[TableInfo]:
        """List all tables in the database."""

    @property
    @abstractmethod
    def db_type(self) -> str:
        """Return the database type identifier (e.g. 'mysql', 'sqlite')."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the adapter currently has an active connection."""


class SQLAdapter(DatabaseAdapter):
    """Specialized adapter for SQL (relational) databases.

    Adds schema introspection and transaction methods on top of the base adapter.
    """

    @abstractmethod
    async def get_columns(self, table: str) -> list[ColumnInfo]:
        """Get column metadata for a table."""

    @abstractmethod
    async def get_indexes(self, table: str) -> list[IndexInfo]:
        """Get index metadata for a table."""

    @abstractmethod
    async def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        """Get foreign key metadata for a table."""

    @abstractmethod
    async def explain(self, sql: str) -> QueryResult:
        """Run EXPLAIN on a SQL statement and return the plan."""

    async def begin_transaction(self) -> None:
        """Begin an explicit transaction."""
        await self.execute("BEGIN")

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.execute("COMMIT")

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self.execute("ROLLBACK")
