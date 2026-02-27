"""Tests for message bus and channel abstractions."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from queryclaw.bus.events import InboundMessage, OutboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.channels.base import BaseChannel


class FakeChannelConfig:
    """Minimal config for testing BaseChannel.is_allowed."""

    def __init__(self, allow_from: list[str] | None = None) -> None:
        self.allow_from = allow_from or []


class FakeChannel(BaseChannel):
    """Concrete channel for testing."""

    name = "fake"

    async def start(self) -> None:
        self._running = True
        while self._running:
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        pass


class TestMessageBus:
    @pytest.mark.asyncio
    async def test_publish_consume_inbound(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel="test",
            sender_id="u1",
            chat_id="c1",
            content="hello",
        )
        await bus.publish_inbound(msg)
        assert bus.inbound_size == 1
        consumed = await bus.consume_inbound()
        assert consumed.content == "hello"
        assert consumed.channel == "test"
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_publish_consume_outbound(self) -> None:
        bus = MessageBus()
        msg = OutboundMessage(channel="test", chat_id="c1", content="hi")
        await bus.publish_outbound(msg)
        assert bus.outbound_size == 1
        consumed = await bus.consume_outbound()
        assert consumed.content == "hi"
        assert bus.outbound_size == 0


class TestBaseChannel:
    def test_is_allowed_empty_list(self) -> None:
        config = FakeChannelConfig()
        bus = MessageBus()
        channel = FakeChannel(config, bus)
        assert channel.is_allowed("any_user") is True

    def test_is_allowed_in_list(self) -> None:
        config = FakeChannelConfig(allow_from=["u1", "u2"])
        bus = MessageBus()
        channel = FakeChannel(config, bus)
        assert channel.is_allowed("u1") is True
        assert channel.is_allowed("u2") is True
        assert channel.is_allowed("u3") is False

    @pytest.mark.asyncio
    async def test_handle_message_publishes_to_bus(self) -> None:
        config = FakeChannelConfig()
        bus = MessageBus()
        channel = FakeChannel(config, bus)

        await channel._handle_message(
            sender_id="u1",
            chat_id="c1",
            content="test message",
        )

        assert bus.inbound_size == 1
        msg = await bus.consume_inbound()
        assert msg.channel == "fake"
        assert msg.sender_id == "u1"
        assert msg.chat_id == "c1"
        assert msg.content == "test message"

    @pytest.mark.asyncio
    async def test_handle_message_denied_when_not_in_allow_list(self) -> None:
        config = FakeChannelConfig(allow_from=["u1"])
        bus = MessageBus()
        channel = FakeChannel(config, bus)

        await channel._handle_message(
            sender_id="u2",
            chat_id="c1",
            content="blocked",
        )

        assert bus.inbound_size == 0


class TestInboundMessage:
    def test_session_key_default(self) -> None:
        msg = InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="hi")
        assert msg.session_key == "feishu:c1"

    def test_session_key_override(self) -> None:
        msg = InboundMessage(
            channel="feishu",
            sender_id="u1",
            chat_id="c1",
            content="hi",
            session_key_override="custom:key",
        )
        assert msg.session_key == "custom:key"


class TestChannelConfirmation:
    """Tests for channel-mode confirmation flow (confirm/cancel intercept)."""

    @pytest.mark.asyncio
    async def test_publish_inbound_intercepts_confirm(self) -> None:
        """When pending confirmation exists, '确认' reply resolves future and does not enqueue."""
        bus = MessageBus()
        session_key = "feishu:c1"
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        bus.register_confirmation(session_key, future, "DROP TABLE x")

        async def resolve_later() -> None:
            await asyncio.sleep(0.05)
            await bus.publish_inbound(
                InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="确认")
            )

        asyncio.create_task(resolve_later())
        result = await asyncio.wait_for(future, timeout=1.0)
        assert result is True
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_publish_inbound_intercepts_cancel(self) -> None:
        """When pending confirmation exists, '取消' reply resolves future to False."""
        bus = MessageBus()
        session_key = "feishu:c1"
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        bus.register_confirmation(session_key, future, "DELETE FROM users")

        async def resolve_later() -> None:
            await asyncio.sleep(0.05)
            await bus.publish_inbound(
                InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="取消")
            )

        asyncio.create_task(resolve_later())
        result = await asyncio.wait_for(future, timeout=1.0)
        assert result is False
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_publish_inbound_passes_through_when_no_pending(self) -> None:
        """When no pending confirmation, message is enqueued normally."""
        bus = MessageBus()
        msg = InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="确认")
        await bus.publish_inbound(msg)
        assert bus.inbound_size == 1
        consumed = await bus.consume_inbound()
        assert consumed.content == "确认"

    @pytest.mark.asyncio
    async def test_confirm_keywords_parsed_as_true(self) -> None:
        """Various confirm keywords resolve to True."""
        keywords = ["确认", "confirm", "yes", "ok", "批准"]
        for kw in keywords:
            bus = MessageBus()
            session_key = "test:c1"
            future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
            bus.register_confirmation(session_key, future, "summary")
            await bus.publish_inbound(
                InboundMessage(channel="test", sender_id="u1", chat_id="c1", content=kw)
            )
            assert await asyncio.wait_for(future, timeout=0.5) is True

    @pytest.mark.asyncio
    async def test_cancel_keywords_parsed_as_false(self) -> None:
        """Various cancel keywords resolve to False."""
        keywords = ["取消", "cancel", "no", "拒绝"]
        for kw in keywords:
            bus = MessageBus()
            session_key = "test:c1"
            future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
            bus.register_confirmation(session_key, future, "summary")
            await bus.publish_inbound(
                InboundMessage(channel="test", sender_id="u1", chat_id="c1", content=kw)
            )
            assert await asyncio.wait_for(future, timeout=0.5) is False

    @pytest.mark.asyncio
    async def test_cancel_confirmation_cancels_future(self) -> None:
        """cancel_confirmation cancels the pending future."""
        bus = MessageBus()
        session_key = "feishu:c1"
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        bus.register_confirmation(session_key, future, "summary")
        bus.cancel_confirmation(session_key)

        with pytest.raises(asyncio.CancelledError):
            await future

        # Subsequent inbound for same session goes through (no pending)
        await bus.publish_inbound(
            InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="确认")
        )
        assert bus.inbound_size == 1
