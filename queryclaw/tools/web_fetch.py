"""Web fetch tool — fetch URL content as text or JSON."""

from __future__ import annotations

import re
from typing import Any

from queryclaw.config.schema import ExternalAccessConfig
from queryclaw.safety.external import ExternalAccessPolicy
from queryclaw.tools.base import Tool


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class WebFetchTool(Tool):
    """Fetch content from a URL. Returns text (HTML stripped or raw) or JSON."""

    def __init__(
        self,
        policy: ExternalAccessPolicy,
        config: ExternalAccessConfig,
    ) -> None:
        self._policy = policy
        self._config = config

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch content from a URL. Use for web pages, API docs, or public APIs. "
            "Returns text (HTML stripped by default) or JSON. Only public URLs are allowed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (http or https only).",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "json", "raw"],
                    "description": "Output format: 'text' (strip HTML, default), 'json' (parse as JSON), 'raw' (unchanged).",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50000,
                    "description": "Max characters to return (default 10000).",
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        format: str = "text",
        max_chars: int = 10000,
        **kwargs: Any,
    ) -> str:
        allowed, reason = self._policy.is_allowed(url)
        if not allowed:
            return f"Error: {reason}"

        max_chars = min(max_chars, self._config.max_response_chars)

        try:
            import httpx
        except ImportError:
            return "Error: httpx is required for web_fetch. Install with: pip install httpx"

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._config.timeout_seconds,
        ) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.TimeoutException:
                return f"Error: Request timed out after {self._config.timeout_seconds}s"
            except httpx.HTTPStatusError as e:
                return f"Error: HTTP {e.response.status_code} — {e.response.text[:500]}"
            except Exception as e:
                return f"Error: {e}"

            content = resp.text
            if len(content) > self._config.max_response_chars:
                content = content[: self._config.max_response_chars] + "\n\n[... truncated ...]"

            if format == "json":
                try:
                    import json
                    data = json.loads(content)
                    out = json.dumps(data, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    out = f"Error: Response is not valid JSON.\nRaw preview:\n{content[:500]}"
            elif format == "raw":
                out = content
            else:
                out = _strip_html(content)

            if len(out) > max_chars:
                out = out[:max_chars] + "\n\n[... truncated ...]"

            return out
