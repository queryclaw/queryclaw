"""Async message queue for decoupled channel-agent communication."""

from __future__ import annotations

import asyncio

from queryclaw.bus.events import InboundMessage, OutboundMessage

# Keywords for parsing confirm/cancel in channel mode
_CONFIRM_KEYWORDS = {"确认", "confirm", "yes", "y", "ok", "批准", "执行"}
_CANCEL_KEYWORDS = {"取消", "cancel", "no", "n", "拒绝", "不"}


def _parse_confirm(content: str) -> bool:
    """Parse user reply as confirm (True) or cancel (False). Ambiguous defaults to cancel."""
    normalized = content.strip().lower()
    if any(kw in normalized for kw in _CONFIRM_KEYWORDS):
        return True
    if any(kw in normalized for kw in _CANCEL_KEYWORDS):
        return False
    return False


class ConfirmationStore:
    """Tracks pending confirmations per session for channel-mode interactive confirmation."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[asyncio.Future[bool], str]] = {}

    def register(self, session_key: str, future: asyncio.Future[bool], summary: str) -> None:
        self._pending[session_key] = (future, summary)

    def resolve(self, session_key: str, content: str) -> bool | None:
        """If session has pending confirmation, parse content and resolve. Returns True/False if resolved, None if no pending."""
        entry = self._pending.pop(session_key, None)
        if entry is None:
            return None
        future, _ = entry
        if future.done():
            return None
        result = _parse_confirm(content)
        future.set_result(result)
        return result

    def cancel_all(self, session_key: str) -> None:
        """Cancel pending confirmation (e.g. on timeout)."""
        entry = self._pending.pop(session_key, None)
        if entry:
            future, _ = entry
            if not future.done():
                future.cancel()


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._confirm_store = ConfirmationStore()

    def register_confirmation(self, session_key: str, future: asyncio.Future[bool], summary: str) -> None:
        """Register a pending confirmation for the session. Used by channel-mode confirmation callback."""
        self._confirm_store.register(session_key, future, summary)

    def cancel_confirmation(self, session_key: str) -> None:
        """Cancel pending confirmation (e.g. on timeout)."""
        self._confirm_store.cancel_all(session_key)

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent. Intercepts confirm/cancel replies for pending confirmations."""
        resolved = self._confirm_store.resolve(msg.session_key, msg.content)
        if resolved is not None:
            return
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
