"""Tests for agent core: memory, context, and loop."""

import pytest
import pytest_asyncio
from typing import Any
from unittest.mock import AsyncMock

from queryclaw.agent.memory import MemoryStore
from queryclaw.agent.context import ContextBuilder
from queryclaw.agent.loop import AgentLoop
from queryclaw.agent.skills import SkillsLoader
from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest


# -- Memory -------------------------------------------------------------------

class TestMemoryStore:
    def test_add_and_get(self):
        mem = MemoryStore()
        mem.add("user", "hello")
        mem.add("assistant", "hi")
        msgs = mem.get_recent()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi"}

    def test_get_recent_n(self):
        mem = MemoryStore()
        for i in range(10):
            mem.add("user", f"msg {i}")
        recent = mem.get_recent(3)
        assert len(recent) == 3
        assert recent[0]["content"] == "msg 7"

    def test_trim(self):
        mem = MemoryStore(max_messages=5)
        for i in range(10):
            mem.add("user", f"msg {i}")
        assert len(mem) == 5
        msgs = mem.get_recent()
        assert msgs[0]["content"] == "msg 5"

    def test_clear(self):
        mem = MemoryStore()
        mem.add("user", "test")
        mem.clear()
        assert len(mem) == 0

    def test_add_tool_call(self):
        mem = MemoryStore()
        mem.add_tool_call({"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]})
        assert len(mem) == 1
        assert mem.get_recent()[0]["role"] == "assistant"

    def test_add_tool_result(self):
        mem = MemoryStore()
        mem.add_tool_result("call_1", "echo", "result text")
        msgs = mem.get_recent()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "call_1"
        assert msgs[0]["name"] == "echo"

    def test_message_count(self):
        mem = MemoryStore()
        assert mem.message_count == 0
        mem.add("user", "a")
        assert mem.message_count == 1


# -- Context ------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_with_data(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "ctx_test.db"))
    await adapter.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price REAL)"
    )
    await adapter.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")
    yield adapter
    await adapter.close()


@pytest.mark.asyncio
class TestContextBuilder:
    async def test_build_system_prompt(self, db_with_data):
        ctx = ContextBuilder(db_with_data)
        prompt = await ctx.build_system_prompt()
        assert "QueryClaw" in prompt
        assert "products" in prompt
        assert "schema_inspect" in prompt
        assert "sqlite" in prompt.lower()

    async def test_build_system_prompt_empty_db(self, tmp_path):
        adapter = SQLiteAdapter()
        await adapter.connect(database=str(tmp_path / "empty.db"))
        ctx = ContextBuilder(adapter)
        prompt = await ctx.build_system_prompt()
        assert "empty" in prompt.lower()
        await adapter.close()

    async def test_schema_cache(self, db_with_data):
        ctx = ContextBuilder(db_with_data)
        prompt1 = await ctx.build_system_prompt()
        prompt2 = await ctx.build_system_prompt()
        assert prompt1 == prompt2

    async def test_invalidate_cache(self, db_with_data):
        ctx = ContextBuilder(db_with_data)
        await ctx.build_system_prompt()
        assert ctx._schema_cache is not None
        ctx.invalidate_schema_cache()
        assert ctx._schema_cache is None

    async def test_build_messages(self, db_with_data):
        ctx = ContextBuilder(db_with_data)
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        messages = await ctx.build_messages(history, "show me all products")
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "hi"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "show me all products"

    async def test_skills_in_prompt(self, db_with_data):
        ctx = ContextBuilder(db_with_data)
        prompt = await ctx.build_system_prompt()
        assert "data_analysis" in prompt
        assert "read_skill" in prompt
        assert "read_file" not in prompt


# -- Agent loop (with mock provider) -----------------------------------------

class MockProvider(LLMProvider):
    """A mock LLM provider that returns scripted responses."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__()
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    def get_default_model(self) -> str:
        return "mock-model"


@pytest_asyncio.fixture
async def agent_db(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "agent_test.db"))
    await adapter.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL)"
    )
    await adapter.execute("INSERT INTO items VALUES (1, 'Apple', 1.50)")
    await adapter.execute("INSERT INTO items VALUES (2, 'Banana', 0.75)")
    yield adapter
    await adapter.close()


@pytest.mark.asyncio
class TestAgentLoop:
    async def test_simple_response(self, agent_db):
        """LLM returns a direct text answer (no tool calls)."""
        provider = MockProvider([
            LLMResponse(content="The database has an items table with 2 rows."),
        ])
        agent = AgentLoop(provider=provider, db=agent_db)
        result = await agent.chat("What tables are there?")
        assert "items" in result
        assert agent.memory.message_count == 2

    async def test_tool_call_then_response(self, agent_db):
        """LLM calls a tool, then gives a final answer."""
        provider = MockProvider([
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="schema_inspect",
                        arguments={"action": "list_tables"},
                    ),
                ],
            ),
            LLMResponse(content="I found the items table with 2 products."),
        ])
        agent = AgentLoop(provider=provider, db=agent_db)
        result = await agent.chat("Show me the tables")
        assert "items" in result or "products" in result

    async def test_multiple_tool_calls(self, agent_db):
        """LLM calls multiple tools in sequence."""
        provider = MockProvider([
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="schema_inspect",
                        arguments={"action": "list_tables"},
                    ),
                ],
            ),
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_2",
                        name="query_execute",
                        arguments={"sql": "SELECT * FROM items"},
                    ),
                ],
            ),
            LLMResponse(content="There are 2 items: Apple ($1.50) and Banana ($0.75)."),
        ])
        agent = AgentLoop(provider=provider, db=agent_db)
        result = await agent.chat("What items are in the database?")
        assert "Apple" in result or "items" in result

    async def test_max_iterations(self, agent_db):
        """Agent stops after max_iterations even if LLM keeps calling tools."""
        endless_tool_call = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(id="c", name="schema_inspect", arguments={"action": "list_tables"}),
            ],
        )
        provider = MockProvider([endless_tool_call] * 10)
        agent = AgentLoop(provider=provider, db=agent_db, max_iterations=3)
        result = await agent.chat("infinite loop test")
        assert "maximum iterations" in result.lower()

    async def test_reset(self, agent_db):
        provider = MockProvider([LLMResponse(content="ok")])
        agent = AgentLoop(provider=provider, db=agent_db)
        await agent.chat("hello")
        assert agent.memory.message_count > 0
        agent.reset()
        assert agent.memory.message_count == 0
        assert agent.context._schema_cache is None

    async def test_conversation_history(self, agent_db):
        """Memory preserves multi-turn conversation."""
        provider = MockProvider([
            LLMResponse(content="Answer 1"),
            LLMResponse(content="Answer 2"),
        ])
        agent = AgentLoop(provider=provider, db=agent_db)
        await agent.chat("Question 1")
        await agent.chat("Question 2")
        msgs = agent.memory.get_recent()
        assert len(msgs) == 4
        assert msgs[0]["content"] == "Question 1"
        assert msgs[1]["content"] == "Answer 1"
        assert msgs[2]["content"] == "Question 2"
        assert msgs[3]["content"] == "Answer 2"

    async def test_tool_names_registered(self, agent_db):
        provider = MockProvider([LLMResponse(content="ok")])
        agent = AgentLoop(provider=provider, db=agent_db)
        assert agent.tools.has("read_skill")
        assert agent.tools.has("schema_inspect")
        assert agent.tools.has("query_execute")
        assert agent.tools.has("explain_plan")
        assert agent.tools.has("spawn_subagent")
        assert len(agent.tools) == 5

    async def test_tool_names_without_subagent(self, agent_db):
        provider = MockProvider([LLMResponse(content="ok")])
        agent = AgentLoop(provider=provider, db=agent_db, enable_subagent=False)
        assert agent.tools.has("read_skill")
        assert agent.tools.has("schema_inspect")
        assert agent.tools.has("query_execute")
        assert agent.tools.has("explain_plan")
        assert not agent.tools.has("spawn_subagent")
        assert len(agent.tools) == 4

    async def test_explain_tool_integration(self, agent_db):
        """LLM calls explain_plan and gets a result."""
        provider = MockProvider([
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="explain_plan",
                        arguments={"sql": "SELECT * FROM items WHERE id = 1"},
                    ),
                ],
            ),
            LLMResponse(content="The query uses a primary key lookup, which is efficient."),
        ])
        agent = AgentLoop(provider=provider, db=agent_db)
        result = await agent.chat("Explain this query")
        assert "efficient" in result.lower() or "primary" in result.lower()
