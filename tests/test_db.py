"""Tests for database adapter layer."""

import pytest
import pytest_asyncio

from queryclaw.db.base import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    QueryResult,
    TableInfo,
)
from queryclaw.db.sqlite import SQLiteAdapter
from queryclaw.db.registry import AdapterRegistry


class TestQueryResult:
    def test_row_count(self):
        r = QueryResult(columns=["a", "b"], rows=[(1, 2), (3, 4)])
        assert r.row_count == 2

    def test_to_text_basic(self):
        r = QueryResult(columns=["id", "name"], rows=[(1, "alice"), (2, "bob")])
        text = r.to_text()
        assert "id" in text
        assert "name" in text
        assert "alice" in text
        assert "bob" in text

    def test_to_text_truncation(self):
        rows = [(i,) for i in range(200)]
        r = QueryResult(columns=["id"], rows=rows)
        text = r.to_text(max_rows=10)
        assert "190 more rows" in text

    def test_to_text_no_columns(self):
        r = QueryResult(affected_rows=5)
        text = r.to_text()
        assert "5 rows affected" in text

    def test_empty_result(self):
        r = QueryResult(columns=["x"], rows=[])
        assert r.row_count == 0


class TestDataClasses:
    def test_column_info(self):
        c = ColumnInfo(name="id", data_type="INTEGER", is_primary_key=True)
        assert c.name == "id"
        assert c.is_primary_key is True
        assert c.nullable is True

    def test_table_info(self):
        t = TableInfo(name="users", row_count=100)
        assert t.name == "users"
        assert t.schema == ""

    def test_index_info(self):
        i = IndexInfo(name="idx_email", columns=["email"], unique=True)
        assert i.unique is True

    def test_foreign_key_info(self):
        fk = ForeignKeyInfo(
            name="fk_order_user",
            columns=["user_id"],
            ref_table="users",
            ref_columns=["id"],
        )
        assert fk.ref_table == "users"


class TestAdapterRegistry:
    def test_available_types(self):
        types = AdapterRegistry.available_types()
        assert "sqlite" in types
        assert "mysql" in types

    def test_create_sqlite(self):
        adapter = AdapterRegistry.create("sqlite")
        assert adapter.db_type == "sqlite"

    def test_create_mysql(self):
        adapter = AdapterRegistry.create("mysql")
        assert adapter.db_type == "mysql"

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            AdapterRegistry.create("oracle")

    def test_get(self):
        assert AdapterRegistry.get("sqlite") is not None
        assert AdapterRegistry.get("oracle") is None


@pytest.mark.asyncio
class TestSQLiteAdapter:
    @pytest_asyncio.fixture
    async def adapter(self, tmp_path):
        a = SQLiteAdapter()
        db_path = str(tmp_path / "test.db")
        await a.connect(database=db_path)
        yield a
        await a.close()

    async def test_connect_and_close(self, tmp_path):
        a = SQLiteAdapter()
        assert a.is_connected is False
        await a.connect(database=str(tmp_path / "t.db"))
        assert a.is_connected is True
        await a.close()
        assert a.is_connected is False

    async def test_connect_no_database_raises(self):
        a = SQLiteAdapter()
        with pytest.raises(ValueError, match="requires a 'database' path"):
            await a.connect()

    async def test_execute_not_connected_raises(self):
        a = SQLiteAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            await a.execute("SELECT 1")

    async def test_execute_select(self, adapter):
        result = await adapter.execute("SELECT 1 AS val, 'hello' AS msg")
        assert result.columns == ["val", "msg"]
        assert result.rows == [(1, "hello")]
        assert result.execution_time_ms >= 0

    async def test_create_and_query_table(self, adapter):
        await adapter.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT)"
        )
        await adapter.execute("INSERT INTO users VALUES (1, 'Alice', 'a@test.com')")
        await adapter.execute("INSERT INTO users VALUES (2, 'Bob', 'b@test.com')")

        result = await adapter.execute("SELECT * FROM users ORDER BY id")
        assert result.row_count == 2
        assert result.rows[0] == (1, "Alice", "a@test.com")

    async def test_get_tables(self, adapter):
        await adapter.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        await adapter.execute("CREATE TABLE t2 (id INTEGER PRIMARY KEY)")
        await adapter.execute("INSERT INTO t1 VALUES (1)")

        tables = await adapter.get_tables()
        names = [t.name for t in tables]
        assert "t1" in names
        assert "t2" in names

        t1 = next(t for t in tables if t.name == "t1")
        assert t1.row_count == 1

    async def test_get_columns(self, adapter):
        await adapter.execute(
            "CREATE TABLE items ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "price REAL DEFAULT 0.0, "
            "qty INTEGER"
            ")"
        )
        cols = await adapter.get_columns("items")
        assert len(cols) == 4

        id_col = next(c for c in cols if c.name == "id")
        assert id_col.is_primary_key is True

        name_col = next(c for c in cols if c.name == "name")
        assert name_col.nullable is False

        price_col = next(c for c in cols if c.name == "price")
        assert "REAL" in price_col.data_type.upper()

    async def test_get_indexes(self, adapter):
        await adapter.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, email TEXT)")
        await adapter.execute("CREATE UNIQUE INDEX idx_email ON t(email)")

        indexes = await adapter.get_indexes("t")
        assert len(indexes) >= 1
        idx = next(i for i in indexes if i.name == "idx_email")
        assert idx.unique is True
        assert "email" in idx.columns

    async def test_get_foreign_keys(self, adapter):
        await adapter.execute("CREATE TABLE parents (id INTEGER PRIMARY KEY)")
        await adapter.execute(
            "CREATE TABLE children ("
            "id INTEGER PRIMARY KEY, "
            "parent_id INTEGER REFERENCES parents(id)"
            ")"
        )
        fks = await adapter.get_foreign_keys("children")
        assert len(fks) == 1
        assert fks[0].ref_table == "parents"
        assert "parent_id" in fks[0].columns
        assert "id" in fks[0].ref_columns

    async def test_explain(self, adapter):
        await adapter.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        result = await adapter.explain("SELECT * FROM t WHERE id = 1")
        assert result.row_count >= 1

    async def test_db_type(self, adapter):
        assert adapter.db_type == "sqlite"
