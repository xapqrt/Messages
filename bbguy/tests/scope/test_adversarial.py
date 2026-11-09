"""Adversarial scope cases required by PRD Phase 0 (>= 200).

The generated cases are not decoration: they exercise the wildcard boundary at
scale, and the explicit cases cover the spellings that make resolvers and
canonicalisers disagree.
"""

from __future__ import annotations

import pytest

from bbguy.scope.matching import ScopeMatcher

from .support import acme_revision

IN_SCOPE_HOSTS = (
    [
        "acme.example",
        "a.acme.example",
        "deep.a.acme.example",
        "ACME.EXAMPLE",
        "acme.example.",
        "a-b.acme.example",
        "xn--mnchen-3ya.acme.example",
    ]
    + [f"host{i}.acme.example" for i in range(40)]
    + [f"a.b{i}.acme.example" for i in range(15)]
)

OUT_OF_SCOPE_HOSTS = (
    [
        "evil.com",
        "acme.example.evil.com",
        "evilacme.example",
        "acme.example.attacker.net",
        "notacme.example",
        "stg.acme.example",
        "x.stg.acme.example",
        "deep.x.stg.acme.example",
        "internal.acme.example",
        "x.internal.acme.example",
    ]
    + [f"host{i}.stg.acme.example" for i in range(25)]
    + [f"host{i}.evil.com" for i in range(20)]
)

INVALID_HOSTS = [
    "",
    " acme.example",
    "acme.example ",
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
    "a" * 64 + ".acme.example",
    ".".join(["a" * 60] * 5),
    "2130706433",
    "0x7f000001",
    "017700000001",
    "127.1",
    "1.2.3.999",
    "a_b.acme.example",
    "acme.example\x00",
    "acme.example\x01",
    "münchen..example",
    "acme..",
]

IP_ALLOWED = ["8.8.8.8", "45.33.0.1", "45.33.255.255", "2001:4860::1"]
IP_DENIED = [
    "8.8.4.4",
    "45.34.0.1",
    "2001:4861::1",
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "100.64.0.1",
    "224.0.0.1",
    "0.0.0.0",
    "203.0.113.10",
    "::1",
    "fe80::1",
    "fd7a:115c:a1e0::1",
    "fd00::1",
    "2001:db8::1",
]

URL_ALLOWED = [
    "https://portal.example.net/api/v2",
    "https://portal.example.net/api/v2/",
    "https://portal.example.net/api/v2/items",
    "https://portal.example.net/api/v2/items?x=1",
    "https://portal.example.net/api/v2//items",
    "https://portal.example.net/api/v2/./items",
    "HTTPS://PORTAL.EXAMPLE.NET/api/v2/items",
    "https://PORTAL.EXAMPLE.NET./api/v2/items",
    "https://acme.example/anything",
    "https://a.acme.example/anything",
    "http://acme.example:80/path",
    "https://acme.example:8443/path",
    "https://8.8.8.8/anything",
    "https://45.33.9.9/anything",
] + [f"https://host{i}.acme.example/path" for i in range(15)]

URL_DENIED = [
    "https://portal.example.net/api/v20",
    "https://portal.example.net/api/v2x",
    "https://portal.example.net/api",
    "https://portal.example.net/",
    "https://portal.example.net/other",
    "https://portal.example.net/API/v2/x",
    "https://portal.example.net/api/v2/../admin",
    "https://portal.example.net/api/v2/%2e%2e/admin",
    "https://portal.example.net/admin",
    "https://portal.example.net/admin/x",
    "https://portal.example.net:8443/api/v2/x",
    "http://portal.example.net/api/v2/items",
    "https://portal.example.net:22/api/v2/x",
    "https://portal.example.net.evil.com/api/v2",
    "https://evil.com/api/v2",
    "https://stg.acme.example/",
    "https://x.stg.acme.example/",
    "https://internal.acme.example/",
    "https://github.com/acme/website",
    "https://8.8.4.4/anything",
    "https://45.34.1.1/anything",
    "https://127.0.0.1/anything",
    "https://169.254.169.254/latest/meta-data/",
    "https://100.64.0.1/anything",
    "https://[::1]/anything",
    "https://[fd7a:115c:a1e0::1]/anything",
]

INVALID_URLS = [
    "ftp://portal.example.net/api/v2",
    "file:///etc/passwd",
    "https:///api/v2",
    "https://user@portal.example.net/api/v2",
    "https://user:pass@portal.example.net/api/v2",
    "https://portal.example.net:99999/api/v2",
    "https://portal.example.net:0/api/v2",
    "https://portal.example.net/api/%2f/admin",
    "https://portal.example.net/api/%252f/admin",
    "https://portal.example.net/api/%5c/admin",
    " https://portal.example.net/api/v2",
    "https://portal.example.net/a b",
]


@pytest.fixture(scope="module")
def scope() -> ScopeMatcher:
    return ScopeMatcher(acme_revision())


def test_suite_size_meets_phase_zero_gate() -> None:
    total = (
        len(IN_SCOPE_HOSTS)
        + len(OUT_OF_SCOPE_HOSTS)
        + len(INVALID_HOSTS)
        + len(IP_ALLOWED)
        + len(IP_DENIED)
        + len(URL_ALLOWED)
        + len(URL_DENIED)
        + len(INVALID_URLS)
    )
    assert total >= 200, f"only {total} adversarial cases"


@pytest.mark.parametrize("host", IN_SCOPE_HOSTS)
def test_in_scope_hosts(scope: ScopeMatcher, host: str) -> None:
    decision = scope.check_host(host)
    assert decision.allowed is True, decision.to_dict()
    assert decision.matched_asset in {"as_01", "as_02"}


@pytest.mark.parametrize("host", OUT_OF_SCOPE_HOSTS)
def test_out_of_scope_hosts(scope: ScopeMatcher, host: str) -> None:
    decision = scope.check_host(host)
    assert decision.allowed is False, decision.to_dict()
    assert decision.reason in {"no_matching_asset", "denied_by_scope"}


@pytest.mark.parametrize("host", INVALID_HOSTS)
def test_invalid_hosts(scope: ScopeMatcher, host: str) -> None:
    decision = scope.check_host(host)
    assert decision.allowed is False
    assert decision.reason == "invalid_host"


@pytest.mark.parametrize("address", IP_ALLOWED)
def test_in_scope_addresses(scope: ScopeMatcher, address: str) -> None:
    assert scope.check_host(address).allowed is True


@pytest.mark.parametrize("address", IP_DENIED)
def test_out_of_scope_or_reserved_addresses(scope: ScopeMatcher, address: str) -> None:
    decision = scope.check_host(address)
    assert decision.allowed is False
    assert decision.reason in {"private_or_reserved_ip", "no_matching_asset"}


@pytest.mark.parametrize("url", URL_ALLOWED)
def test_in_scope_urls(scope: ScopeMatcher, url: str) -> None:
    decision = scope.check_url(url)
    assert decision.allowed is True, decision.to_dict()


@pytest.mark.parametrize("url", URL_DENIED)
def test_out_of_scope_urls(scope: ScopeMatcher, url: str) -> None:
    decision = scope.check_url(url)
    assert decision.allowed is False, decision.to_dict()


@pytest.mark.parametrize("url", INVALID_URLS)
def test_invalid_urls(scope: ScopeMatcher, url: str) -> None:
    decision = scope.check_url(url)
    assert decision.allowed is False
    assert decision.reason == "invalid_url"
