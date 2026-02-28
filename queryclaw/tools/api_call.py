"""API call tool — generic REST API requests."""

from __future__ import annotations

import json
from typing import Any

from queryclaw.config.schema import ExternalAccessConfig
from queryclaw.safety.external import ExternalAccessPolicy
from queryclaw.tools.base import Tool


class ApiCallTool(Tool):
    """Make REST API calls (GET, POST, PUT, PATCH, DELETE)."""

    def __init__(
        self,
        policy: ExternalAccessPolicy,
        config: ExternalAccessConfig,
    ) -> None:
        self._policy = policy
        self._config = config

    @property
    def name(self) -> str:
        return "api_call"

    @property
    def description(self) -> str:
        return (
            "Make REST API calls. Use for weather APIs, webhooks, or any HTTP API. "
            "Supports GET, POST, PUT, PATCH, DELETE. Only public URLs are allowed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "API endpoint URL (http or https only).",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method (default GET).",
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Optional request headers.",
                },
                "body": {
                    "description": "Request body — JSON object or string.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50000,
                    "description": "Max characters in response (default 10000).",
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: Any = None,
        max_chars: int = 10000,
        **kwargs: Any,
    ) -> str:
        allowed, reason = self._policy.is_allowed(url)
        if not allowed:
            return f"Error: {reason}"

        max_chars = min(max_chars, self._config.max_response_chars)
        headers = headers or {}

        try:
            import httpx
        except ImportError:
            return "Error: httpx is required for api_call. Install with: pip install httpx"

        # Prepare body
        if body is not None:
            if isinstance(body, dict):
                body = json.dumps(body)
            elif not isinstance(body, str):
                body = str(body)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._config.timeout_seconds,
        ) as client:
            try:
                resp = await client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    content=body,
                )
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

            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[... truncated ...]"

            return content
