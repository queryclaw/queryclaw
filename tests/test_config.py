"""Tests for config schema and loader."""

import json
from pathlib import Path

import pytest

from queryclaw.config.schema import (
    AgentConfig,
    ChannelsConfig,
    Config,
    DatabaseConfig,
    DingTalkConfig,
    FeishuConfig,
    ProviderConfig,
    ProvidersConfig,
    SafetyConfig,
)
from queryclaw.config.loader import load_config, save_config


class TestDatabaseConfig:
    def test_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.type == "sqlite"
        assert cfg.host == "localhost"
        assert cfg.port == 3306
        assert cfg.database == ""
        assert cfg.user == ""
        assert cfg.password == ""

    def test_custom_values(self):
        cfg = DatabaseConfig(
            type="mysql", host="db.example.com", port=3307,
            database="mydb", user="admin", password="secret",
        )
        assert cfg.type == "mysql"
        assert cfg.host == "db.example.com"
        assert cfg.port == 3307

    def test_postgresql_type(self):
        cfg = DatabaseConfig(type="postgresql", host="pg.local", port=5432)
        assert cfg.type == "postgresql"
        assert cfg.port == 5432

    def test_invalid_type_rejected(self):
        with pytest.raises(Exception):
            DatabaseConfig(type="oracle")


class TestProviderConfig:
    def test_defaults(self):
        cfg = ProviderConfig()
        assert cfg.api_key == ""
        assert cfg.api_base == ""
        assert cfg.extra_headers == {}

    def test_custom_values(self):
        cfg = ProviderConfig(api_key="sk-test", api_base="https://api.example.com")
        assert cfg.api_key == "sk-test"


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.model == "anthropic/claude-sonnet-4-5"
        assert cfg.provider == "auto"
        assert cfg.max_iterations == 30
        assert cfg.temperature == 0.1
        assert cfg.max_tokens == 4096


class TestSafetyConfig:
    def test_defaults(self):
        cfg = SafetyConfig()
        assert cfg.read_only is True
        assert cfg.max_affected_rows == 1000
        assert cfg.require_confirmation is True
        assert cfg.audit_enabled is True

    def test_custom(self):
        cfg = SafetyConfig(read_only=False, max_affected_rows=500)
        assert cfg.read_only is False
        assert cfg.max_affected_rows == 500


class TestChannelsConfig:
    def test_defaults(self):
        cfg = ChannelsConfig()
        assert cfg.feishu.enabled is False
        assert cfg.feishu.app_id == ""
        assert cfg.dingtalk.enabled is False
        assert cfg.dingtalk.client_id == ""

    def test_feishu_enabled(self):
        cfg = ChannelsConfig(
            feishu=FeishuConfig(enabled=True, app_id="cli_xxx", app_secret="secret"),
        )
        assert cfg.feishu.enabled is True
        assert cfg.feishu.app_id == "cli_xxx"


class TestConfig:
    def test_defaults(self):
        cfg = Config()
        assert cfg.database.type == "sqlite"
        assert cfg.agent.max_iterations == 30
        assert isinstance(cfg.providers, ProvidersConfig)
        assert isinstance(cfg.safety, SafetyConfig)
        assert isinstance(cfg.channels, ChannelsConfig)
        assert cfg.safety.read_only is True

    def test_get_provider_no_keys(self):
        cfg = Config()
        assert cfg.get_provider() is None
        assert cfg.get_provider_name() is None
        assert cfg.get_api_key() is None

    def test_get_provider_with_key(self):
        cfg = Config(
            providers=ProvidersConfig(
                anthropic=ProviderConfig(api_key="sk-ant-test"),
            ),
        )
        p = cfg.get_provider("anthropic/claude-sonnet-4-5")
        assert p is not None
        assert p.api_key == "sk-ant-test"
        assert cfg.get_provider_name("anthropic/claude-sonnet-4-5") == "anthropic"

    def test_get_provider_forced(self):
        cfg = Config(
            agent=AgentConfig(provider="deepseek"),
            providers=ProvidersConfig(
                deepseek=ProviderConfig(api_key="sk-ds-test"),
                anthropic=ProviderConfig(api_key="sk-ant-test"),
            ),
        )
        assert cfg.get_provider_name() == "deepseek"
        assert cfg.get_provider().api_key == "sk-ds-test"

    def test_get_provider_fallback(self):
        cfg = Config(
            providers=ProvidersConfig(
                openai=ProviderConfig(api_key="sk-openai"),
            ),
        )
        # Model doesn't match openai keywords, but should fallback
        p = cfg.get_provider("some-unknown-model")
        assert p is not None
        assert p.api_key == "sk-openai"

    def test_serialization_roundtrip(self):
        cfg = Config(
            database=DatabaseConfig(type="mysql", host="db.local", database="app"),
            providers=ProvidersConfig(
                anthropic=ProviderConfig(api_key="sk-test"),
            ),
        )
        data = cfg.model_dump()
        restored = Config.model_validate(data)
        assert restored.database.type == "mysql"
        assert restored.database.host == "db.local"
        assert restored.providers.anthropic.api_key == "sk-test"
        assert "channels" in data
        assert restored.channels.feishu.enabled is False


class TestLoader:
    def test_load_default_when_no_file(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.json")
        assert isinstance(cfg, Config)
        assert cfg.database.type == "sqlite"

    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "config.json"
        original = Config(
            database=DatabaseConfig(type="mysql", host="myhost", database="testdb"),
            agent=AgentConfig(model="deepseek/deepseek-chat", max_iterations=10),
        )
        save_config(original, path)

        assert path.exists()
        loaded = load_config(path)
        assert loaded.database.type == "mysql"
        assert loaded.database.host == "myhost"
        assert loaded.agent.model == "deepseek/deepseek-chat"
        assert loaded.agent.max_iterations == 10

    def test_load_invalid_json(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        cfg = load_config(path)
        assert isinstance(cfg, Config)

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "deep" / "nested" / "config.json"
        save_config(Config(), path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "database" in data
