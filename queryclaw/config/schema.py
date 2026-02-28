"""Configuration schema using Pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model with convenient defaults."""

    model_config = ConfigDict(populate_by_name=True)


class DatabaseConfig(Base):
    """Database connection configuration."""

    type: Literal["mysql", "sqlite", "postgresql", "seekdb"] = "sqlite"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    user: str = ""
    password: str = ""


class SafetyConfig(Base):
    """Safety layer configuration."""

    read_only: bool = True
    max_affected_rows: int = 1000
    require_confirmation: bool = True
    allowed_tables: list[str] | None = None
    blocked_patterns: list[str] = Field(default_factory=lambda: [
        "DROP DATABASE",
        "DROP SCHEMA",
        "ALTER USER",
        "SET PASSWORD",
        "CREATE USER",
        "IDENTIFIED BY",
        "GRANT ",
    ])
    audit_enabled: bool = True


class ProviderConfig(Base):
    """Single LLM provider configuration."""

    api_key: str = ""
    api_base: str = ""
    extra_headers: dict[str, str] = Field(default_factory=dict)


class ProvidersConfig(Base):
    """All supported LLM providers."""

    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)


class AgentConfig(Base):
    """Agent behavior configuration."""

    model: str = "anthropic/claude-sonnet-4-5"
    provider: str = "auto"
    max_iterations: int = 30
    temperature: float = 0.1
    max_tokens: int = 4096


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DingTalkConfig(Base):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class ChannelsConfig(Base):
    """Multi-channel output configuration."""

    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)


class Config(BaseSettings):
    """Root configuration for QueryClaw."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)

    model_config = ConfigDict(env_prefix="QUERYCLAW_", env_nested_delimiter="__")

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config for the given model. Falls back to first available."""
        from queryclaw.providers.registry import PROVIDERS

        forced = self.agent.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return p if p and p.api_key else None

        model_lower = (model or self.agent.model).lower()

        for spec in PROVIDERS:
            if spec.is_gateway or spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key and any(kw in model_lower for kw in spec.keywords):
                return p

        # Fallback: first provider with an api_key
        for spec in PROVIDERS:
            if spec.is_gateway or spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p
        return None

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider."""
        from queryclaw.providers.registry import PROVIDERS

        forced = self.agent.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return forced if p and p.api_key else None

        model_lower = (model or self.agent.model).lower()

        for spec in PROVIDERS:
            if spec.is_gateway or spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key and any(kw in model_lower for kw in spec.keywords):
                return spec.name

        for spec in PROVIDERS:
            if spec.is_gateway or spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return spec.name
        return None

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model."""
        p = self.get_provider(model)
        return p.api_base if p and p.api_base else None
