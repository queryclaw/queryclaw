"""Agent loop: the core ReACT processing engine."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from typing import Callable, Awaitable

_COMPACT_KEEP_TAIL = 6
_COMPACT_TOOL_MAX = 500
_COMPACT_ASST_MAX = 300

from queryclaw.agent.context import ContextBuilder
from queryclaw.agent.memory import MemoryStore
from queryclaw.agent.skills import SkillsLoader
from queryclaw.agent.subagent import SubAgentSpawner, SpawnSubAgentTool
from queryclaw.db.base import SQLAdapter
from queryclaw.providers.base import LLMProvider
from queryclaw.safety.audit import AuditLogger
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.redact import redact_private_info
from queryclaw.safety.validator import QueryValidator
from queryclaw.tools.registry import ToolRegistry
from queryclaw.tools.read_skill import ReadSkillTool
from queryclaw.tools.schema import SchemaInspectTool
from queryclaw.tools.query import QueryExecuteTool
from queryclaw.tools.explain import ExplainPlanTool
from queryclaw.tools.modify import DataModifyTool
from queryclaw.tools.ddl import DDLExecuteTool
from queryclaw.tools.transaction import TransactionTool

from queryclaw.config.schema import ExternalAccessConfig

ConfirmationCallback = Callable[[str, str], Awaitable[bool]]


class AgentLoop:
    """The ReACT agent loop for database interaction.

    Flow:
    1. Receive user message
    2. Build context with schema + history
    3. Call LLM
    4. If LLM returns tool calls -> execute tools -> feed results back -> repeat
    5. If LLM returns final text -> return to user
    """

    def __init__(
        self,
        provider: LLMProvider,
        db: SQLAdapter,
        model: str | None = None,
        max_iterations: int = 30,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_query_rows: int = 100,
        safety_policy: SafetyPolicy | None = None,
        enable_subagent: bool = True,
        confirmation_callback: ConfirmationCallback | None = None,
        bus: Any = None,
        external_access_config: ExternalAccessConfig | None = None,
    ) -> None:
        self.provider = provider
        self.db = db
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.safety_policy = safety_policy or SafetyPolicy()
        self.confirmation_callback = confirmation_callback
        self.bus = bus

        self.tools = ToolRegistry()
        self.skills = SkillsLoader()
        ext_cfg = external_access_config
        self.context = ContextBuilder(
            db, self.skills,
            read_only=self.safety_policy.read_only,
            enable_subagent=enable_subagent,
            external_access_enabled=bool(ext_cfg and ext_cfg.enabled),
        )
        self.memory = MemoryStore()
        self.subagent_spawner = SubAgentSpawner(provider, db, model=self.model)
        self._sessions: dict[str, MemoryStore] = {}
        self._running = False
        self._current_msg: Any = None

        self._register_default_tools(max_query_rows, enable_subagent, ext_cfg)

    def _register_default_tools(
        self,
        max_query_rows: int,
        enable_subagent: bool,
        external_access_config: ExternalAccessConfig | None = None,
    ) -> None:
        """Register the built-in database tools."""
        self.tools.register(ReadSkillTool(self.skills))
        self.tools.register(SchemaInspectTool(self.db))
        self.tools.register(QueryExecuteTool(self.db, max_rows=max_query_rows))
        self.tools.register(ExplainPlanTool(self.db))
        if enable_subagent:
            self.tools.register(SpawnSubAgentTool(self.subagent_spawner))

        if external_access_config and external_access_config.enabled:
            from queryclaw.safety.external import ExternalAccessPolicy
            from queryclaw.tools.web_fetch import WebFetchTool
            from queryclaw.tools.api_call import ApiCallTool
            policy = ExternalAccessPolicy(external_access_config)
            self.tools.register(WebFetchTool(policy, external_access_config))
            self.tools.register(ApiCallTool(policy, external_access_config))

        if self.safety_policy.allows_write():
            validator = QueryValidator(blocked_patterns=self.safety_policy.blocked_patterns)
            audit = AuditLogger(self.db)
            self.tools.register(DataModifyTool(
                db=self.db,
                policy=self.safety_policy,
                validator=validator,
                audit=audit,
                confirmation_callback=self.confirmation_callback,
            ))
            self.tools.register(DDLExecuteTool(
                db=self.db,
                policy=self.safety_policy,
                validator=validator,
                audit=audit,
                confirmation_callback=self.confirmation_callback,
                on_schema_change=self.context.invalidate_schema_cache,
            ))
            self.tools.register(TransactionTool(
                db=self.db,
                policy=self.safety_policy,
            ))

    async def chat(self, user_message: str, debug: bool = False) -> str:
        """Process a user message and return the agent's response.

        This is the main entry point for the interactive loop.

        Args:
            user_message: The user's input message.
            debug: If True, print LLM prompts to the log (use with `queryclaw chat --debug`).
        """
        messages = await self.context.build_messages(
            history=self.memory.get_recent(),
            current_message=user_message,
        )

        final_content, tools_used, updated_messages = await self._run_agent_loop(messages, log_prompt=debug)

        self.memory.add("user", user_message)
        out = final_content or "(no response)"
        out = redact_private_info(out)
        if final_content:
            self.memory.add("assistant", out)

        if tools_used:
            logger.debug("Tools used: {}", ", ".join(tools_used))

        return out

    async def _run_agent_loop(
        self,
        messages: list[dict[str, Any]],
        log_prompt: bool = False,
    ) -> tuple[str | None, list[str], list[dict[str, Any]]]:
        """Run the ReACT iteration loop.

        Returns:
            (final_content, tools_used, messages)
        """
        iteration = 0
        final_content: str | None = None
        tools_used: list[str] = []

        while iteration < self.max_iterations:
            iteration += 1

            # Log the full prompt sent to the LLM on each call (chat mode only, no truncation)
            if log_prompt:
                def _format_msg(m: dict[str, Any]) -> str:
                    role = m.get("role", "?")
                    content = m.get("content")
                    if content is None and "tool_calls" in m:
                        return f"[{role}] tool_calls={m['tool_calls']}"
                    s = str(content) if content is not None else ""
                    return f"[{role}] {s}"

                logger.info(
                    "LLM prompt (iteration {}):\n{}",
                    iteration,
                    "\n---\n".join(_format_msg(m) for m in messages),
                )

            compact = self._compact_messages(messages)

            response = await self.provider.chat(
                messages=compact,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if response.has_tool_calls:
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ]
                # Moonshot (and some providers) require reasoning_content on assistant messages
                # that have tool_calls when "thinking" is enabled; omit or re-send to avoid API error.
                if getattr(response, "reasoning_content", None) is not None:
                    assistant_msg["reasoning_content"] = response.reasoning_content
                else:
                    assistant_msg["reasoning_content"] = ""
                messages.append(assistant_msg)

                for tc in response.tool_calls:
                    logger.debug("Tool call: {}({})", tc.name, tc.arguments)
                    result = await self.tools.execute(tc.name, tc.arguments)
                    tools_used.append(tc.name)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result,
                    })
            else:
                final_content = response.content
                break

        if final_content is None and iteration >= self.max_iterations:
            final_content = "(Reached maximum iterations without a final response.)"

        return final_content, tools_used, messages

    @staticmethod
    def _compact_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return a token-efficient copy of *messages*.

        The last ``_COMPACT_KEEP_TAIL`` messages are kept intact so the LLM
        has full context for the current iteration.  Older tool results and
        assistant text messages are truncated to save tokens.
        """
        # +1 for system prompt at index 0
        if len(messages) <= _COMPACT_KEEP_TAIL + 1:
            return messages

        cutoff = len(messages) - _COMPACT_KEEP_TAIL
        result: list[dict[str, Any]] = [messages[0]]

        for i in range(1, len(messages)):
            msg = messages[i]
            if i >= cutoff:
                result.append(msg)
                continue

            role = msg.get("role")
            content = msg.get("content") or ""

            if role == "tool" and len(content) > _COMPACT_TOOL_MAX:
                result.append({**msg, "content": content[:300] + "\n\n[... truncated ...]"})
            elif role == "assistant" and "tool_calls" not in msg and len(content) > _COMPACT_ASST_MAX:
                result.append({**msg, "content": content[:200] + "\n[... truncated ...]"})
            else:
                result.append(msg)

        return result

    def reset(self) -> None:
        """Clear conversation history and schema cache."""
        self.memory.clear()
        self.context.invalidate_schema_cache()

    async def run(self) -> None:
        """Run the agent loop, consuming inbound messages and publishing outbound.

        Requires bus to be set. Used by the serve command for channel mode.
        """
        if self.bus is None:
            raise RuntimeError("MessageBus is required for run()")
        from queryclaw.bus.events import InboundMessage, OutboundMessage

        self._running = True
        logger.info("Agent loop started (channel mode)")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            task = asyncio.create_task(self._dispatch_message(msg))
            try:
                await task
            except Exception as e:
                logger.exception("Error processing message: {}", e)
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Sorry, I encountered an error.",
                    )
                )

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _dispatch_message(self, msg: Any) -> None:
        """Process a single inbound message and publish the response."""
        from queryclaw.bus.events import OutboundMessage

        response = await self._process_message(msg)
        if response is not None:
            await self.bus.publish_outbound(response)

    async def _process_message(self, msg: Any) -> Any | None:
        """Process a single inbound message and return the outbound response."""
        from queryclaw.bus.events import OutboundMessage

        self._current_msg = msg
        try:
            return await self._process_message_impl(msg)
        finally:
            self._current_msg = None

    async def _process_message_impl(self, msg: Any) -> Any | None:
        """Implementation of message processing."""
        from queryclaw.bus.events import OutboundMessage

        session_key = msg.session_key
        memory = self._sessions.get(session_key)
        if memory is None:
            memory = MemoryStore()
            self._sessions[session_key] = memory

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        messages = await self.context.build_messages(
            history=memory.get_recent(),
            current_message=msg.content,
        )

        final_content, tools_used, updated_messages = await self._run_agent_loop(messages, log_prompt=False)

        memory.add("user", msg.content)
        if final_content:
            memory.add("assistant", final_content)

        if tools_used:
            logger.debug("Tools used: {}", ", ".join(tools_used))

        out = final_content or "(no response)"
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=redact_private_info(out),
            metadata=getattr(msg, "metadata", None) or {},
        )
