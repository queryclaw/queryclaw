"""Tests for privacy redaction."""

import pytest

from queryclaw.safety.redact import is_sensitive_column, redact_private_info


class TestRedactPrivateInfo:
    def test_redact_private_ip(self):
        assert "192.168.1.1" not in redact_private_info("Host: 192.168.1.1")
        assert "[REDACTED]" in redact_private_info("Host: 192.168.1.1")

    def test_redact_localhost(self):
        assert "localhost" not in redact_private_info("Connected to localhost:3306")
        assert "[REDACTED]" in redact_private_info("Connected to localhost:3306")

    def test_redact_127(self):
        assert "127.0.0.1" not in redact_private_info("Bind 127.0.0.1")
        assert "[REDACTED]" in redact_private_info("Bind 127.0.0.1")

    def test_redact_connection_string(self):
        out = redact_private_info("mysql://root:secret@192.168.1.1/db")
        assert "secret" not in out
        assert "192.168.1.1" not in out
        assert "[REDACTED]" in out

    def test_redact_credential_pattern(self):
        out = redact_private_info("password=mysecret123")
        assert "mysecret123" not in out
        assert "***" in out

    def test_passthrough_safe_text(self):
        text = "Query returned 10 rows from table users"
        assert redact_private_info(text) == text


class TestIsSensitiveColumn:
    def test_sensitive(self):
        assert is_sensitive_column("password") is True
        assert is_sensitive_column("PASSWORD") is True
        assert is_sensitive_column("api_key") is True
        assert is_sensitive_column("secret") is True

    def test_not_sensitive(self):
        assert is_sensitive_column("name") is False
        assert is_sensitive_column("email") is False
