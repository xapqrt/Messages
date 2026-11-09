"""Test helpers shared by the scope suites."""

from __future__ import annotations

from bbguy.scope.models import (
    Asset,
    AssetType,
    AutomationVerdict,
    RateLimit,
    ScopeRevision,
)


def asset(
    asset_id: str,
    value: str,
    asset_type: AssetType,
    *,
    eligible: bool = True,
    instruction: str | None = None,
    constraints: dict | None = None,
    include_apex: bool = False,
) -> Asset:
    return Asset(
        id=asset_id,
        value=value,
        type=asset_type,
        eligible_for_submission=eligible,
        eligible_for_bounty=eligible,
        instruction=instruction,
        constraints=dict(constraints or {}),
        include_apex=include_apex,
    )


def revision(
    assets: tuple[Asset, ...],
    *,
    automation: AutomationVerdict = AutomationVerdict.ALLOWED,
    accounts: bool = True,
    deny: tuple[str, ...] = (),
    ports: tuple[int, ...] = (80, 443, 8443),
) -> ScopeRevision:
    return ScopeRevision(
        program="acme",
        platform="hackerone",
        handle="acme",
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://acme",
        assets=assets,
        automation_verdict=automation,
        accounts_allowed=accounts,
        deny=deny,
        ports=ports,
        rate_limits=RateLimit(default_rps=2.0, burst=10),
        forbidden=("dos", "bruteforce", "social_engineering", "physical"),
    ).finalize()


def acme_assets() -> tuple[Asset, ...]:
    return (
        asset("as_01", "acme.example", AssetType.DOMAIN),
        asset("as_02", "*.acme.example", AssetType.WILDCARD),
        asset("as_03", "stg.acme.example", AssetType.DOMAIN, eligible=False),
        asset("as_04", "*.stg.acme.example", AssetType.WILDCARD, eligible=False),
        asset("as_05", "https://portal.example.net/api/v2/", AssetType.URL),
        asset(
            "as_06",
            "https://portal.example.net/admin/",
            AssetType.URL,
            eligible=False,
        ),
        asset("as_07", "8.8.8.8", AssetType.IP_ADDRESS),
        asset("as_08", "45.33.0.0/16", AssetType.CIDR),
        asset("as_09", "2001:4860::/32", AssetType.CIDR),
        asset("as_10", "https://github.com/acme/website", AssetType.SOURCE_CODE),
        asset("as_11", "com.acme.app", AssetType.OTHER),
        asset("as_12", "internal.acme.example", AssetType.DOMAIN, eligible=False),
    )


def acme_revision(**kwargs) -> ScopeRevision:
    return revision(acme_assets(), **kwargs)
