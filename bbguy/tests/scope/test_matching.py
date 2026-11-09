from __future__ import annotations

import pytest

from bbguy.scope.matching import ScopeMatcher
from bbguy.scope.models import AssetType, AutomationVerdict, ScopeError

from .support import acme_revision, asset, revision


def matcher(**kwargs) -> ScopeMatcher:
    return ScopeMatcher(acme_revision(**kwargs))


def test_exact_domain_and_wildcard() -> None:
    scope = matcher()
    assert scope.check_host("acme.example").reason == "matched_domain"
    assert scope.check_host("a.acme.example").reason == "matched_wildcard"
    assert scope.check_host("a.b.acme.example").reason == "matched_wildcard"
    assert scope.check_host("ACME.EXAMPLE.").allowed is True


@pytest.mark.parametrize(
    "host",
    [
        "evil.com",
        "acme.example.evil.com",
        "evilacme.example",
        "notacme.example",
        "acme.example.attacker.net",
    ],
)
def test_wildcard_boundary(host: str) -> None:
    assert matcher().check_host(host).allowed is False


def test_wildcard_apex_is_not_implicit() -> None:
    scope = revision((asset("as_01", "*.example.org", AssetType.WILDCARD),))
    matcher_ = ScopeMatcher(scope)
    assert matcher_.check_host("example.org").allowed is False
    assert matcher_.check_host("a.example.org").allowed is True


def test_wildcard_include_apex() -> None:
    scope = revision(
        (asset("as_01", "*.example.org", AssetType.WILDCARD, include_apex=True),)
    )
    assert ScopeMatcher(scope).check_host("example.org").allowed is True


def test_deny_subtree_beats_allow_wildcard() -> None:
    scope = matcher()
    apex = scope.check_host("stg.acme.example")
    child = scope.check_host("x.stg.acme.example")
    deep = scope.check_host("a.b.stg.acme.example")
    assert apex.allowed is False and child.allowed is False and deep.allowed is False
    assert "as_03" in (apex.matched_deny or "") or "as_04" in (child.matched_deny or "")


def test_internal_deny() -> None:
    decision = matcher().check_url("https://internal.acme.example/")
    assert decision.allowed is False
    assert decision.reason == "denied_by_scope"


def test_explicit_deny_wildcard() -> None:
    scope = revision(
        (asset("as_01", "*.example.org", AssetType.WILDCARD),),
        deny=("*.blocked.example.org",),
    )
    matcher_ = ScopeMatcher(scope)
    assert matcher_.check_host("a.example.org").allowed is True
    assert matcher_.check_host("x.blocked.example.org").allowed is False
    assert matcher_.check_host("x.notblocked.example.org").allowed is True


def test_url_prefix_allows_only_prefix() -> None:
    scope = matcher()
    assert scope.check_url("https://portal.example.net/api/v2").allowed is True
    assert scope.check_url("https://portal.example.net/api/v2/").allowed is True
    assert scope.check_url("https://portal.example.net/api/v2/items?x=1").allowed is True
    assert scope.check_url("https://portal.example.net/api/v2//items").allowed is True
    assert scope.check_url("https://portal.example.net/api/v2/./items").allowed is True


@pytest.mark.parametrize(
    "url",
    [
        "https://portal.example.net/api/v20",
        "https://portal.example.net/api",
        "https://portal.example.net/",
        "https://portal.example.net/other",
        "https://portal.example.net/API/v2/x",
    ],
)
def test_url_prefix_rejects_lookalikes(url: str) -> None:
    decision = matcher().check_url(url)
    assert decision.allowed is False
    assert decision.connect_allowed is True
    assert decision.reason == "url_path_outside_prefix"


def test_url_deny_path_beats_host_allow() -> None:
    decision = matcher().check_url("https://portal.example.net/admin/x")
    assert decision.allowed is False
    assert decision.connect_allowed is False
    assert decision.reason == "denied_by_scope"


def test_url_traversal_normalises_into_denied_prefix() -> None:
    decision = matcher().check_url("https://portal.example.net/api/v2/../../admin")
    assert decision.allowed is False
    assert decision.reason == "denied_by_scope"


def test_host_only_url_asset_is_connect_only() -> None:
    decision = matcher().check_host("portal.example.net")
    assert decision.allowed is False
    assert decision.connect_allowed is True
    assert decision.reason == "url_requires_request_path"


def test_host_allow_is_path_agnostic() -> None:
    assert matcher().check_url("https://acme.example/admin").allowed is True
    assert matcher().check_url("https://a.acme.example/anything").allowed is True


def test_port_policy() -> None:
    scope = matcher()
    assert scope.check_host("acme.example", 443).allowed is True
    assert scope.check_host("acme.example", 8443).allowed is True
    assert scope.check_host("acme.example", 80).allowed is True
    denied = scope.check_host("acme.example", 22)
    assert denied.allowed is False
    assert denied.reason == "port_not_allowed"


def test_url_port_mismatch() -> None:
    decision = matcher().check_url("https://portal.example.net:8443/api/v2/x")
    assert decision.allowed is False
    assert decision.connect_allowed is True
    assert decision.reason == "url_port_mismatch"


def test_url_explicit_port() -> None:
    scope = revision(
        (asset("as_01", "https://portal.example.net:8443/api/v2/", AssetType.URL),),
        ports=(8443,),
    )
    matcher_ = ScopeMatcher(scope)
    assert matcher_.check_url("https://portal.example.net:8443/api/v2/x").allowed is True
    assert matcher_.check_url("https://portal.example.net/api/v2/x").allowed is False


def test_ip_and_cidr() -> None:
    scope = matcher()
    assert scope.check_host("8.8.8.8").reason == "matched_ip"
    assert scope.check_host("45.33.1.2").reason == "matched_cidr"
    assert scope.check_host("45.34.1.2").allowed is False
    assert scope.check_host("2001:4860::8888").reason == "matched_cidr"
    assert scope.check_host("8.8.4.4").allowed is False


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "169.254.169.254",
        "10.1.2.3",
        "192.168.1.1",
        "100.64.0.1",
        "224.0.0.1",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fd7a:115c:a1e0::1",
        "fd00::1",
    ],
)
def test_private_and_reserved_ip_denied(address: str) -> None:
    decision = matcher().check_host(address)
    assert decision.allowed is False
    assert decision.reason == "private_or_reserved_ip"


def test_lab_private_ip_override() -> None:
    scope = revision((asset("as_01", "10.0.0.0/8", AssetType.CIDR),))
    assert ScopeMatcher(scope).check_host("10.1.2.3").allowed is False
    lab = ScopeMatcher(scope, allow_private_ips=True)
    assert lab.check_host("10.1.2.3").allowed is True


def test_source_code_and_other_are_not_targetable() -> None:
    scope = matcher()
    assert scope.check_host("github.com").allowed is False
    assert scope.check_host("com.acme.app").allowed is False
    assert scope.check_host("acme.app").allowed is False


def test_longest_wildcard_wins() -> None:
    scope = revision(
        (
            asset("as_01", "*.example.org", AssetType.WILDCARD),
            asset("as_02", "*.api.example.org", AssetType.WILDCARD),
        )
    )
    decision = ScopeMatcher(scope).check_host("x.api.example.org")
    assert decision.matched_asset == "as_02"


def test_exact_domain_beats_wildcard() -> None:
    scope = revision(
        (
            asset("as_01", "*.example.org", AssetType.WILDCARD),
            asset("as_02", "app.example.org", AssetType.DOMAIN),
        )
    )
    assert ScopeMatcher(scope).check_host("app.example.org").matched_asset == "as_02"


def test_deny_wins_over_more_specific_allow() -> None:
    scope = revision(
        (
            asset("as_01", "*.example.org", AssetType.WILDCARD),
            asset("as_02", "*.api.example.org", AssetType.WILDCARD),
            asset("as_03", "*.api.example.org", AssetType.WILDCARD, eligible=False),
        )
    )
    assert ScopeMatcher(scope).check_host("x.api.example.org").allowed is False


def test_unknown_instruction_blocks_active_automation() -> None:
    scope = revision(
        (
            asset(
                "as_01",
                "app.example.org",
                AssetType.DOMAIN,
                instruction="Only test with the account acme_test.",
            ),
        )
    )
    decision = ScopeMatcher(scope).check_host("app.example.org")
    assert decision.allowed is True
    assert decision.constraints["automation"] == "unknown"


def test_explicit_automation_forbidden() -> None:
    scope = revision(
        (
            asset(
                "as_01",
                "app.example.org",
                AssetType.DOMAIN,
                constraints={"automation": "forbidden"},
            ),
        )
    )
    decision = ScopeMatcher(scope).check_host("app.example.org")
    assert decision.allowed is True
    assert decision.constraints["automation"] == "forbidden"


def test_accounts_default_and_override() -> None:
    scope = revision(
        (asset("as_01", "app.example.org", AssetType.DOMAIN),), accounts=False
    )
    assert ScopeMatcher(scope).check_host("app.example.org").constraints["accounts"] == "forbidden"
    scope = revision(
        (
            asset(
                "as_01",
                "app.example.org",
                AssetType.DOMAIN,
                constraints={"accounts": "allowed"},
            ),
        ),
        accounts=False,
    )
    assert ScopeMatcher(scope).check_host("app.example.org").constraints["accounts"] == "allowed"


def test_global_automation_unknown_is_reported() -> None:
    scope = acme_revision(automation=AutomationVerdict.UNKNOWN)
    decision = ScopeMatcher(scope).check_host("acme.example")
    assert decision.allowed is True
    assert decision.constraints["automation"] == "unknown"


def test_rate_constraint() -> None:
    decision = matcher().check_host("acme.example")
    assert decision.constraints["rate"]["default_rps"] == 2.0
    assert "dos" in decision.constraints["forbidden_classes"]


def test_hash_tamper_is_refused() -> None:
    scope = acme_revision()
    scope.assets[0].value = "evil.example"
    with pytest.raises(ScopeError):
        ScopeMatcher(scope)


def test_invalid_inputs() -> None:
    scope = matcher()
    assert scope.check_host("").reason == "invalid_host"
    assert scope.check_url("ftp://acme.example/x").reason == "invalid_url"
    assert scope.check_url("https://user@acme.example/x").reason == "invalid_url"


def test_decision_serialises() -> None:
    payload = matcher().check_host("acme.example").to_dict()
    assert payload["allowed"] is True
    assert payload["matched_asset"] == "as_01"
    assert payload["revision"].startswith("sha256:")
    assert payload["constraints"]["accounts"] == "allowed"


def test_deny_entry_variants_cover_ip_cidr_and_invalid_values() -> None:
    scope = revision(
        (
            asset("as_01", "*.example.org", AssetType.WILDCARD),
            asset("as_10", "8.8.4.4", AssetType.IP_ADDRESS, eligible=False),
            asset("as_11", "45.34.0.0/16", AssetType.CIDR, eligible=False),
            asset("as_12", "https://github.com/acme/x", AssetType.SOURCE_CODE, eligible=False),
            asset("as_13", "com.acme.app", AssetType.OTHER, eligible=False),
        ),
        deny=(
            "1.1.1.1",
            "45.35.0.0/16",
            "*..",
            "https://user@evil.example/",
            "bad host",
            "foo/bar",
        ),
    )
    matcher_ = ScopeMatcher(scope)
    assert matcher_.check_host("8.8.4.4").allowed is False
    assert matcher_.check_host("45.34.1.1").allowed is False
    assert matcher_.check_host("45.35.1.1").allowed is False
    assert matcher_.check_host("1.1.1.1").allowed is False
    assert matcher_.check_host("a.example.org").allowed is True
    assert matcher_.check_host("github.com").allowed is False
    assert matcher_.check_host("com.acme.app").allowed is False


def test_unknown_automation_turns_accounts_off() -> None:
    scope = revision(
        (asset("as_01", "app.example.org", AssetType.DOMAIN),),
        automation=AutomationVerdict.UNKNOWN,
    )
    decision = ScopeMatcher(scope).check_host("app.example.org")
    assert decision.constraints["automation"] == "unknown"
    assert decision.constraints["accounts"] == "forbidden"


def test_instruction_makes_accounts_forbidden_until_classified() -> None:
    scope = revision(
        (
            asset(
                "as_01",
                "app.example.org",
                AssetType.DOMAIN,
                instruction="Only test with the account acme_test.",
            ),
        )
    )
    decision = ScopeMatcher(scope).check_host("app.example.org")
    assert decision.constraints["automation"] == "unknown"
    assert decision.constraints["accounts"] == "forbidden"
