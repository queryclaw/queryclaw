"""Explicit transaction management tool."""

from __future__ import annotations

from typing import Any

from queryclaw.db.base import SQLAdapter
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.tools.base import Tool


class TransactionTool(Tool):
    """Allow the agent to explicitly manage transactions.

    Useful when multiple DML statements need to be grouped atomically.
    """

    def __init__(self, db: SQLAdapter, policy: SafetyPolicy) -> None:
        self._db = db
        self._policy = policy

    @property
    def name(self) -> str:
        return "transaction"

    @property
    def description(self) -> str:
        return (
            "Manage database transactions explicitly. "
            "Actions: 'begin' (start a transaction), "
            "'commit' (save changes), "
            "'rollback' (discard changes). "
            "Use this when multiple data_modify calls need to succeed or fail together."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["begin", "commit", "rollback"],
                    "description": "The transaction action to perform.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        if not self._policy.allows_write():
            return "Error: Write operations are disabled (read_only mode)."

        try:
            match action:
                case "begin":
                    await self._db.begin_transaction()
                    return "Transaction started."
                case "commit":
                    await self._db.commit()
                    return "Transaction committed."
                case "rollback":
                    await self._db.rollback()
                    return "Transaction rolled back."
                case _:
                    return f"Error: Unknown action '{action}'. Use 'begin', 'commit', or 'rollback'."
        except Exception as e:
            return f"Error: {e}"
