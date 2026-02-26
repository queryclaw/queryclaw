"""Tests for the tool system: base, registry, schema, query, explain."""

import pytest
import pytest_asyncio
from typing import Any

from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.tools.base import Tool
from queryclaw.tools.registry import ToolRegistry
from queryclaw.tools.schema import SchemaInspectTool
from queryclaw.tools.query import QueryExecuteTool
from queryclaw.tools.explain import ExplainPlanTool


# -- Helpers ------------------------------------------------------------------

class EchoTool(Tool):
    """A simple test tool that echoes its input."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the message."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to echo."},
            },
            "required": ["message"],
        }

    async def execute(self, message: str, **kwargs: Any) -> str:
        return f"echo: {message}"


class ErrorTool(Tool):
    """A tool that always raises."""

    @property
    def name(self) -> str:
        return "fail"

    @property
    def description(self) -> str:
        return "Always fails."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("intentional failure")


@pytest_asyncio.fixture
async def populated_db(tmp_path):
    """SQLite adapter with sample tables for tool testing."""
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "tools_test.db"))

    await adapter.execute(
        "CREATE TABLE users ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "email TEXT UNIQUE, "
        "age INTEGER DEFAULT 0"
        ")"
    )
    await adapter.execute(
        "CREATE TABLE orders ("
        "id INTEGER PRIMARY KEY, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "amount REAL NOT NULL, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    await adapter.execute("CREATE INDEX idx_orders_user ON orders(user_id)")
    await adapter.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@test.com', 30)")
    await adapter.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@test.com', 25)")
    await adapter.execute("INSERT INTO users VALUES (3, 'Charlie', 'charlie@test.com', 35)")
    await adapter.execute("INSERT INTO orders VALUES (1, 1, 99.99, '2025-01-01')")
    await adapter.execute("INSERT INTO orders VALUES (2, 1, 49.50, '2025-01-15')")
    await adapter.execute("INSERT INTO orders VALUES (3, 2, 200.00, '2025-02-01')")

    yield adapter
    await adapter.close()


# -- Tool base ----------------------------------------------------------------

class TestToolBase:
    def test_to_schema(self):
        tool = EchoTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert "message" in schema["function"]["parameters"]["properties"]

    def test_validate_params_valid(self):
        tool = EchoTool()
        errors = tool.validate_params({"message": "hello"})
        assert errors == []

    def test_validate_params_missing_required(self):
        tool = EchoTool()
        errors = tool.validate_params({})
        assert any("missing required" in e for e in errors)

    def test_validate_params_wrong_type(self):
        tool = EchoTool()
        errors = tool.validate_params({"message": 123})
        assert any("should be string" in e for e in errors)


# -- Tool registry ------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        assert reg.has("echo")
        assert reg.get("echo") is not None
        assert len(reg) == 1

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        reg.unregister("echo")
        assert not reg.has("echo")
        assert len(reg) == 0

    def test_get_definitions(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "echo"

    def test_tool_names(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        reg.register(ErrorTool())
        assert set(reg.tool_names) == {"echo", "fail"}

    def test_contains(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        assert "echo" in reg
        assert "missing" not in reg

    @pytest.mark.asyncio
    async def test_execute_success(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        result = await reg.execute("echo", {"message": "hi"})
        assert result == "echo: hi"

    @pytest.mark.asyncio
    async def test_execute_not_found(self):
        reg = ToolRegistry()
        result = await reg.execute("missing", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_execute_invalid_params(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        result = await reg.execute("echo", {})
        assert "Invalid parameters" in result

    @pytest.mark.asyncio
    async def test_execute_tool_error(self):
        reg = ToolRegistry()
        reg.register(ErrorTool())
        result = await reg.execute("fail", {})
        assert "Error executing" in result
        assert "intentional failure" in result


# -- SchemaInspectTool --------------------------------------------------------

@pytest.mark.asyncio
class TestSchemaInspectTool:
    async def test_list_tables(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="list_tables")
        assert "users" in result
        assert "orders" in result
        assert "2" in result  # 2 tables

    async def test_describe_table(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="describe_table", table="users")
        assert "id" in result
        assert "name" in result
        assert "email" in result
        assert "age" in result
        assert "PRI" in result

    async def test_describe_table_missing_param(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="describe_table")
        assert "Error" in result

    async def test_list_indexes(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="list_indexes", table="orders")
        assert "idx_orders_user" in result

    async def test_list_indexes_missing_param(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="list_indexes")
        assert "Error" in result

    async def test_list_foreign_keys(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="list_foreign_keys", table="orders")
        assert "users" in result
        assert "user_id" in result

    async def test_list_foreign_keys_no_fks(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="list_foreign_keys", table="users")
        assert "No foreign keys" in result

    async def test_unknown_action(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="unknown_action")
        assert "Error" in result

    async def test_nonexistent_table(self, populated_db):
        tool = SchemaInspectTool(populated_db)
        result = await tool.execute(action="describe_table", table="nonexistent")
        assert "No columns" in result or "not exist" in result


# -- QueryExecuteTool ---------------------------------------------------------

@pytest.mark.asyncio
class TestQueryExecuteTool:
    async def test_select(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="SELECT name, email FROM users ORDER BY id")
        assert "Alice" in result
        assert "Bob" in result
        assert "Charlie" in result
        assert "3 row(s)" in result

    async def test_aggregation(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="SELECT COUNT(*) AS cnt FROM users")
        assert "3" in result

    async def test_empty_result(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="SELECT * FROM users WHERE id = 999")
        assert "0 row(s)" in result

    async def test_rejects_insert(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="INSERT INTO users VALUES (99, 'x', 'x@x', 0)")
        assert "Error" in result
        assert "not permitted" in result

    async def test_rejects_delete(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="DELETE FROM users")
        assert "Error" in result

    async def test_rejects_drop(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="DROP TABLE users")
        assert "Error" in result

    async def test_rejects_update(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="UPDATE users SET name='x'")
        assert "Error" in result

    async def test_rejects_non_select(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="PRAGMA table_info(users)")
        assert "Error" in result

    async def test_allows_with_cte(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(
            sql="WITH top_users AS (SELECT * FROM users) SELECT * FROM top_users"
        )
        assert "Alice" in result

    async def test_auto_limit(self, populated_db):
        tool = QueryExecuteTool(populated_db, max_rows=2)
        result = await tool.execute(sql="SELECT * FROM users ORDER BY id")
        assert "2 row(s)" in result

    async def test_preserves_explicit_limit(self, populated_db):
        tool = QueryExecuteTool(populated_db, max_rows=100)
        result = await tool.execute(sql="SELECT * FROM users LIMIT 1")
        assert "1 row(s)" in result

    async def test_sql_error(self, populated_db):
        tool = QueryExecuteTool(populated_db)
        result = await tool.execute(sql="SELECT * FROM nonexistent_table")
        assert "Error" in result


# -- ExplainPlanTool ----------------------------------------------------------

@pytest.mark.asyncio
class TestExplainPlanTool:
    async def test_explain_select(self, populated_db):
        tool = ExplainPlanTool(populated_db)
        result = await tool.execute(sql="SELECT * FROM users WHERE id = 1")
        assert "Execution plan" in result

    async def test_explain_join(self, populated_db):
        tool = ExplainPlanTool(populated_db)
        result = await tool.execute(
            sql="SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert "Execution plan" in result

    async def test_explain_empty_sql(self, populated_db):
        tool = ExplainPlanTool(populated_db)
        result = await tool.execute(sql="")
        assert "Error" in result

    async def test_explain_strips_semicolon(self, populated_db):
        tool = ExplainPlanTool(populated_db)
        result = await tool.execute(sql="SELECT 1;")
        assert "Execution plan" in result

    async def test_explain_invalid_sql(self, populated_db):
        tool = ExplainPlanTool(populated_db)
        result = await tool.execute(sql="SELECT * FROM nonexistent")
        assert "Error" in result
