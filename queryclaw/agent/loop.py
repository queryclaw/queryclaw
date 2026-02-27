"""Agent loop: the core ReACT processing engine."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from typing import Callable, Awaitable

from queryclaw.agent.context import ContextBuilder
from queryclaw.agent.memory import MemoryStore
from queryclaw.agent.skills import SkillsLoader
from queryclaw.agent.subagent import SubAgentSpawner, SpawnSubAgentTool
from queryclaw.db.base import SQLAdapter
from queryclaw.providers.base import LLMProvider
from queryclaw.safety.audit import AuditLogger
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.validator import QueryValidator
from queryclaw.tools.registry import ToolRegistry
from queryclaw.tools.schema import SchemaInspectTool
from queryclaw.tools.query import QueryExecuteTool
from queryclaw.tools.explain import ExplainPlanTool
from queryclaw.tools.modify import DataModifyTool
from queryclaw.tools.ddl import DDLExecuteTool
from queryclaw.tools.transaction import TransactionTool

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
        self.context = ContextBuilder(db, self.skills)
        self.memory = MemoryStore()
        self.subagent_spawner = SubAgentSpawner(provider, db, model=self.model)
        self._sessions: dict[str, MemoryStore] = {}
        self._running = False

        self._register_default_tools(max_query_rows, enable_subagent)

    def _register_default_tools(self, max_query_rows: int, enable_subagent: bool) -> None:
        """Register the built-in database tools."""
        self.tools.register(SchemaInspectTool(self.db))
        self.tools.register(QueryExecuteTool(self.db, max_rows=max_query_rows))
        self.tools.register(ExplainPlanTool(self.db))
        if enable_subagent:
            self.tools.register(SpawnSubAgentTool(self.subagent_spawner))

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

    async def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response.

        This is the main entry point for the interactive loop.
        """
        messages = await self.context.build_messages(
            history=self.memory.get_recent(),
            current_message=user_message,
        )

        final_content, tools_used, updated_messages = await self._run_agent_loop(messages)

        self.memory.add("user", user_message)
        if final_content:
            self.memory.add("assistant", final_content)

        if tools_used:
            logger.debug("Tools used: {}", ", ".join(tools_used))

        return final_content or "(no response)"

    async def _run_agent_loop(
        self,
        messages: list[dict[str, Any]],
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

            response = await self.provider.chat(
                messages=messages,
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

        final_content, tools_used, updated_messages = await self._run_agent_loop(messages)

        memory.add("user", msg.content)
        if final_content:
            memory.add("assistant", final_content)

        if tools_used:
            logger.debug("Tools used: {}", ", ".join(tools_used))

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content or "(no response)",
            metadata=getattr(msg, "metadata", None) or {},
        )
