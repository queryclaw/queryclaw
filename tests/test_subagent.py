"""Tests for subagent system."""

import pytest
import pytest_asyncio

from queryclaw.agent.subagent import SubAgent, SubAgentSpawner, SpawnSubAgentTool
from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class MockProvider(LLMProvider):
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
async def sub_db(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "sub.db"))
    await adapter.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    await adapter.execute("INSERT INTO t VALUES (1, 'hello')")
    yield adapter
    await adapter.close()


@pytest.mark.asyncio
class TestSubAgent:
    async def test_simple_response(self, sub_db):
        provider = MockProvider([
            LLMResponse(content="The table has 1 row."),
        ])
        agent = SubAgent("test", provider, sub_db)
        result = await agent.run("Count rows in t")
        assert "1 row" in result

    async def test_tool_call_then_response(self, sub_db):
        provider = MockProvider([
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(id="c1", name="schema_inspect", arguments={"action": "list_tables"}),
                ],
            ),
            LLMResponse(content="Found table t."),
        ])
        agent = SubAgent("test", provider, sub_db)
        result = await agent.run("List tables")
        assert "Found table t" in result

    async def test_max_iterations(self, sub_db):
        loop_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(id="c", name="schema_inspect", arguments={"action": "list_tables"}),
            ],
        )
        provider = MockProvider([loop_response] * 20)
        agent = SubAgent("test", provider, sub_db, max_iterations=3)
        result = await agent.run("loop test")
        assert "max iterations" in result.lower()


@pytest.mark.asyncio
class TestSubAgentSpawner:
    async def test_spawn(self, sub_db):
        provider = MockProvider([LLMResponse(content="done")])
        spawner = SubAgentSpawner(provider, sub_db)
        agent = spawner.spawn("worker")
        assert agent.name == "worker"
        result = await agent.run("test")
        assert result == "done"


@pytest.mark.asyncio
class TestSpawnSubAgentTool:
    async def test_tool_schema(self, sub_db):
        provider = MockProvider([LLMResponse(content="result")])
        spawner = SubAgentSpawner(provider, sub_db)
        tool = SpawnSubAgentTool(spawner)
        assert tool.name == "spawn_subagent"
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "task" in schema["function"]["parameters"]["properties"]

    async def test_execute(self, sub_db):
        provider = MockProvider([LLMResponse(content="analysis complete")])
        spawner = SubAgentSpawner(provider, sub_db)
        tool = SpawnSubAgentTool(spawner)
        result = await tool.execute(task="analyze table t", agent_name="analyzer")
        assert "SubAgent 'analyzer' result" in result
        assert "analysis complete" in result
