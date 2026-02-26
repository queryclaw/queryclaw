"""Tests for CLI commands (batch C)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from queryclaw.cli.commands import app
from queryclaw.config.loader import load_config, save_config
from queryclaw.config.schema import Config, ProviderConfig, ProvidersConfig
from queryclaw.db.base import QueryResult, SQLAdapter, TableInfo, ColumnInfo, IndexInfo, ForeignKeyInfo
from queryclaw.providers.base import LLMProvider, LLMResponse

runner = CliRunner()


class FakeAdapter(SQLAdapter):
    """Minimal SQLAdapter used for CLI tests."""

    def __init__(self) -> None:
        self._connected = False

    @property
    def db_type(self) -> str:
        return "sqlite"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self, **kwargs: Any) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def execute(self, sql: str, params: tuple | None = None) -> QueryResult:
        return QueryResult(columns=["ok"], rows=[("ok",)])

    async def get_tables(self) -> list[TableInfo]:
        return [TableInfo(name="users", row_count=2)]

    async def get_columns(self, table: str) -> list[ColumnInfo]:
        return [ColumnInfo(name="id", data_type="INTEGER", is_primary_key=True)]

    async def get_indexes(self, table: str) -> list[IndexInfo]:
        return []

    async def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        return []

    async def explain(self, sql: str) -> QueryResult:
        return QueryResult(columns=["plan"], rows=[("SCAN users",)])


class FakeProvider(LLMProvider):
    """Minimal provider returning a constant response."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content="CLI test response.")

    def get_default_model(self) -> str:
        return "fake-model"


def test_onboard_creates_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    result = runner.invoke(app, ["onboard", "-c", str(config_path)])
    assert result.exit_code == 0
    assert config_path.exists()
    cfg = load_config(config_path)
    assert cfg.database.type == "sqlite"


def test_onboard_refreshes_existing_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    cfg = Config()
    cfg.database.database = "my.db"
    save_config(cfg, config_path)

    result = runner.invoke(app, ["onboard", "-c", str(config_path)])
    assert result.exit_code == 0
    refreshed = load_config(config_path)
    assert refreshed.database.database == "my.db"


def test_onboard_overwrite_resets_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    cfg = Config()
    cfg.database.type = "mysql"
    save_config(cfg, config_path)

    result = runner.invoke(app, ["onboard", "-c", str(config_path), "--overwrite"])
    assert result.exit_code == 0
    refreshed = load_config(config_path)
    assert refreshed.database.type == "sqlite"


def test_chat_single_turn(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    cfg = Config(
        providers=ProvidersConfig(anthropic=ProviderConfig(api_key="sk-test")),
    )
    save_config(cfg, config_path)

    async def _fake_create_and_connect(**kwargs: Any) -> SQLAdapter:
        adapter = FakeAdapter()
        await adapter.connect()
        return adapter

    monkeypatch.setattr(
        "queryclaw.cli.commands.AdapterRegistry.create_and_connect",
        _fake_create_and_connect,
    )
    monkeypatch.setattr("queryclaw.cli.commands._make_provider", lambda config: FakeProvider())

    result = runner.invoke(
        app,
        ["chat", "-c", str(config_path), "-m", "show tables", "--no-markdown"],
    )
    assert result.exit_code == 0
    assert "CLI test response." in result.stdout


def test_chat_missing_provider_key(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    save_config(Config(), config_path)
    result = runner.invoke(app, ["chat", "-c", str(config_path), "-m", "hello"])
    assert result.exit_code == 1
    assert "No LLM API key configured" in result.stdout


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "queryclaw v" in result.stdout
