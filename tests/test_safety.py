"""Tests for safety layer: policy, validator, dry_run, audit."""

import pytest
import pytest_asyncio

from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.safety.policy import SafetyPolicy
from queryclaw.safety.validator import QueryValidator, ValidationResult
from queryclaw.safety.dry_run import DryRunEngine
from queryclaw.safety.audit import AuditLogger, AuditEntry, AUDIT_TABLE


# -- Policy -------------------------------------------------------------------


class TestSafetyPolicy:
    def test_defaults(self):
        p = SafetyPolicy()
        assert p.read_only is True
        assert p.max_affected_rows == 1000
        assert p.require_confirmation is True
        assert p.audit_enabled is True
        assert p.allows_write() is False

    def test_write_enabled(self):
        p = SafetyPolicy(read_only=False)
        assert p.allows_write() is True

    def test_table_allowed_none(self):
        p = SafetyPolicy()
        assert p.is_table_allowed("anything") is True

    def test_table_allowed_list(self):
        p = SafetyPolicy(allowed_tables=["users", "orders"])
        assert p.is_table_allowed("users") is True
        assert p.is_table_allowed("USERS") is True
        assert p.is_table_allowed("secrets") is False

    def test_requires_confirmation(self):
        p = SafetyPolicy(max_affected_rows=100)
        assert p.requires_confirmation_for(50) is False
        assert p.requires_confirmation_for(200) is True

    def test_no_confirmation(self):
        p = SafetyPolicy(require_confirmation=False)
        assert p.requires_confirmation_for(10000) is False

    def test_blocked_patterns_default(self):
        p = SafetyPolicy()
        assert "DROP DATABASE" in p.blocked_patterns
        assert "DROP SCHEMA" in p.blocked_patterns


# -- Validator ----------------------------------------------------------------


class TestQueryValidator:
    def test_select_allowed(self):
        v = QueryValidator()
        r = v.validate("SELECT * FROM users WHERE id = 1")
        assert r.allowed is True
        assert r.operation_type == "select"
        assert r.requires_confirmation is False

    def test_blocked_pattern(self):
        v = QueryValidator(blocked_patterns=["DROP DATABASE"])
        r = v.validate("DROP DATABASE production")
        assert r.allowed is False
        assert "Blocked pattern" in r.warnings[0]

    def test_insert_detected(self):
        v = QueryValidator()
        r = v.validate("INSERT INTO users (name) VALUES ('alice')")
        assert r.operation_type == "insert"
        assert r.allowed is True

    def test_update_without_where(self):
        v = QueryValidator()
        r = v.validate("UPDATE users SET status = 'active'")
        assert r.operation_type == "update"
        assert r.requires_confirmation is True
        assert any("without WHERE" in w for w in r.warnings)

    def test_update_with_where(self):
        v = QueryValidator()
        r = v.validate("UPDATE users SET status = 'active' WHERE id = 1")
        assert r.operation_type == "update"
        assert r.requires_confirmation is False

    def test_delete_without_where(self):
        v = QueryValidator()
        r = v.validate("DELETE FROM users")
        assert r.operation_type == "delete"
        assert r.requires_confirmation is True
        assert any("without WHERE" in w for w in r.warnings)

    def test_drop_table(self):
        v = QueryValidator()
        r = v.validate("DROP TABLE users")
        assert r.operation_type == "ddl_drop"
        assert r.requires_confirmation is True

    def test_truncate(self):
        v = QueryValidator()
        r = v.validate("TRUNCATE TABLE users")
        assert r.operation_type == "ddl_truncate"
        assert r.requires_confirmation is True

    def test_create_table(self):
        v = QueryValidator()
        r = v.validate("CREATE TABLE test (id INT)")
        assert r.operation_type == "ddl_create"
        assert r.allowed is True

    def test_alter_table(self):
        v = QueryValidator()
        r = v.validate("ALTER TABLE users ADD COLUMN email TEXT")
        assert r.operation_type == "ddl_alter"
        assert r.allowed is True

    def test_tables_extracted(self):
        v = QueryValidator()
        r = v.validate("SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id")
        assert "users" in r.tables_affected or "orders" in r.tables_affected


# -- Dry Run ------------------------------------------------------------------


@pytest_asyncio.fixture
async def dry_run_db(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "dryrun.db"))
    await adapter.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL)"
    )
    for i in range(50):
        await adapter.execute(
            "INSERT INTO items VALUES (?, ?, ?)", (i + 1, f"item_{i}", i * 1.5)
        )
    yield adapter
    await adapter.close()


@pytest.mark.asyncio
class TestDryRunEngine:
    async def test_delete_count(self, dry_run_db):
        engine = DryRunEngine(dry_run_db)
        result = await engine.analyze("DELETE FROM items WHERE price > 50")
        assert result.estimated_rows > 0

    async def test_update_count(self, dry_run_db):
        engine = DryRunEngine(dry_run_db)
        result = await engine.analyze("UPDATE items SET name = 'x' WHERE id < 10")
        assert result.estimated_rows == 9

    async def test_delete_all(self, dry_run_db):
        engine = DryRunEngine(dry_run_db)
        result = await engine.analyze("DELETE FROM items")
        assert result.estimated_rows == 50

    async def test_insert_values(self, dry_run_db):
        engine = DryRunEngine(dry_run_db)
        result = await engine.analyze(
            "INSERT INTO items VALUES (100, 'a', 1.0), (101, 'b', 2.0)"
        )
        assert result.estimated_rows >= 1

    async def test_explain_included(self, dry_run_db):
        engine = DryRunEngine(dry_run_db)
        result = await engine.analyze("DELETE FROM items WHERE id = 1")
        assert result.explain_plan != "" or len(result.warnings) > 0


# -- Audit --------------------------------------------------------------------


@pytest_asyncio.fixture
async def audit_db(tmp_path):
    adapter = SQLiteAdapter()
    await adapter.connect(database=str(tmp_path / "audit.db"))
    yield adapter
    await adapter.close()


@pytest.mark.asyncio
class TestAuditLogger:
    async def test_ensure_table(self, audit_db):
        logger = AuditLogger(audit_db)
        await logger.ensure_table()
        tables = await audit_db.get_tables()
        table_names = [t.name for t in tables]
        assert AUDIT_TABLE in table_names

    async def test_log_entry(self, audit_db):
        logger = AuditLogger(audit_db, session_id="test-session")
        await logger.log(AuditEntry(
            operation_type="update",
            sql_text="UPDATE users SET name = 'bob' WHERE id = 1",
            affected_rows=1,
            execution_time_ms=5.2,
        ))
        result = await audit_db.execute(f"SELECT * FROM {AUDIT_TABLE}")
        assert result.row_count == 1

    async def test_multiple_entries(self, audit_db):
        logger = AuditLogger(audit_db)
        for i in range(3):
            await logger.log(AuditEntry(
                operation_type="insert",
                sql_text=f"INSERT INTO t VALUES ({i})",
                affected_rows=1,
            ))
        result = await audit_db.execute(f"SELECT COUNT(*) FROM {AUDIT_TABLE}")
        assert result.rows[0][0] == 3

    async def test_session_id(self, audit_db):
        logger = AuditLogger(audit_db, session_id="s123")
        await logger.log(AuditEntry(
            operation_type="delete",
            sql_text="DELETE FROM t WHERE id = 1",
        ))
        result = await audit_db.execute(
            f"SELECT session_id FROM {AUDIT_TABLE}"
        )
        assert result.rows[0][0] == "s123"
