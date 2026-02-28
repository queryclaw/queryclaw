"""Privacy redaction: never expose database passwords, IPs, or credentials."""

from __future__ import annotations

import re

_REDACTED = "[REDACTED]"

# Private/local IP ranges and localhost
_IP_PATTERN = re.compile(
    r"\b("
    r"127\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"localhost"
    r")\b",
    re.IGNORECASE,
)

# Connection strings: mysql://user:password@host, postgresql://..., etc.
_CONN_PATTERN = re.compile(
    r"[a-z+]+://[^:]+:[^@\s]+@[^\s]+",
    re.IGNORECASE,
)

# password=xxx, password:xxx, pwd=xxx, api_key=xxx style
_CRED_PATTERN = re.compile(
    r"(password|pwd|passwd|secret|api_key|apikey|token)\s*[:=]\s*['\"]?[^\s'\"]+['\"]?",
    re.IGNORECASE,
)


def redact_private_info(text: str) -> str:
    """Redact IP addresses, connection strings, and credential-like patterns.

    Use this on any text that may be shown to the user or sent to the LLM.
    """
    if not text or not isinstance(text, str):
        return text
    out = _IP_PATTERN.sub(_REDACTED, text)
    out = _CONN_PATTERN.sub(_REDACTED, out)
    out = _CRED_PATTERN.sub(r"\1=***", out)
    return out


# Column names that should have their values redacted in query results
_SENSITIVE_COLUMNS = frozenset({
    "password", "pwd", "passwd", "secret", "api_key", "apikey",
    "token", "access_token", "refresh_token", "credential",
})


def is_sensitive_column(name: str) -> bool:
    """Return True if the column name suggests sensitive data."""
    return name.lower() in _SENSITIVE_COLUMNS
