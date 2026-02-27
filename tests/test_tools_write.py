"""Tests for write tools: data_modify, ddl_execute, transaction."""

import pytest
import pytest_asyncio

from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.safety.audit import AuditLogger, AUDIT_TABLE
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.validator import QueryValidator
from queryclaw.tools.modify import DataModifyTool
from queryclaw.tools.ddl import DDLExecuteTool
from queryclaw.tools.transaction import TransactionTool


@pytest_asyncio.fixture
async def write_db(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "write_test.db"))
    await adapter.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"
    )
    await adapter.execute("INSERT INTO users VALUES (1, 'Alice', 'a@test.com')")
    await adapter.execute("INSERT INTO users VALUES (2, 'Bob', 'b@test.com')")
    await adapter.execute("INSERT INTO users VALUES (3, 'Charlie', 'c@test.com')")
    yield adapter
    await adapter.close()


def _write_policy(**overrides) -> SafetyPolicy:
    defaults = dict(read_only=False, require_confirmation=False, audit_enabled=True)
    defaults.update(overrides)
    return SafetyPolicy(**defaults)


# -- DataModifyTool -----------------------------------------------------------


@pytest.mark.asyncio
class TestDataModifyTool:
    async def test_insert(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="INSERT INTO users VALUES (4, 'Dave', 'd@test.com')")
        assert "Success" in result
        assert "1 row(s) affected" in result

        rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert rows.rows[0][0] == 4

    async def test_update(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="UPDATE users SET name = 'Alicia' WHERE id = 1")
        assert "Success" in result

        rows = await write_db.execute("SELECT name FROM users WHERE id = 1")
        assert rows.rows[0][0] == "Alicia"

    async def test_delete(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="DELETE FROM users WHERE id = 3")
        assert "Success" in result
        assert "1 row(s) affected" in result

        rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert rows.rows[0][0] == 2

    async def test_read_only_blocked(self, write_db):
        tool = DataModifyTool(write_db, SafetyPolicy(read_only=True))
        result = await tool.execute(sql="INSERT INTO users VALUES (5, 'Eve', 'e@test.com')")
        assert "Error" in result
        assert "read_only" in result

    async def test_rejects_select(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="SELECT * FROM users")
        assert "Error" in result
        assert "data_modify only accepts" in result

    async def test_rejects_ddl(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="CREATE TABLE foo (id INT)")
        assert "Error" in result

    async def test_blocked_pattern(self, write_db):
        tool = DataModifyTool(write_db, _write_policy(blocked_patterns=["DROP DATABASE"]))
        result = await tool.execute(sql="DROP DATABASE test")
        assert "Error" in result
        assert "data_modify only accepts" in result

    async def test_table_not_allowed(self, write_db):
        policy = _write_policy(allowed_tables=["orders"])
        tool = DataModifyTool(write_db, policy)
        result = await tool.execute(sql="INSERT INTO users VALUES (5, 'Eve', 'e@test.com')")
        assert "Error" in result
        assert "not in the allowed_tables" in result

    async def test_audit_logged(self, write_db):
        audit = AuditLogger(write_db)
        tool = DataModifyTool(write_db, _write_policy(), audit=audit)
        await tool.execute(sql="INSERT INTO users VALUES (10, 'Test', 't@test.com')")
        rows = await write_db.execute(f"SELECT * FROM {AUDIT_TABLE}")
        assert rows.row_count >= 1

    async def test_audit_skipped_when_disabled(self, write_db):
        """When audit_enabled=False, no audit entry is written."""
        audit = AuditLogger(write_db)
        await audit.ensure_table()
        before = await write_db.execute(f"SELECT COUNT(*) FROM {AUDIT_TABLE}")
        before_count = before.rows[0][0]
        policy = _write_policy(audit_enabled=False)
        tool = DataModifyTool(write_db, policy, audit=audit)
        await tool.execute(sql="INSERT INTO users VALUES (20, 'NoAudit', 'n@test.com')")
        after = await write_db.execute(f"SELECT COUNT(*) FROM {AUDIT_TABLE}")
        assert after.rows[0][0] == before_count

    async def test_delete_without_where_no_confirmation_when_disabled(self, write_db):
        """When require_confirmation=False, DELETE without WHERE executes without confirmation."""
        policy = _write_policy(require_confirmation=False)
        tool = DataModifyTool(write_db, policy)
        result = await tool.execute(sql="DELETE FROM users")
        assert "Success" in result
        assert "3 row(s) affected" in result
        rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert rows.rows[0][0] == 0

    async def test_confirmation_required_no_handler(self, write_db):
        policy = _write_policy(require_confirmation=True, max_affected_rows=0)
        tool = DataModifyTool(write_db, policy)
        result = await tool.execute(sql="DELETE FROM users WHERE id = 1")
        assert "Confirmation required" in result

    async def test_confirmation_accepted(self, write_db):
        async def always_confirm(sql, msg):
            return True
        policy = _write_policy(require_confirmation=True, max_affected_rows=0)
        tool = DataModifyTool(write_db, policy, confirmation_callback=always_confirm)
        result = await tool.execute(sql="DELETE FROM users WHERE id = 1")
        assert "Success" in result

    async def test_confirmation_rejected(self, write_db):
        async def always_reject(sql, msg):
            return False
        policy = _write_policy(require_confirmation=True, max_affected_rows=0)
        tool = DataModifyTool(write_db, policy, confirmation_callback=always_reject)
        result = await tool.execute(sql="DELETE FROM users WHERE id = 1")
        assert "cancelled" in result

    async def test_sql_error_returns_error(self, write_db):
        tool = DataModifyTool(write_db, _write_policy())
        result = await tool.execute(sql="INSERT INTO nonexistent VALUES (1)")
        assert "Error" in result


# -- DDLExecuteTool -----------------------------------------------------------


@pytest.mark.asyncio
class TestDDLExecuteTool:
    async def test_create_table(self, write_db):
        tool = DDLExecuteTool(write_db, _write_policy())
        result = await tool.execute(sql="CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
        assert "Success" in result
        assert "ddl_create" in result

        tables = await write_db.get_tables()
        names = [t.name for t in tables]
        assert "products" in names

    async def test_alter_table(self, write_db):
        tool = DDLExecuteTool(write_db, _write_policy())
        result = await tool.execute(sql="ALTER TABLE users ADD COLUMN age INTEGER")
        assert "Success" in result

        cols = await write_db.get_columns("users")
        col_names = [c.name for c in cols]
        assert "age" in col_names

    async def test_drop_no_confirmation_when_disabled(self, write_db):
        """When require_confirmation=False, DROP executes without confirmation."""
        await write_db.execute("CREATE TABLE temp_drop (id INT)")
        tool = DDLExecuteTool(write_db, _write_policy(require_confirmation=False))
        result = await tool.execute(sql="DROP TABLE temp_drop")
        assert "Success" in result
        tables = [t.name for t in await write_db.get_tables()]
        assert "temp_drop" not in tables

    async def test_drop_requires_confirmation(self, write_db):
        tool = DDLExecuteTool(write_db, _write_policy(require_confirmation=True))
        result = await tool.execute(sql="DROP TABLE users")
        assert "Error" in result
        assert "confirmation" in result.lower()

    async def test_drop_with_confirmation(self, write_db):
        async def confirm(sql, msg):
            return True
        policy = _write_policy(require_confirmation=True)
        tool = DDLExecuteTool(write_db, policy, confirmation_callback=confirm)
        result = await tool.execute(sql="DROP TABLE users")
        assert "Success" in result

    async def test_read_only_blocked(self, write_db):
        tool = DDLExecuteTool(write_db, SafetyPolicy(read_only=True))
        result = await tool.execute(sql="CREATE TABLE t (id INT)")
        assert "Error" in result
        assert "read_only" in result

    async def test_rejects_select(self, write_db):
        tool = DDLExecuteTool(write_db, _write_policy())
        result = await tool.execute(sql="SELECT * FROM users")
        assert "Error" in result
        assert "ddl_execute only accepts" in result

    async def test_rejects_dml(self, write_db):
        tool = DDLExecuteTool(write_db, _write_policy())
        result = await tool.execute(sql="INSERT INTO users VALUES (5, 'Eve', 'e@t.com')")
        assert "Error" in result

    async def test_schema_cache_invalidated(self, write_db):
        cache_invalidated = {"called": False}
        def on_change():
            cache_invalidated["called"] = True

        tool = DDLExecuteTool(write_db, _write_policy(), on_schema_change=on_change)
        await tool.execute(sql="CREATE TABLE items (id INTEGER PRIMARY KEY)")
        assert cache_invalidated["called"] is True

    async def test_audit_logged(self, write_db):
        audit = AuditLogger(write_db)
        tool = DDLExecuteTool(write_db, _write_policy(), audit=audit)
        await tool.execute(sql="CREATE TABLE logs (id INTEGER PRIMARY KEY)")
        rows = await write_db.execute(f"SELECT * FROM {AUDIT_TABLE}")
        assert rows.row_count >= 1

    async def test_audit_skipped_when_disabled(self, write_db):
        """When audit_enabled=False, no audit entry is written."""
        audit = AuditLogger(write_db)
        await audit.ensure_table()
        before = await write_db.execute(f"SELECT COUNT(*) FROM {AUDIT_TABLE}")
        before_count = before.rows[0][0]
        policy = _write_policy(audit_enabled=False)
        tool = DDLExecuteTool(write_db, policy, audit=audit)
        await tool.execute(sql="CREATE TABLE no_audit_ddl (id INTEGER PRIMARY KEY)")
        after = await write_db.execute(f"SELECT COUNT(*) FROM {AUDIT_TABLE}")
        assert after.rows[0][0] == before_count

    async def test_blocked_pattern(self, write_db):
        policy = _write_policy(blocked_patterns=["DROP DATABASE"])
        tool = DDLExecuteTool(write_db, policy)
        result = await tool.execute(sql="DROP DATABASE mydb")
        assert "Error" in result
        assert "blocked" in result.lower()


# -- TransactionTool ----------------------------------------------------------


@pytest.mark.asyncio
class TestTransactionTool:
    async def test_begin(self, write_db):
        tool = TransactionTool(write_db, _write_policy())
        result = await tool.execute(action="begin")
        assert "started" in result.lower()

    async def test_commit(self, write_db):
        tool = TransactionTool(write_db, _write_policy())
        await tool.execute(action="begin")
        await write_db.execute("INSERT INTO users VALUES (10, 'TxUser', 'tx@test.com')")
        result = await tool.execute(action="commit")
        assert "committed" in result.lower()

        rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert rows.rows[0][0] == 4

    async def test_rollback(self, write_db):
        tool = TransactionTool(write_db, _write_policy())
        await tool.execute(action="begin")
        await write_db.execute("INSERT INTO users VALUES (11, 'RbUser', 'rb@test.com')")

        mid_rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert mid_rows.rows[0][0] == 4

        result = await tool.execute(action="rollback")
        assert "rolled back" in result.lower()

        rows = await write_db.execute("SELECT COUNT(*) FROM users")
        assert rows.rows[0][0] == 3

    async def test_read_only_blocked(self, write_db):
        tool = TransactionTool(write_db, SafetyPolicy(read_only=True))
        result = await tool.execute(action="begin")
        assert "Error" in result
        assert "read_only" in result

    async def test_unknown_action(self, write_db):
        tool = TransactionTool(write_db, _write_policy())
        result = await tool.execute(action="savepoint")
        assert "Error" in result
        assert "Unknown action" in result


# -- Integration: AgentLoop with write tools ----------------------------------


@pytest.mark.asyncio
class TestAgentLoopWriteTools:
    async def test_write_tools_registered_when_not_readonly(self, write_db):
        from queryclaw.agent.loop import AgentLoop
        from queryclaw.providers.base import LLMProvider, LLMResponse

        class MockProvider(LLMProvider):
            async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
                return LLMResponse(content="ok")
            def get_default_model(self):
                return "mock"

        agent = AgentLoop(
            provider=MockProvider(),
            db=write_db,
            safety_policy=SafetyPolicy(read_only=False),
        )
        assert agent.tools.has("read_skill")
        assert agent.tools.has("data_modify")
        assert agent.tools.has("ddl_execute")
        assert agent.tools.has("transaction")
        assert agent.tools.has("schema_inspect")
        assert agent.tools.has("query_execute")
        assert agent.tools.has("explain_plan")
        assert agent.tools.has("spawn_subagent")
        assert len(agent.tools) == 8

    async def test_write_tools_not_registered_when_readonly(self, write_db):
        from queryclaw.agent.loop import AgentLoop
        from queryclaw.providers.base import LLMProvider, LLMResponse

        class MockProvider(LLMProvider):
            async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
                return LLMResponse(content="ok")
            def get_default_model(self):
                return "mock"

        agent = AgentLoop(
            provider=MockProvider(),
            db=write_db,
            safety_policy=SafetyPolicy(read_only=True),
        )
        assert agent.tools.has("read_skill")
        assert not agent.tools.has("data_modify")
        assert not agent.tools.has("ddl_execute")
        assert not agent.tools.has("transaction")
        assert len(agent.tools) == 5
