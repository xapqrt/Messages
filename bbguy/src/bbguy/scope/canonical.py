"""Host, IP and URL canonicalisation.

Every scope decision starts here. The input is hostile: it may come from a crawl,
a redirect chain, a certificate SAN, or a model. Rejection is a deny, never a
best-effort normalisation, and the same function is used by the executor and by
`bbguy scope explain`, so the two cannot disagree.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit

import idna

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ALL_DIGITS = re.compile(r"^[0-9]+$")
_HEX_INT = re.compile(r"^0[xX][0-9a-fA-F]+$")
_DOTTED_NUMERIC = re.compile(r"^[0-9.]+$")
_ENCODED_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
_FORBIDDEN_HOST_CHARS = frozenset("@/\\%?#")
_DEFAULT_PORTS = {"http": 80, "https": 443}
_MAX_HOST = 253
_MAX_LABEL = 63

_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_TAILSCALE_ULA = ipaddress.ip_network("fd7a:115c:a1e0::/48")


class HostRejected(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


class UrlRejected(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


class PathRejected(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass(frozen=True)
class CanonicalHost:
    host: str
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    is_ip: bool


@dataclass(frozen=True)
class CanonicalUrl:
    url: str
    scheme: str
    host: CanonicalHost
    port: int
    path: str
    query: str


def _check_raw_host(raw: str) -> str:
    if not isinstance(raw, str):
        raise HostRejected("not_a_string")
    if raw == "":
        raise HostRejected("empty_host")
    for char in raw:
        code = ord(char)
        if code <= 0x20 or code == 0x7F:
            raise HostRejected("whitespace_or_control")
        if char in _FORBIDDEN_HOST_CHARS:
            raise HostRejected("forbidden_character", char)
    return raw


def canonicalize_host(raw: str) -> CanonicalHost:
    """Return the canonical host or raise HostRejected.

    Ports are not part of a host. IPv6 literals may be bracketed; a bracketed
    literal with a port is rejected because the caller passed the wrong field.
    """
    host = _check_raw_host(raw)
    if host.startswith("["):
        if not host.endswith("]"):
            raise HostRejected("invalid_ipv6_literal", host)
        host = host[1:-1]
        if not host:
            raise HostRejected("empty_host")

    host = host.removesuffix(".")
    if not host:
        raise HostRejected("empty_host")

    if any(ord(char) > 127 for char in host):
        try:
            host = idna.encode(host, uts46=True, std3_rules=True).decode("ascii")
        except idna.IDNAError as exc:
            raise HostRejected("idna_invalid", str(exc)) from exc

    host = host.lower()

    if ":" in host:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise HostRejected("invalid_ip_literal", host) from exc
        return CanonicalHost(host=str(ip), ip=ip, is_ip=True)

    if _ALL_DIGITS.fullmatch(host) or _HEX_INT.fullmatch(host) or _DOTTED_NUMERIC.fullmatch(host):
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            # 2130706433, 0x7f000001, 017700000001, 127.1 and 1.2.3.999 are
            # alternate spellings of an address, not names. Accepting them as
            # DNS labels makes canonicalisation and the resolver disagree.
            raise HostRejected("ambiguous_numeric_host", host) from exc
        return CanonicalHost(host=str(ip), ip=ip, is_ip=True)

    try:
        ip = ipaddress.ip_address(host)
        return CanonicalHost(host=str(ip), ip=ip, is_ip=True)
    except ValueError:
        pass

    if len(host) > _MAX_HOST:
        raise HostRejected("host_too_long", str(len(host)))
    labels = host.split(".")
    if any(label == "" for label in labels):
        raise HostRejected("empty_label", host)
    for label in labels:
        if len(label) > _MAX_LABEL:
            raise HostRejected("label_too_long", label)
        if not _LABEL.fullmatch(label):
            raise HostRejected("invalid_label", label)
    return CanonicalHost(host=host, ip=None, is_ip=False)


def normalize_path(path: str) -> str:
    """Decode once, collapse separators, resolve dot segments.

    Encoded separators are rejected after decoding as well, so `%252f` cannot
    smuggle a slash through a second decode.
    """
    if path == "":
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    if _ENCODED_SEPARATOR.search(path):
        raise PathRejected("encoded_separator")
    try:
        decoded = unquote(path, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PathRejected("invalid_utf8", str(exc)) from exc
    if _ENCODED_SEPARATOR.search(decoded):
        raise PathRejected("encoded_separator")
    if "\\" in decoded:
        raise PathRejected("backslash_in_path")
    if "\x00" in decoded or any(ord(c) < 0x20 for c in decoded):
        raise PathRejected("control_in_path")

    decoded = re.sub(r"/{2,}", "/", decoded)
    segments: list[str] = []
    for segment in decoded.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not segments:
                raise PathRejected("path_traversal")
            segments.pop()
            continue
        segments.append(segment)

    normalized = "/" + "/".join(segments)
    if decoded.endswith("/") and normalized != "/":
        normalized += "/"
    return normalized


def path_has_prefix(path: str, prefix: str) -> bool:
    """Segment-boundary prefix match: /api/v2 matches /api/v2/x, not /api/v20."""
    normalized_prefix = normalize_path(prefix).rstrip("/") or "/"
    normalized_path = normalize_path(path)
    if normalized_prefix == "/":
        return True
    return normalized_path == normalized_prefix or normalized_path.startswith(
        normalized_prefix + "/"
    )


def canonicalize_url(raw: str) -> CanonicalUrl:
    if not isinstance(raw, str) or raw == "":
        raise UrlRejected("empty_url")
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in raw):
        raise UrlRejected("whitespace_or_control")
    try:
        split = urlsplit(raw)
    except ValueError as exc:
        raise UrlRejected("unparseable_url", str(exc)) from exc
    scheme = split.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise UrlRejected("unsupported_scheme", scheme or "(none)")
    if split.username is not None or split.password is not None:
        raise UrlRejected("userinfo_not_allowed")
    if split.hostname is None:
        raise UrlRejected("missing_host")
    try:
        port = split.port
    except ValueError as exc:
        raise UrlRejected("invalid_port", str(exc)) from exc
    if port is None:
        port = _DEFAULT_PORTS[scheme]
    if not 1 <= port <= 65535:
        raise UrlRejected("invalid_port", str(port))
    try:
        host = canonicalize_host(split.hostname)
        path = normalize_path(split.path)
    except (HostRejected, PathRejected) as exc:
        kind = "host" if isinstance(exc, HostRejected) else "path"
        raise UrlRejected(f"invalid_{kind}", str(exc)) from exc

    host_part = f"[{host.host}]" if host.is_ip and ":" in host.host else host.host
    netloc = host_part if port == _DEFAULT_PORTS[scheme] else f"{host_part}:{port}"
    canonical = urlunsplit((scheme, netloc, path, split.query, ""))
    return CanonicalUrl(
        url=canonical,
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        query=split.query,
    )


def denied_ip_reason(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> str | None:
    """Why an address must never be reached, or None when it is public."""
    if ip.version == 4 and ip in _CGNAT:
        return "cgnat"
    if ip.version == 6 and ip in _TAILSCALE_ULA:
        return "tailscale_ula"
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link_local"
    if ip.is_unspecified:
        return "unspecified"
    if ip.is_multicast:
        return "multicast"
    if ip.is_private:
        return "private"
    if ip.is_reserved:
        return "reserved"
    if not ip.is_global:
        return "not_global"
    return None
