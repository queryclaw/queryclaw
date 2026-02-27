"""Subagent system — spawn focused child agents for specific tasks."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from queryclaw.db.base import SQLAdapter
from queryclaw.providers.base import LLMProvider
from queryclaw.tools.registry import ToolRegistry
from queryclaw.tools.schema import SchemaInspectTool
from queryclaw.tools.query import QueryExecuteTool
from queryclaw.tools.explain import ExplainPlanTool
from queryclaw.tools.base import Tool


class SubAgent:
    """A focused child agent that runs a specific task with a subset of tools.

    The subagent has its own conversation context and tool registry, but
    shares the same database connection and LLM provider as the parent.
    """

    def __init__(
        self,
        name: str,
        provider: LLMProvider,
        db: SQLAdapter,
        *,
        model: str | None = None,
        system_prompt: str = "",
        tools: list[Tool] | None = None,
        max_iterations: int = 10,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> None:
        self.name = name
        self.provider = provider
        self.db = db
        self.model = model or provider.get_default_model()
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.tool_registry = ToolRegistry()
        if tools:
            for tool in tools:
                self.tool_registry.register(tool)
        else:
            self.tool_registry.register(SchemaInspectTool(db))
            self.tool_registry.register(QueryExecuteTool(db))
            self.tool_registry.register(ExplainPlanTool(db))

    async def run(self, task: str) -> str:
        """Execute a task and return the final response."""
        messages: list[dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": task})

        logger.debug("SubAgent[{}] starting task: {}", self.name, task[:80])

        for iteration in range(1, self.max_iterations + 1):
            response = await self.provider.chat(
                messages=messages,
                tools=self.tool_registry.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if response.has_tool_calls:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                }
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ]
                if getattr(response, "reasoning_content", None) is not None:
                    assistant_msg["reasoning_content"] = response.reasoning_content
                else:
                    assistant_msg["reasoning_content"] = ""
                messages.append(assistant_msg)

                for tc in response.tool_calls:
                    logger.debug("SubAgent[{}] tool: {}({})", self.name, tc.name, tc.arguments)
                    result = await self.tool_registry.execute(tc.name, tc.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result,
                    })
            else:
                logger.debug("SubAgent[{}] completed in {} iterations", self.name, iteration)
                return response.content or ""

        return "(SubAgent reached max iterations without a final response)"


class SubAgentSpawner:
    """Factory for creating subagents from the parent agent context."""

    def __init__(self, provider: LLMProvider, db: SQLAdapter, model: str | None = None) -> None:
        self._provider = provider
        self._db = db
        self._model = model

    def spawn(
        self,
        name: str,
        system_prompt: str = "",
        *,
        tools: list[Tool] | None = None,
        max_iterations: int = 10,
    ) -> SubAgent:
        """Create a new subagent."""
        return SubAgent(
            name=name,
            provider=self._provider,
            db=self._db,
            model=self._model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
        )


class SpawnSubAgentTool(Tool):
    """Tool that allows the main agent to spawn a subagent for a focused task."""

    def __init__(self, spawner: SubAgentSpawner) -> None:
        self._spawner = spawner

    @property
    def name(self) -> str:
        return "spawn_subagent"

    @property
    def description(self) -> str:
        return (
            "Spawn a focused subagent to handle a specific subtask. "
            "The subagent has access to schema_inspect, query_execute, and explain_plan tools. "
            "Use this for complex tasks that benefit from delegated, focused analysis."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task description for the subagent to accomplish.",
                },
                "agent_name": {
                    "type": "string",
                    "description": "A short descriptive name for the subagent (e.g. 'schema_analyzer').",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt giving the subagent specific instructions.",
                },
            },
            "required": ["task", "agent_name"],
        }

    async def execute(self, task: str, agent_name: str, system_prompt: str = "", **kwargs: Any) -> str:
        subagent = self._spawner.spawn(
            name=agent_name,
            system_prompt=system_prompt or (
                "You are a focused database analysis subagent. "
                "Complete the given task using the available tools and return a clear, "
                "structured response."
            ),
        )
        try:
            result = await subagent.run(task)
            return f"[SubAgent '{agent_name}' result]\n\n{result}"
        except Exception as e:
            return f"[SubAgent '{agent_name}' error] {e}"
