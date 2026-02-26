"""Tests for LLM provider layer."""

import pytest

from queryclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from queryclaw.providers.registry import (
    PROVIDERS,
    ProviderSpec,
    find_by_model,
    find_by_name,
    find_gateway,
)


class TestToolCallRequest:
    def test_basic(self):
        tc = ToolCallRequest(id="call_1", name="query_execute", arguments={"sql": "SELECT 1"})
        assert tc.id == "call_1"
        assert tc.name == "query_execute"
        assert tc.arguments["sql"] == "SELECT 1"


class TestLLMResponse:
    def test_no_tool_calls(self):
        r = LLMResponse(content="Hello")
        assert r.has_tool_calls is False
        assert r.content == "Hello"
        assert r.finish_reason == "stop"

    def test_with_tool_calls(self):
        tc = ToolCallRequest(id="1", name="test", arguments={})
        r = LLMResponse(content=None, tool_calls=[tc])
        assert r.has_tool_calls is True

    def test_usage(self):
        r = LLMResponse(
            content="hi",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        assert r.usage["total_tokens"] == 15

    def test_reasoning_content(self):
        r = LLMResponse(content="answer", reasoning_content="thinking...")
        assert r.reasoning_content == "thinking..."


class TestSanitizeEmptyContent:
    def test_empty_string_assistant_with_tool_calls(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]}]
        result = LLMProvider._sanitize_empty_content(msgs)
        assert result[0]["content"] is None

    def test_empty_string_user(self):
        msgs = [{"role": "user", "content": ""}]
        result = LLMProvider._sanitize_empty_content(msgs)
        assert result[0]["content"] == "(empty)"

    def test_non_empty_unchanged(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = LLMProvider._sanitize_empty_content(msgs)
        assert result[0]["content"] == "hello"


class TestProviderRegistry:
    def test_providers_not_empty(self):
        assert len(PROVIDERS) > 0

    def test_find_anthropic_by_model(self):
        spec = find_by_model("anthropic/claude-sonnet-4-5")
        assert spec is not None
        assert spec.name == "anthropic"

    def test_find_openai_by_model(self):
        spec = find_by_model("gpt-4o")
        assert spec is not None
        assert spec.name == "openai"

    def test_find_deepseek_by_model(self):
        spec = find_by_model("deepseek-chat")
        assert spec is not None
        assert spec.name == "deepseek"

    def test_find_gemini_by_model(self):
        spec = find_by_model("gemini-2.5-pro")
        assert spec is not None
        assert spec.name == "gemini"

    def test_find_dashscope_by_model(self):
        spec = find_by_model("qwen-max")
        assert spec is not None
        assert spec.name == "dashscope"

    def test_find_moonshot_by_model(self):
        spec = find_by_model("kimi-k2.5")
        assert spec is not None
        assert spec.name == "moonshot"

    def test_unknown_model_returns_none(self):
        assert find_by_model("totally-unknown-model") is None

    def test_find_by_name(self):
        assert find_by_name("anthropic") is not None
        assert find_by_name("nonexistent") is None

    def test_find_gateway_by_key_prefix(self):
        spec = find_gateway(api_key="sk-or-abc123")
        assert spec is not None
        assert spec.name == "openrouter"

    def test_find_gateway_by_base_keyword(self):
        spec = find_gateway(api_base="https://openrouter.ai/api/v1")
        assert spec is not None
        assert spec.name == "openrouter"

    def test_find_gateway_by_name(self):
        spec = find_gateway(provider_name="openrouter")
        assert spec is not None
        assert spec.name == "openrouter"

    def test_no_gateway_for_standard(self):
        assert find_gateway(provider_name="anthropic") is None

    def test_provider_spec_label(self):
        spec = find_by_name("anthropic")
        assert spec.label == "Anthropic"

    def test_all_providers_have_required_fields(self):
        for spec in PROVIDERS:
            assert spec.name
            assert isinstance(spec.keywords, tuple)
