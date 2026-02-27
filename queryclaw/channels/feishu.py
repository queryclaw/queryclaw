"""Feishu/Lark channel implementation using lark-oapi SDK with WebSocket long connection."""

import asyncio
import json
import threading
from collections import OrderedDict
from typing import Any

from loguru import logger

from queryclaw.bus.events import OutboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.channels.base import BaseChannel
from queryclaw.config.schema import FeishuConfig

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        Emoji,
        P2ImMessageReceiveV1,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None
    Emoji = None


def _extract_post_content(content_json: dict) -> str:
    """Extract plain text from Feishu post (rich text) message content."""
    def extract_from_lang(lang_content: dict) -> str | None:
        if not isinstance(lang_content, dict):
            return None
        title = lang_content.get("title", "")
        content_blocks = lang_content.get("content", [])
        if not isinstance(content_blocks, list):
            return None
        text_parts = []
        if title:
            text_parts.append(title)
        for block in content_blocks:
            if not isinstance(block, list):
                continue
            for element in block:
                if isinstance(element, dict):
                    tag = element.get("tag")
                    if tag == "text":
                        text_parts.append(element.get("text", ""))
                    elif tag == "a":
                        text_parts.append(element.get("text", ""))
                    elif tag == "at":
                        text_parts.append(f"@{element.get('user_name', 'user')}")
        return " ".join(text_parts).strip() or None

    if "content" in content_json:
        text = extract_from_lang(content_json)
        if text:
            return text
    for lang_key in ("zh_cn", "en_us", "ja_jp"):
        lang_content = content_json.get(lang_key)
        text = extract_from_lang(lang_content) if isinstance(lang_content, dict) else None
        if text:
            return text
    return ""


def _extract_interactive_content(content: dict) -> list[str]:
    """Recursively extract text from interactive card content."""
    parts = []
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return [content] if content.strip() else []
    if not isinstance(content, dict):
        return parts
    for element in content.get("elements", []) or []:
        if isinstance(element, dict):
            tag = element.get("tag", "")
            if tag in ("markdown", "lark_md"):
                c = element.get("content", "")
                if c:
                    parts.append(c)
            elif tag == "plain_text":
                c = element.get("content", "")
                if c:
                    parts.append(c)
    if content.get("card"):
        parts.extend(_extract_interactive_content(content["card"]))
    return parts


class FeishuChannel(BaseChannel):
    """
    Feishu/Lark channel using WebSocket long connection.

    Uses WebSocket to receive events - no public IP or webhook required.

    Requires:
    - App ID and App Secret from Feishu Open Platform
    - Bot capability enabled
    - Event subscription enabled (im.message.receive_v1)
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client: Any = None
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _build_card_elements(self, content: str) -> list[dict]:
        """Build Feishu card elements from markdown content."""
        return [{"tag": "markdown", "content": content}]

    async def start(self) -> None:
        """Start the Feishu bot with WebSocket long connection."""
        if not FEISHU_AVAILABLE:
            logger.error("Feishu SDK not installed. Run: pip install queryclaw[feishu]")
            return

        if not self.config.app_id or not self.config.app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return

        self._running = True
        self._loop = asyncio.get_running_loop()

        self._client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

        event_handler = (
            lark.EventDispatcherHandler.builder(
                self.config.encrypt_key or "",
                self.config.verification_token or "",
            )
            .register_p2_im_message_receive_v1(self._on_message_sync)
            .build()
        )

        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        def run_ws() -> None:
            import time
            # lark-oapi ws.Client uses a module-level event loop; it fails when the main
            # thread's loop is already running. Create a dedicated loop for this thread.
            ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_loop)
            try:
                import lark_oapi.ws.client as ws_client
                ws_client.loop = ws_loop
            except Exception:
                pass
            while self._running:
                try:
                    self._ws_client.start()
                except Exception as e:
                    logger.warning("Feishu WebSocket error: {}", e)
                if self._running:
                    time.sleep(5)
            ws_loop.close()

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        logger.info("Feishu bot started with WebSocket long connection")
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Feishu bot."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception as e:
                logger.warning("Error stopping WebSocket client: {}", e)
        logger.info("Feishu bot stopped")

    def _add_reaction_sync(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """Add reaction sync (runs in thread pool)."""
        if not self._client or not FEISHU_AVAILABLE or Emoji is None:
            return
        try:
            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message_reaction.create(request)
            if not response.success():
                logger.debug("Failed to add reaction: code={}, msg={}", response.code, response.msg)
        except Exception as e:
            logger.debug("Error adding reaction: {}", e)

    def _send_message_sync(self, receive_id_type: str, receive_id: str, msg_type: str, content: str) -> bool:
        """Send a message synchronously."""
        if not self._client:
            return False
        try:
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message.create(request)
            if not response.success():
                logger.error(
                    "Failed to send Feishu {} message: code={}, msg={}",
                    msg_type, response.code, response.msg,
                )
                return False
            return True
        except Exception as e:
            logger.error("Error sending Feishu {} message: {}", msg_type, e)
            return False

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Feishu (text-only, interactive card)."""
        if not self._client:
            logger.warning("Feishu client not initialized")
            return

        if not msg.content or not msg.content.strip():
            return

        try:
            receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
            loop = asyncio.get_running_loop()
            card = {
                "config": {"wide_screen_mode": True},
                "elements": self._build_card_elements(msg.content),
            }
            await loop.run_in_executor(
                None,
                self._send_message_sync,
                receive_id_type,
                msg.chat_id,
                "interactive",
                json.dumps(card, ensure_ascii=False),
            )
        except Exception as e:
            logger.error("Error sending Feishu message: {}", e)

    def _on_message_sync(self, data: Any) -> None:
        """Sync handler for incoming messages (called from WebSocket thread)."""
        logger.info("[Feishu] Received event (sync handler)")
        if not self._loop or not self._loop.is_running():
            logger.warning("[Feishu] Main loop not available, cannot process message")
            return
        asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)

    async def _on_message(self, data: Any) -> None:
        """Handle incoming message from Feishu."""
        try:
            event = data.event
            message = event.message
            sender = event.sender

            message_id = message.message_id
            chat_type = getattr(message, "chat_type", "?")
            logger.info("[Feishu] Processing message chat_type={} msg_id={}", chat_type, message_id)
            if message_id in self._processed_message_ids:
                logger.debug("[Feishu] Skipping duplicate message_id")
                return
            self._processed_message_ids[message_id] = None

            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

            if sender.sender_type == "bot":
                logger.debug("[Feishu] Skipping bot sender")
                return

            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = message.chat_id
            chat_type = message.chat_type
            msg_type = message.message_type
            logger.info("[Feishu] chat_id={} msg_type={} sender={}", chat_id, msg_type, sender_id)

            if FEISHU_AVAILABLE and Emoji:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._add_reaction_sync, message_id, "THUMBSUP")

            content_parts = []
            try:
                content_json = json.loads(message.content) if message.content else {}
            except json.JSONDecodeError:
                content_json = {}

            if msg_type == "text":
                text = content_json.get("text", "")
                if text:
                    content_parts.append(text)
            elif msg_type == "post":
                text = _extract_post_content(content_json)
                if text:
                    content_parts.append(text)
            elif msg_type == "interactive":
                parts = _extract_interactive_content(content_json)
                if parts:
                    content_parts.append("\n".join(parts))
            else:
                content_parts.append(f"[{msg_type}]")

            content = "\n".join(content_parts) if content_parts else ""
            if not content:
                logger.warning("[Feishu] Empty content extracted, msg_type={} raw={}", msg_type, (message.content or "")[:100])
                return

            reply_to = chat_id if chat_type == "group" else sender_id
            logger.info("[Feishu] Forwarding to bus: reply_to={} content_len={}", reply_to, len(content))
            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                },
            )

        except Exception as e:
            logger.error("Error processing Feishu message: {}", e)
