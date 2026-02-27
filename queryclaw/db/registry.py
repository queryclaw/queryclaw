"""Database adapter registry and factory."""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import DatabaseAdapter


class AdapterRegistry:
    """Registry for database adapters.

    Maintains a mapping from db type names to adapter classes,
    and provides a factory method to create adapter instances.
    """

    _adapters: dict[str, type[DatabaseAdapter]] = {}

    @classmethod
    def register(cls, db_type: str, adapter_cls: type[DatabaseAdapter]) -> None:
        """Register an adapter class for a database type."""
        cls._adapters[db_type] = adapter_cls

    @classmethod
    def get(cls, db_type: str) -> type[DatabaseAdapter] | None:
        """Get the adapter class for a database type."""
        return cls._adapters.get(db_type)

    @classmethod
    def create(cls, db_type: str) -> DatabaseAdapter:
        """Create an adapter instance for the given database type.

        Raises:
            ValueError: If the db_type is not registered.
        """
        adapter_cls = cls._adapters.get(db_type)
        if adapter_cls is None:
            available = ", ".join(sorted(cls._adapters)) or "(none)"
            raise ValueError(
                f"Unsupported database type: {db_type!r}. Available: {available}"
            )
        return adapter_cls()

    @classmethod
    def available_types(cls) -> list[str]:
        """List all registered database type names."""
        return sorted(cls._adapters)

    @classmethod
    async def create_and_connect(cls, **kwargs: Any) -> DatabaseAdapter:
        """Create an adapter and connect using the provided kwargs.

        kwargs must include 'type' (the db type) plus connection params.
        """
        db_type = kwargs.pop("type", None)
        if not db_type:
            raise ValueError("Missing 'type' in connection config")
        adapter = cls.create(db_type)
        await adapter.connect(**kwargs)
        return adapter


def _register_defaults() -> None:
    """Register built-in adapters."""
    from queryclaw.db.mysql import MySQLAdapter
    from queryclaw.db.postgresql import PostgreSQLAdapter
    from queryclaw.db.seekdb import SeekDBAdapter
    from queryclaw.db.sqlite import SQLiteAdapter

    AdapterRegistry.register("mysql", MySQLAdapter)
    AdapterRegistry.register("postgresql", PostgreSQLAdapter)
    AdapterRegistry.register("seekdb", SeekDBAdapter)
    AdapterRegistry.register("sqlite", SQLiteAdapter)


_register_defaults()
