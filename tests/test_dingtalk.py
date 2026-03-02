"""Tests for DingTalk channel, including WebSocket reconnection fix."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from queryclaw.bus.queue import MessageBus
from queryclaw.channels.dingtalk import DingTalkChannel
from queryclaw.config.schema import DingTalkConfig


@pytest.fixture
def dingtalk_config() -> DingTalkConfig:
    return DingTalkConfig(
        enabled=True,
        client_id="test_app_key",
        client_secret="test_app_secret",
    )


@pytest.fixture
def bus() -> MessageBus:
    return MessageBus()


def _make_mock_ws_context(exit_immediately: bool = True):
    """Create async context manager for websockets.connect that exits immediately."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    if exit_immediately:
        mock_conn.__aiter__ = lambda self: self
        mock_conn.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
    return mock_conn


class TestDingTalkStreamLoop:
    """Tests for _stream_loop: non-blocking reconnection, CancelledError propagation, backoff."""

    @pytest.mark.asyncio
    async def test_open_connection_runs_in_executor_not_blocking(
        self, dingtalk_config: DingTalkConfig, bus: MessageBus
    ) -> None:
        """open_connection must run in executor to avoid blocking the event loop."""
        run_in_executor_calls: list = []

        with (
            patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", True),
            patch("queryclaw.channels.dingtalk.Credential"),
            patch("queryclaw.channels.dingtalk.DingTalkStreamClient") as mock_client_cls,
            patch("queryclaw.channels.dingtalk.ChatbotMessage"),
            patch("queryclaw.channels.dingtalk.websockets") as mock_ws,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.pre_start = MagicMock()
            mock_client.open_connection = MagicMock(
                return_value={"endpoint": "wss://test.example/connect", "ticket": "ticket123"}
            )
            mock_client.keepalive = AsyncMock()
            mock_client.background_task = AsyncMock()
            mock_ws.connect.return_value = _make_mock_ws_context()

            channel = DingTalkChannel(dingtalk_config, bus)
            channel._running = True
            channel._client = mock_client
            channel._http = MagicMock()

            loop = asyncio.get_running_loop()
            original_run = loop.run_in_executor

            def patched_run_in_executor(executor, func, *args):
                run_in_executor_calls.append((func, args))
                return original_run(executor, lambda: func(*args))

            with patch.object(loop, "run_in_executor", patched_run_in_executor):
                task = asyncio.create_task(channel._stream_loop())
                await asyncio.sleep(0.15)
                channel._running = False
                await asyncio.sleep(0.2)
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except asyncio.TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            assert len(run_in_executor_calls) >= 1
            func, _ = run_in_executor_calls[0]
            assert func is mock_client.open_connection

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_on_stop(
        self, dingtalk_config: DingTalkConfig, bus: MessageBus
    ) -> None:
        """CancelledError must propagate so the task can be cleanly cancelled."""
        with (
            patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", True),
            patch("queryclaw.channels.dingtalk.Credential"),
            patch("queryclaw.channels.dingtalk.DingTalkStreamClient") as mock_client_cls,
            patch("queryclaw.channels.dingtalk.ChatbotMessage"),
            patch("queryclaw.channels.dingtalk.websockets") as mock_ws,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.pre_start = MagicMock()
            mock_client.open_connection = MagicMock(
                return_value={"endpoint": "wss://test/connect", "ticket": "t"}
            )
            mock_client.keepalive = AsyncMock()
            mock_client.background_task = AsyncMock()
            mock_ws.connect.return_value = _make_mock_ws_context()

            channel = DingTalkChannel(dingtalk_config, bus)
            channel._running = True
            channel._client = mock_client
            channel._http = MagicMock()

            task = asyncio.create_task(channel._stream_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_reconnect_resets_count_on_success(
        self, dingtalk_config: DingTalkConfig, bus: MessageBus
    ) -> None:
        """Reconnect count resets to 0 after successful connection."""
        with (
            patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", True),
            patch("queryclaw.channels.dingtalk.Credential"),
            patch("queryclaw.channels.dingtalk.DingTalkStreamClient") as mock_client_cls,
            patch("queryclaw.channels.dingtalk.ChatbotMessage"),
            patch("queryclaw.channels.dingtalk.websockets") as mock_ws,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.pre_start = MagicMock()
            mock_client.open_connection = MagicMock(
                return_value={"endpoint": "wss://test/connect", "ticket": "t"}
            )
            mock_client.keepalive = AsyncMock()
            mock_client.background_task = AsyncMock()
            mock_ws.connect.return_value = _make_mock_ws_context()

            channel = DingTalkChannel(dingtalk_config, bus)
            channel._running = True
            channel._client = mock_client
            channel._http = MagicMock()
            channel._reconnect_count = 5
            channel._last_connected_at = 0

            task = asyncio.create_task(channel._stream_loop())
            await asyncio.sleep(0.2)
            channel._running = False
            await asyncio.sleep(0.15)
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            assert channel._reconnect_count == 0
            assert channel._connected is False
            assert channel._last_connected_at > 0

    @pytest.mark.asyncio
    async def test_connection_closed_increments_backoff(
        self, dingtalk_config: DingTalkConfig, bus: MessageBus
    ) -> None:
        """ConnectionClosed (e.g. from async for) increments reconnect_count and applies backoff."""
        try:
            import websockets.exceptions
        except ImportError:
            pytest.skip("websockets not installed")

        # Simulate: connect succeeds, then async for raises ConnectionClosed (like "no close frame")
        mock_conn = _make_mock_ws_context()
        mock_conn.__anext__ = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosedError(
                rcvd=None, sent=None, rcvd_then_sent=None
            )
        )

        with (
            patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", True),
            patch("queryclaw.channels.dingtalk.Credential"),
            patch("queryclaw.channels.dingtalk.DingTalkStreamClient") as mock_client_cls,
            patch("queryclaw.channels.dingtalk.ChatbotMessage"),
            patch("queryclaw.channels.dingtalk.websockets") as mock_ws,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.pre_start = MagicMock()
            mock_client.open_connection = MagicMock(
                return_value={"endpoint": "wss://test/connect", "ticket": "t"}
            )
            mock_client.keepalive = AsyncMock()
            mock_client.background_task = AsyncMock()
            mock_ws.connect.return_value = mock_conn
            mock_ws.exceptions.ConnectionClosed = websockets.exceptions.ConnectionClosed
            mock_ws.exceptions.ConnectionClosedError = websockets.exceptions.ConnectionClosedError

            channel = DingTalkChannel(dingtalk_config, bus)
            channel._running = True
            channel._client = mock_client
            channel._http = MagicMock()
            channel._last_connected_at = 0

            task = asyncio.create_task(channel._stream_loop())
            await asyncio.sleep(0.5)
            channel._running = False
            await asyncio.sleep(0.3)
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            assert channel._reconnect_count >= 1


class TestDingTalkChannelStartStop:
    """Tests for start/stop when SDK is unavailable or misconfigured."""

    @pytest.mark.asyncio
    async def test_start_returns_early_when_sdk_unavailable(
        self, dingtalk_config: DingTalkConfig, bus: MessageBus
    ) -> None:
        with patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", False):
            channel = DingTalkChannel(dingtalk_config, bus)
            await channel.start()
            assert channel._client is None

    @pytest.mark.asyncio
    async def test_start_returns_early_when_no_credentials(
        self, bus: MessageBus
    ) -> None:
        with patch("queryclaw.channels.dingtalk.DINGTALK_AVAILABLE", True):
            config = DingTalkConfig(enabled=True, client_id="", client_secret="")
            channel = DingTalkChannel(config, bus)
            await channel.start()
            assert channel._client is None

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self, dingtalk_config: DingTalkConfig, bus: MessageBus) -> None:
        channel = DingTalkChannel(dingtalk_config, bus)
        channel._running = True
        channel._http = MagicMock()
        channel._http.aclose = AsyncMock()

        await channel.stop()

        assert channel._running is False
        assert channel._connected is False
        assert channel._http is None
