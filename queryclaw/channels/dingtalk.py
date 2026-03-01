"""DingTalk/DingDing channel implementation using Stream Mode."""

import asyncio
import json
import time
from typing import Any
from urllib.parse import quote_plus

import httpx
from loguru import logger

from queryclaw.bus.events import OutboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.channels.base import BaseChannel
from queryclaw.config.schema import DingTalkConfig

try:
    from dingtalk_stream import (
        AckMessage,
        CallbackHandler,
        CallbackMessage,
        Credential,
        DingTalkStreamClient,
    )
    from dingtalk_stream.chatbot import ChatbotMessage
    import websockets

    DINGTALK_AVAILABLE = True
except ImportError:
    DINGTALK_AVAILABLE = False
    CallbackHandler = object  # type: ignore[assignment,misc]
    CallbackMessage = None  # type: ignore[assignment,misc]
    AckMessage = None  # type: ignore[assignment,misc]
    ChatbotMessage = None  # type: ignore[assignment,misc]


class QueryClawDingTalkHandler(CallbackHandler):
    """
    DingTalk Stream SDK Callback Handler.
    Parses incoming messages and forwards them to the channel.
    """

    def __init__(self, channel: "DingTalkChannel") -> None:
        super().__init__()
        self.channel = channel

    async def process(self, message: CallbackMessage) -> tuple[str, str]:
        """Process incoming stream message."""
        if not DINGTALK_AVAILABLE or AckMessage is None:
            return "OK", "OK"
        try:
            chatbot_msg = ChatbotMessage.from_dict(message.data)

            content = ""
            if chatbot_msg.text:
                content = chatbot_msg.text.content.strip()
            if not content:
                content = message.data.get("text", {}).get("content", "").strip()

            if not content:
                logger.warning(
                    "Received empty or unsupported message type: {}",
                    chatbot_msg.message_type,
                )
                return AckMessage.STATUS_OK, "OK"

            sender_id = chatbot_msg.sender_staff_id or chatbot_msg.sender_id
            sender_name = chatbot_msg.sender_nick or "Unknown"
            conversation_id = message.data.get("conversationId", "")
            conversation_type = message.data.get("conversationType", "1")

            logger.info("Received DingTalk message from {} ({}): {}", sender_name, sender_id, content)

            task = asyncio.create_task(
                self.channel._on_message(
                    content, sender_id, sender_name,
                    conversation_id=conversation_id,
                    conversation_type=conversation_type,
                )
            )
            self.channel._background_tasks.add(task)
            task.add_done_callback(self.channel._background_tasks.discard)

            return AckMessage.STATUS_OK, "OK"

        except Exception as e:
            logger.error("Error processing DingTalk message: {}", e)
            return AckMessage.STATUS_OK, "Error"


class DingTalkChannel(BaseChannel):
    """
    DingTalk channel using Stream Mode.

    Uses WebSocket to receive events via `dingtalk-stream` SDK.
    Uses direct HTTP API to send messages (SDK is mainly for receiving).

    Note: Currently only supports private (1:1) chat. Group messages are
    received but replies are sent back as private messages to the sender.
    """

    name = "dingtalk"
    _MAX_RECONNECT_DELAY = 60

    def __init__(self, config: DingTalkConfig, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config: DingTalkConfig = config
        self._client: Any = None
        self._http: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._background_tasks: set[asyncio.Task] = set()
        self._connected: bool = False
        self._reconnect_count: int = 0
        self._last_connected_at: float = 0

    async def start(self) -> None:
        """Start the DingTalk bot with Stream Mode.

        Replaces the SDK's built-in start() loop to fix:
        - SDK uses synchronous requests.post() in open_connection(), blocking
          the asyncio event loop during reconnection.
        - SDK swallows asyncio.CancelledError, preventing clean shutdown.
        - No exponential backoff on repeated failures.
        """
        try:
            if not DINGTALK_AVAILABLE:
                logger.error(
                    "DingTalk Stream SDK not installed. Run: pip install queryclaw[dingtalk]"
                )
                return

            if not self.config.client_id or not self.config.client_secret:
                logger.error("DingTalk client_id and client_secret not configured")
                return

            self._running = True
            self._http = httpx.AsyncClient()

            logger.info(
                "Initializing DingTalk Stream Client with Client ID: {}...",
                self.config.client_id,
            )
            credential = Credential(self.config.client_id, self.config.client_secret)
            self._client = DingTalkStreamClient(credential)
            self._client.pre_start()

            handler = QueryClawDingTalkHandler(self)
            self._client.register_callback_handler(ChatbotMessage.TOPIC, handler)

            logger.info("DingTalk bot started with Stream Mode")
            await self._stream_loop()

        except asyncio.CancelledError:
            logger.info("DingTalk channel cancelled, shutting down")
            raise
        except Exception as e:
            logger.exception("Failed to start DingTalk channel: {}", e)

    async def _stream_loop(self) -> None:
        """WebSocket stream loop with non-blocking reconnection.

        Uses asyncio.to_thread() for the SDK's synchronous open_connection()
        call to avoid blocking the event loop. Implements exponential backoff
        on repeated failures with a reset on successful connection.
        """
        while self._running:
            try:
                loop = asyncio.get_running_loop()
                connection = await loop.run_in_executor(
                    None, self._client.open_connection
                )
                if not connection:
                    self._reconnect_count += 1
                    delay = min(10 * self._reconnect_count, self._MAX_RECONNECT_DELAY)
                    logger.error(
                        "DingTalk open_connection failed (attempt #{}), retry in {}s",
                        self._reconnect_count, delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                endpoint = connection.get("endpoint", "unknown")
                ticket = connection.get("ticket", "")
                logger.info("DingTalk stream connected to {}", endpoint)

                uri = f"{endpoint}?ticket={quote_plus(ticket)}"
                async with websockets.connect(uri) as ws:
                    self._client.websocket = ws
                    self._connected = True
                    self._reconnect_count = 0
                    self._last_connected_at = time.monotonic()

                    keepalive_task = asyncio.create_task(
                        self._client.keepalive(ws)
                    )
                    try:
                        async for raw_message in ws:
                            json_message = json.loads(raw_message)
                            asyncio.create_task(
                                self._client.background_task(json_message)
                            )
                    finally:
                        keepalive_task.cancel()
                        self._connected = False

            except asyncio.CancelledError:
                self._connected = False
                raise
            except Exception as e:
                self._connected = False
                self._reconnect_count += 1
                is_ws_close = (
                    DINGTALK_AVAILABLE
                    and isinstance(e, websockets.exceptions.ConnectionClosed)
                )
                if is_ws_close:
                    uptime = time.monotonic() - self._last_connected_at
                    delay = min(3 + self._reconnect_count, self._MAX_RECONNECT_DELAY)
                    logger.warning(
                        "DingTalk WebSocket closed after {:.0f}s: {} "
                        "(reconnect #{}, next in {}s)",
                        uptime, e, self._reconnect_count, delay,
                    )
                else:
                    delay = min(5 * self._reconnect_count, self._MAX_RECONNECT_DELAY)
                    logger.warning(
                        "DingTalk stream error: {} (reconnect #{}, next in {}s)",
                        e, self._reconnect_count, delay,
                    )
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        """Stop the DingTalk bot."""
        self._running = False
        self._connected = False
        if self._http:
            await self._http.aclose()
            self._http = None
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()

    async def _get_access_token(self) -> str | None:
        """Get or refresh Access Token."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        data = {
            "appKey": self.config.client_id,
            "appSecret": self.config.client_secret,
        }

        if not self._http:
            logger.warning("DingTalk HTTP client not initialized, cannot refresh token")
            return None

        try:
            resp = await self._http.post(url, json=data)
            resp.raise_for_status()
            res_data = resp.json()
            self._access_token = res_data.get("accessToken")
            self._token_expiry = time.time() + int(res_data.get("expireIn", 7200)) - 60
            return self._access_token
        except Exception as e:
            logger.error("Failed to get DingTalk access token: {}", e)
            return None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through DingTalk.

        Automatically selects the correct API based on conversation type:
        - Group chat ("2"): POST /v1.0/robot/groupMessages/send
        - 1:1 chat ("1"):   POST /v1.0/robot/oToMessages/batchSend
        """
        token = await self._get_access_token()
        if not token:
            return

        if not self._http:
            logger.warning("DingTalk HTTP client not initialized, cannot send")
            return

        metadata = msg.metadata or {}
        conversation_type = metadata.get("conversation_type", "1")
        headers = {"x-acs-dingtalk-access-token": token}

        if conversation_type == "2":
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            data = {
                "robotCode": self.config.client_id,
                "openConversationId": msg.chat_id,
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps(
                    {"text": msg.content, "title": "QueryClaw"},
                    ensure_ascii=False,
                ),
            }
        else:
            url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
            data = {
                "robotCode": self.config.client_id,
                "userIds": [msg.chat_id],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps(
                    {"text": msg.content, "title": "QueryClaw"},
                    ensure_ascii=False,
                ),
            }

        try:
            resp = await self._http.post(url, json=data, headers=headers)
            if resp.status_code != 200:
                logger.error("DingTalk send failed (type={}): {}", conversation_type, resp.text)
            else:
                logger.debug("DingTalk message sent to {} (type={})", msg.chat_id, conversation_type)
        except Exception as e:
            logger.error("Error sending DingTalk message: {}", e)

    async def _on_message(
        self,
        content: str,
        sender_id: str,
        sender_name: str,
        conversation_id: str = "",
        conversation_type: str = "1",
    ) -> None:
        """Handle incoming message (called by QueryClawDingTalkHandler)."""
        try:
            chat_id = conversation_id if conversation_type == "2" else sender_id
            logger.info(
                "DingTalk inbound: {} from {} (type={}, chat={})",
                content, sender_name, conversation_type, chat_id,
            )
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=str(content),
                metadata={
                    "sender_name": sender_name,
                    "platform": "dingtalk",
                    "conversation_type": conversation_type,
                    "conversation_id": conversation_id,
                },
            )
        except Exception as e:
            logger.error("Error publishing DingTalk message: {}", e)
