"""External access policy — URL validation and SSRF prevention."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from queryclaw.config.schema import ExternalAccessConfig


class ExternalAccessPolicy:
    """Validates URLs for external access tools to prevent SSRF and abuse."""

    # Private/local IP ranges (RFC 1918, loopback, link-local, etc.)
    _PRIVATE_PREFIXES = (
        "127.",   # loopback
        "10.",    # RFC 1918
        "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
        "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
        "172.28.", "172.29.", "172.30.", "172.31.",  # 172.16.0.0/12
        "192.168.",  # RFC 1918
        "169.254.",  # link-local
        "0.",      # 0.0.0.0/8
        "::1",     # IPv6 loopback
        "fe80:",   # IPv6 link-local
        "fc00:",   # IPv6 unique local
        "fd00:",   # IPv6 unique local (fd00::/8)
    )

    def __init__(self, config: ExternalAccessConfig) -> None:
        self._config = config

    def is_allowed(self, url: str) -> tuple[bool, str]:
        """Check if the URL is allowed for external access.

        Returns:
            (allowed, reason) — if not allowed, reason explains why.
        """
        if not url or not isinstance(url, str):
            return False, "URL is required and must be a string"

        url = url.strip()
        if not url:
            return False, "URL cannot be empty"

        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Invalid URL: {e}"

        if not parsed.scheme:
            return False, "URL must have a scheme (e.g. https://)"

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Only http and https are allowed, got {scheme}"

        if self._config.block_file and scheme == "file":
            return False, "file:// URLs are not allowed"

        if scheme in ("file", "ftp"):
            return False, f"{scheme}:// URLs are not allowed"

        if not parsed.netloc:
            return False, "URL must have a host"

        host = parsed.hostname or parsed.netloc.split(":")[0]

        if self._config.block_local:
            blocked, reason = self._check_ssrf(host)
            if blocked:
                return False, reason

        return True, ""

    def _check_ssrf(self, host: str) -> tuple[bool, str]:
        """Check if host resolves to a private/local address. Returns (blocked, reason)."""
        host_lower = host.lower()
        if host_lower in ("localhost", "localhost.", "local"):
            return True, "localhost is not allowed"

        # Check hostname patterns
        for prefix in self._PRIVATE_PREFIXES:
            if host_lower.startswith(prefix):
                return True, f"Private/local address '{host}' is not allowed"

        # Resolve hostname to IP and check
        try:
            ips = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as e:
            return True, f"Cannot resolve host: {e}"

        for family, _, _, _, sockaddr in ips:
            if family == socket.AF_INET:
                ip_str = sockaddr[0]
            elif family == socket.AF_INET6:
                ip_str = sockaddr[0].split("%")[0]
            else:
                continue

            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
                    return True, f"Host resolves to private/local IP: {ip_str}"
            except ValueError:
                continue

        return False, ""
