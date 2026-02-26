"""Agent loop: the core ReACT processing engine."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from queryclaw.agent.context import ContextBuilder
from queryclaw.agent.memory import MemoryStore
from queryclaw.agent.skills import SkillsLoader
from queryclaw.db.base import SQLAdapter
from queryclaw.providers.base import LLMProvider
from queryclaw.tools.registry import ToolRegistry
from queryclaw.tools.schema import SchemaInspectTool
from queryclaw.tools.query import QueryExecuteTool
from queryclaw.tools.explain import ExplainPlanTool


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
    ) -> None:
        self.provider = provider
        self.db = db
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.tools = ToolRegistry()
        self.skills = SkillsLoader()
        self.context = ContextBuilder(db, self.skills)
        self.memory = MemoryStore()

        self._register_default_tools(max_query_rows)

    def _register_default_tools(self, max_query_rows: int) -> None:
        """Register the built-in database tools."""
        self.tools.register(SchemaInspectTool(self.db))
        self.tools.register(QueryExecuteTool(self.db, max_rows=max_query_rows))
        self.tools.register(ExplainPlanTool(self.db))

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
