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
