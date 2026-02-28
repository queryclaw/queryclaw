"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from queryclaw.bus.events import OutboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.channels.base import BaseChannel
from queryclaw.config.schema import Config


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Feishu, DingTalk)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels based on config."""
        if self.config.channels.feishu.enabled:
            try:
                from queryclaw.channels.feishu import FeishuChannel

                self.channels["feishu"] = FeishuChannel(
                    self.config.channels.feishu,
                    self.bus,
                )
                logger.info("Feishu channel enabled")
            except ImportError as e:
                logger.warning("Feishu channel not available: {}", e)

        if self.config.channels.dingtalk.enabled:
            try:
                from queryclaw.channels.dingtalk import DingTalkChannel

                self.channels["dingtalk"] = DingTalkChannel(
                    self.config.channels.dingtalk,
                    self.bus,
                )
                logger.info("DingTalk channel enabled")
            except ImportError as e:
                logger.warning("DingTalk channel not available: {}", e)

    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            await channel.start()
        except Exception as e:
            logger.error("Failed to start channel {}: {}", name, e)

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        if not self.channels:
            logger.warning("No channels enabled")
            return

        tasks = []
        for name, channel in self.channels.items():
            logger.info("Starting {} channel...", name)
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info("Stopped {} channel", name)
            except Exception as e:
                logger.error("Error stopping {}: {}", name, e)

    def _get_broadcast_chat_id(self, channel_name: str, source: str) -> str | None:
        """Get chat_id for cron/heartbeat broadcast to a channel. Returns None if not configured."""
        ch_cfg = getattr(self.config.channels, channel_name, None)
        if not ch_cfg:
            return None
        if source == "heartbeat":
            chat_id = getattr(ch_cfg, "heartbeat_chat_id", "") or getattr(ch_cfg, "cron_chat_id", "")
        else:
            chat_id = getattr(ch_cfg, "cron_chat_id", "")
        default = getattr(getattr(self.config, source, None), "default_chat_id", "") or ""
        return chat_id or default or None

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0,
                )

                if msg.channel in ("cron", "heartbeat"):
                    sent = False
                    for ch_name, channel in self.channels.items():
                        chat_id = self._get_broadcast_chat_id(ch_name, msg.channel)
                        if not chat_id:
                            logger.debug(
                                "Skipping {} for {}: no cron_chat_id/heartbeat_chat_id configured",
                                ch_name,
                                msg.channel,
                            )
                            continue
                        try:
                            meta = {**(msg.metadata or {}), "source": msg.channel}
                            if ch_name == "dingtalk":
                                meta["conversation_type"] = getattr(
                                    channel.config, "cron_conversation_type", "2"
                                )
                            broadcast_msg = OutboundMessage(
                                channel=ch_name,
                                chat_id=chat_id,
                                content=msg.content,
                                metadata=meta,
                            )
                            await channel.send(broadcast_msg)
                            sent = True
                        except Exception as e:
                            logger.error("Error broadcasting to {}: {}", ch_name, e)
                    if not sent:
                        logger.info(
                            "[{}] No channels configured for broadcast. Output: {}",
                            msg.channel,
                            msg.content[:500] + ("..." if len(msg.content) > 500 else ""),
                        )
                else:
                    channel = self.channels.get(msg.channel)
                    if channel:
                        try:
                            await channel.send(msg)
                        except Exception as e:
                            logger.error("Error sending to {}: {}", msg.channel, e)
                    else:
                        logger.warning("Unknown channel: {}", msg.channel)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {"enabled": True, "running": channel.is_running}
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
