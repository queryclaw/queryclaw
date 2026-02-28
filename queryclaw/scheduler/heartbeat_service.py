"""Heartbeat service — periodically injects health-check prompts into the message bus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from queryclaw.bus.events import InboundMessage
from queryclaw.config.schema import HeartbeatConfig

if TYPE_CHECKING:
    from queryclaw.bus.queue import MessageBus


class HeartbeatService:
    """Runs at a fixed interval and publishes a health-check prompt for the agent to process."""

    def __init__(self, bus: MessageBus, config: HeartbeatConfig) -> None:
        self._bus = bus
        self._config = config
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat loop."""
        if not self._config.enabled or self._config.interval_minutes <= 0:
            return

        self._running = True
        interval_sec = self._config.interval_minutes * 60
        logger.info("Heartbeat service started (interval: {} min)", self._config.interval_minutes)

        import asyncio

        while self._running:
            await asyncio.sleep(interval_sec)
            if not self._running:
                break
            try:
                logger.debug("Heartbeat fired")
                msg = InboundMessage(
                    channel="heartbeat",
                    sender_id="heartbeat",
                    chat_id="heartbeat",
                    content=self._config.prompt,
                    session_key_override="heartbeat:main",
                    metadata={"source": "heartbeat"},
                )
                await self._bus.publish_inbound(msg)
            except Exception as e:
                logger.exception("Heartbeat failed: {}", e)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("Heartbeat service stopped")
