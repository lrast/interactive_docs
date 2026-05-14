"""Minimal checks before server-side HTTP fetches to reduce SSRF to local/non-global targets."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Known-local host labels, including dotted typos ``ipaddress`` rejects (e.g. ``127.0.01``).
_LOCALHOST_NAMES = frozenset(
    {
        "ip6-localhost",
        "ip6-loopback",
        "local",
        "localhost",
        "localdomain",
    }
)


def reject_local_or_private_http_url(url: str) -> None:
    """Raise ValueError if ``url`` is not a plain http(s) URL or targets non-global addresses.

    Hostnames are resolved with ``getaddrinfo``; every returned address must be globally
    routable (``is_global``). This does not pin TLS or prevent DNS rebinding between this
    check and the actual fetch; keep fetches short-lived and disable redirects where possible.
    """
    if not isinstance(url, str):
        raise ValueError("URL must be a string.")
    raw = url.strip()
    if not raw:
        raise ValueError("URL is empty.")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https.")

    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host.")

    _reject_if_host_blocked(host)


def _reject_if_host_blocked(host: str) -> None:
    lowered = host.lower().rstrip(".")
    if lowered in _LOCALHOST_NAMES:
        raise ValueError("URL must not target localhost.")

    if lowered.endswith(".local"):
        raise ValueError("URL must not target .local hosts.")

    literal = _parse_literal_ip(host)
    if literal is not None:
        if not literal.is_global:
            raise ValueError("URL must not target loopback, private, or non-global addresses.")
        return

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {exc}") from exc

    if not infos:
        raise ValueError("Host resolved to no addresses.")

    for _fam, _socktype, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        try:
            ipa = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if not ipa.is_global:
            raise ValueError("URL resolves to a non-global (e.g. private or loopback) address.")


def _parse_literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None
