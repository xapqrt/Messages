from __future__ import annotations

import pytest

from bbguy.scope.canonical import (
    HostRejected,
    PathRejected,
    UrlRejected,
    canonicalize_host,
    canonicalize_url,
    denied_ip_reason,
    normalize_path,
    path_has_prefix,
)


@pytest.mark.parametrize(
    ("raw", "expected", "is_ip"),
    [
        ("acme.example", "acme.example", False),
        ("ACME.Example.", "acme.example", False),
        ("a.b.c.example", "a.b.c.example", False),
        ("a-b.example", "a-b.example", False),
        ("xn--mnchen-3ya.example", "xn--mnchen-3ya.example", False),
        ("münchen.example", "xn--mnchen-3ya.example", False),
        ("8.8.8.8", "8.8.8.8", True),
        ("8.8.8.8.", "8.8.8.8", True),
        ("2001:0db8::1", "2001:db8::1", True),
        ("[2001:4860::8888]", "2001:4860::8888", True),
        ("0:0:0:0:0:0:0:1", "::1", True),
    ],
)
def test_canonical_host_accepts(raw: str, expected: str, is_ip: bool) -> None:
    host = canonicalize_host(raw)
    assert host.host == expected
    assert host.is_ip is is_ip


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " acme.example",
        "acme.example ",
        "acme\texample",
        "user@acme.example",
        "acme.example/path",
        "acme.example\\path",
        "acme%2eexample",
        "acme.example?x=1",
        "acme.example#frag",
        "acme.example..",
        ".acme.example",
        "acme..example",
        "acme.example:443",
        "[::1]:443",
        "-acme.example",
        "acme-.example",
        "a" * 64 + ".example",
        ".".join(["a" * 60] * 5),
        "2130706433",
        "0x7f000001",
        "017700000001",
        "127.1",
        "1.2.3.999",
        "a_b.example",
        "acme.example\x00",
        "münchen..example",
        "acme..",
    ],
)
def test_canonical_host_rejects(raw: str) -> None:
    with pytest.raises(HostRejected):
        canonicalize_host(raw)


def test_canonical_host_rejects_non_string() -> None:
    with pytest.raises(HostRejected):
        canonicalize_host(123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", "/"),
        ("/", "/"),
        ("/api/v2", "/api/v2"),
        ("//api//v2//", "/api/v2/"),
        ("/api/./v2", "/api/v2"),
        ("/api/x/../v2", "/api/v2"),
        ("/api/%2e%2e/admin", "/admin"),
        ("/api/v2/", "/api/v2/"),
        ("/api/%E2%98%83", "/api/☃"),
    ],
)
def test_normalize_path(path: str, expected: str) -> None:
    assert normalize_path(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/../etc/passwd",
        "/api/../../etc",
        "/api/%2e%2e/%2e%2e/etc",
        "/api/%2f/admin",
        "/api/%2F/admin",
        "/api/%252f/admin",
        "/api/%5c/admin",
        "/api/\\admin",
        "/api/%00",
        "/api/\x01",
    ],
)
def test_normalize_path_rejects(path: str) -> None:
    with pytest.raises(PathRejected):
        normalize_path(path)


@pytest.mark.parametrize(
    ("path", "prefix", "expected"),
    [
        ("/api/v2", "/api/v2", True),
        ("/api/v2/", "/api/v2", True),
        ("/api/v2/x", "/api/v2", True),
        ("/api/v20", "/api/v2", False),
        ("/api/v2x", "/api/v2", False),
        ("/api", "/api/v2", False),
        ("/anything", "/", True),
    ],
)
def test_path_has_prefix(path: str, prefix: str, expected: bool) -> None:
    assert path_has_prefix(path, prefix) is expected


@pytest.mark.parametrize(
    ("raw", "host", "port", "path"),
    [
        ("https://portal.example.net/api/v2/", "portal.example.net", 443, "/api/v2/"),
        ("http://portal.example.net", "portal.example.net", 80, "/"),
        ("https://portal.example.net:8443/x", "portal.example.net", 8443, "/x"),
        ("HTTPS://PORTAL.EXAMPLE.NET./api", "portal.example.net", 443, "/api"),
        ("https://[2001:4860::8888]/x", "2001:4860::8888", 443, "/x"),
        ("https://münchen.example/x", "xn--mnchen-3ya.example", 443, "/x"),
        ("https://portal.example.net/api/%2e%2e/admin", "portal.example.net", 443, "/admin"),
        ("https://portal.example.net/x#frag", "portal.example.net", 443, "/x"),
    ],
)
def test_canonical_url_accepts(raw: str, host: str, port: int, path: str) -> None:
    url = canonicalize_url(raw)
    assert url.host.host == host
    assert url.port == port
    assert url.path == path
    assert "#" not in url.url


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "ftp://portal.example.net/x",
        "file:///etc/passwd",
        "https:///x",
        "https://user@portal.example.net/x",
        "https://user:pass@portal.example.net/x",
        "https://portal.example.net:99999/x",
        "https://portal.example.net:0/x",
        "https://portal.example.net/api/%2f/admin",
        "https://portal.example.net/api/%252f/admin",
        " https://portal.example.net/x",
        "https://portal.example.net/a b",
    ],
)
def test_canonical_url_rejects(raw: str) -> None:
    with pytest.raises(UrlRejected):
        canonicalize_url(raw)


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("127.0.0.1", "loopback"),
        ("169.254.169.254", "link_local"),
        ("10.1.2.3", "private"),
        ("192.168.1.1", "private"),
        ("100.64.0.1", "cgnat"),
        ("224.0.0.1", "multicast"),
        ("0.0.0.0", "unspecified"),
        ("203.0.113.10", "private"),
        ("::1", "loopback"),
        ("fe80::1", "link_local"),
        ("fd7a:115c:a1e0::1", "tailscale_ula"),
        ("fd00::1", "private"),
    ],
)
def test_denied_ip_reason(address: str, reason: str) -> None:
    assert denied_ip_reason(canonicalize_host(address).ip) == reason


@pytest.mark.parametrize("address", ["8.8.8.8", "45.33.1.2", "2001:4860::8888"])
def test_public_ip_is_not_denied(address: str) -> None:
    assert denied_ip_reason(canonicalize_host(address).ip) is None
