"""In-memory conversation history for the agent."""

from __future__ import annotations

from typing import Any


class MemoryStore:
    """Simple in-memory conversation history.

    Phase 1 uses a plain list; Phase 3 will add database-backed
    persistent memory with semantic recall.
    """

    def __init__(self, max_messages: int = 100) -> None:
        self._messages: list[dict[str, Any]] = []
        self._max_messages = max_messages

    def add(self, role: str, content: str) -> None:
        """Add a message to history."""
        self._messages.append({"role": role, "content": content})
        self._trim()

    def add_tool_call(self, assistant_msg: dict[str, Any]) -> None:
        """Add an assistant message that contains tool_calls (preserving the full dict)."""
        self._messages.append(assistant_msg)
        self._trim()

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add a tool result message."""
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        })
        self._trim()

    def get_recent(self, n: int | None = None) -> list[dict[str, Any]]:
        """Get the most recent n messages (all if n is None)."""
        if n is None:
            return list(self._messages)
        return list(self._messages[-n:])

    def clear(self) -> None:
        """Clear all history."""
        self._messages.clear()

    def _trim(self) -> None:
        """Keep only the most recent max_messages."""
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
