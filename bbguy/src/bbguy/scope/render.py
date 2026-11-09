"""Render a signed revision into proxy/executor policy.

The rendered policy is advisory input to the proxy; the executor calls
ScopeMatcher directly. Both come from the same revision, and only targetable
types produce allow entries. A source-code URL must not become a host to scan.
"""

from __future__ import annotations

from typing import Any

from .canonical import canonicalize_host, canonicalize_url
from .models import Asset, AssetType, ScopeRevision


def _allow_entry(asset: Asset) -> dict[str, Any] | None:
    if asset.type is AssetType.DOMAIN:
        return {"id": asset.id, "kind": "domain", "host": canonicalize_host(asset.value).host}
    if asset.type is AssetType.WILDCARD:
        base = canonicalize_host(asset.value[2:]).host
        return {
            "id": asset.id,
            "kind": "wildcard",
            "base": base,
            "include_apex": asset.include_apex,
        }
    if asset.type is AssetType.URL:
        url = canonicalize_url(asset.value)
        return {
            "id": asset.id,
            "kind": "url",
            "scheme": url.scheme,
            "host": url.host.host,
            "port": url.port,
            "path": url.path,
        }
    if asset.type is AssetType.IP_ADDRESS:
        return {"id": asset.id, "kind": "ip", "address": canonicalize_host(asset.value).host}
    if asset.type is AssetType.CIDR:
        return {"id": asset.id, "kind": "cidr", "network": asset.value}
    return None


def _deny_entry(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "value": asset.value,
        "type": asset.type.value,
        "reason": "eligible_for_submission=false",
    }


def render_policy(revision: ScopeRevision) -> dict[str, Any]:
    revision.validate()
    allows = [entry for asset in revision.assets if asset.eligible_for_submission for entry in [_allow_entry(asset)] if entry]
    recorded_only = [
        {"id": asset.id, "type": asset.type.value, "value": asset.value}
        for asset in revision.assets
        if asset.type in (AssetType.SOURCE_CODE, AssetType.OTHER)
    ]
    constraints = {
        asset.id: {
            key: revision.constraint_for(asset, key)
            for key in ("automation", "accounts", "dns_active", "portscan", "rate")
        }
        for asset in revision.assets
        if asset.eligible_for_submission and asset.type.targetable
    }
    ineligible = {asset.value for asset in revision.assets if not asset.eligible_for_submission}
    explicit = [value for value in revision.deny if value not in ineligible]
    return {
        "revision": revision.revision_hash,
        "program": revision.handle,
        "platform": revision.platform,
        "automation": revision.automation_verdict.value,
        "target": {
            "ports": list(revision.ports),
            "allows": allows,
            "rate_limits": revision.rate_limits.to_dict(),
        },
        "deny": [
            _deny_entry(asset) for asset in revision.assets if not asset.eligible_for_submission
        ]
        + [{"id": None, "value": value, "type": "explicit", "reason": "explicit deny"} for value in explicit],
        "recorded_only": recorded_only,
        "constraints": constraints,
        "forbidden_classes": list(revision.forbidden),
    }


__all__ = ["render_policy"]
