"""Structured-scope importer.

The HackerOne field set is marked [verify] in the PRD. This parser accepts the
documented `data[].attributes` shape and a flat shape, preserves every row, and
fails closed when eligibility is absent. It never filters to eligible rows.
"""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Asset,
    AssetType,
    AutomationVerdict,
    RateLimit,
    ScopeError,
    ScopeRevision,
    digest_text,
)
from .policy import classify_policy, classify_third_party_ai

H1_TYPE_MAP: dict[str, AssetType] = {
    "domain": AssetType.DOMAIN,
    "wildcard": AssetType.WILDCARD,
    "url": AssetType.URL,
    "website": AssetType.URL,
    "ip_address": AssetType.IP_ADDRESS,
    "ip": AssetType.IP_ADDRESS,
    "cidr": AssetType.CIDR,
    "source_code": AssetType.SOURCE_CODE,
    "other": AssetType.OTHER,
    "android": AssetType.OTHER,
    "ios": AssetType.OTHER,
    "apple_store": AssetType.OTHER,
    "google_play": AssetType.OTHER,
    "executable": AssetType.OTHER,
    "hardware": AssetType.OTHER,
    "smart_contract": AssetType.OTHER,
}

DEFAULT_FORBIDDEN = ("dos", "bruteforce", "social_engineering", "physical")
DEFAULT_PORTS = (80, 443, 8443)


@dataclass(frozen=True)
class ImportSummary:
    handle: str
    total_assets: int
    eligible: int
    ineligible: int
    allows: int
    denies: int
    automation: str
    revision: str


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        raise ScopeError("structured scopes payload must be an object or list")
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        nested = data.get("assets") or data.get("scopes")
        if isinstance(nested, list):
            return [row for row in nested if isinstance(row, dict)]
    nested = payload.get("assets") or payload.get("scopes")
    if isinstance(nested, list):
        return [row for row in nested if isinstance(row, dict)]
    raise ScopeError("no data/attributes rows found in structured scopes payload")


def _attrs(row: dict[str, Any]) -> dict[str, Any]:
    attributes = row.get("attributes")
    return attributes if isinstance(attributes, dict) else row


def _identifier(attrs: dict[str, Any]) -> str:
    for key in ("asset_identifier", "identifier", "asset", "value"):
        value = attrs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _looks_like_cidr(value: str) -> bool:
    try:
        ipaddress.ip_network(value, strict=False)
        return "/" in value
    except ValueError:
        return False


def _normalize(value: str, declared: AssetType) -> tuple[str, AssetType]:
    if declared in (AssetType.SOURCE_CODE, AssetType.OTHER):
        return value, declared
    if value.startswith("*.") and declared is AssetType.DOMAIN:
        return value, AssetType.WILDCARD
    if declared is AssetType.DOMAIN:
        if value.lower().startswith(("http://", "https://")):
            return value, AssetType.URL
        if _looks_like_cidr(value):
            return value, AssetType.CIDR
        if _looks_like_ip(value):
            return value, AssetType.IP_ADDRESS
    if declared is AssetType.URL and not value.lower().startswith(("http://", "https://")):
        raise ScopeError(f"URL asset without scheme: {value!r}")
    if declared is AssetType.WILDCARD and not value.startswith("*."):
        raise ScopeError(f"wildcard asset without '*.' prefix: {value!r}")
    return value, declared


def _asset_from_row(
    row: dict[str, Any], index: int, eligible_default: bool = False
) -> Asset:
    attrs = _attrs(row)
    value = _identifier(attrs)
    if not value:
        raise ScopeError(f"scope row {index} has no asset identifier")
    declared_raw = attrs.get("asset_type", attrs.get("type", "other"))
    declared = H1_TYPE_MAP.get(str(declared_raw).lower())
    if declared is None:
        declared = AssetType.OTHER
    value, declared = _normalize(value, declared)

    eligible_raw = attrs.get("eligible_for_submission", eligible_default)
    if not isinstance(eligible_raw, bool):
        raise ScopeError(f"scope row {index} eligibility is not a boolean")
    bounty_raw = attrs.get("eligible_for_bounty", False)
    if not isinstance(bounty_raw, bool):
        raise ScopeError(f"scope row {index} bounty eligibility is not a boolean")

    instruction = attrs.get("instruction")
    if instruction is not None and not isinstance(instruction, str):
        instruction = str(instruction)
    if instruction is not None and not instruction.strip():
        instruction = None

    row_id = row.get("id", attrs.get("id"))
    asset_id = f"as_{int(row_id):02d}" if isinstance(row_id, int) else f"as_{index:02d}"
    if isinstance(row_id, str) and row_id.strip():
        asset_id = row_id.strip()

    constraints: dict[str, Any] = {}
    if instruction:
        constraints["automation"] = "unknown"

    return Asset(
        id=asset_id,
        value=value,
        type=declared,
        eligible_for_submission=eligible_raw,
        eligible_for_bounty=bounty_raw,
        instruction=instruction,
        max_severity=attrs.get("max_severity"),
        constraints=constraints,
    )


def load_blocklist(path: str | Path | None) -> set[str]:
    if path is None:
        return set()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ScopeError("blocklist must be a mapping with a 'handles' list")
    handles = raw.get("handles") or []
    if not isinstance(handles, list):
        raise ScopeError("blocklist 'handles' must be a list")
    return {str(handle).strip().lower() for handle in handles if str(handle).strip()}


def _unique_ids(assets: Iterable[Asset]) -> tuple[Asset, ...]:
    seen: set[str] = set()
    output: list[Asset] = []
    for asset in assets:
        if asset.id in seen:
            suffix = 2
            while f"{asset.id}_{suffix}" in seen:
                suffix += 1
            asset = Asset(**{**asset.__dict__, "id": f"{asset.id}_{suffix}"})
        seen.add(asset.id)
        output.append(asset)
    return tuple(output)


def build_revision(
    payload: Any,
    handle: str,
    *,
    policy_text: str | None = None,
    policy_text_ref: str | None = None,
    fetched_at: str | None = None,
    source: str | None = None,
    platform: str = "hackerone",
    accounts_allowed: bool | None = None,
    blocklist: set[str] | None = None,
    rate_limits: RateLimit | None = None,
    ports: tuple[int, ...] = DEFAULT_PORTS,
    third_party_ai: str | None = None,
) -> ScopeRevision:
    if not handle.strip():
        raise ScopeError("program handle is empty")
    rows = _rows(payload)
    if not rows:
        raise ScopeError("structured scopes payload has no rows")

    assets = _unique_ids(_asset_from_row(row, index) for index, row in enumerate(rows, start=1))
    verdict = classify_policy(policy_text)
    blocked = handle.strip().lower() in (blocklist or set())
    if accounts_allowed is None:
        accounts_allowed = verdict.verdict is not AutomationVerdict.FORBIDDEN and not blocked
    if blocked:
        accounts_allowed = False
    if third_party_ai is None:
        third_party_ai = classify_third_party_ai(policy_text)

    deny = tuple(asset.value for asset in assets if not asset.eligible_for_submission)

    revision = ScopeRevision(
        program=handle,
        platform=platform,
        handle=handle,
        fetched_at=fetched_at or utc_now_iso(),
        source=source
        or f"https://api.hackerone.com/v1/hackers/programs/{handle}/structured_scopes",
        assets=assets,
        automation_verdict=verdict.verdict,
        accounts_allowed=bool(accounts_allowed),
        deny=deny,
        ports=tuple(sorted(set(ports))),
        rate_limits=rate_limits or RateLimit(),
        forbidden=DEFAULT_FORBIDDEN,
        policy_digest=digest_text(policy_text) if policy_text else None,
        policy_text_ref=policy_text_ref,
        third_party_ai=third_party_ai,
    )
    return revision.finalize()


def summarize(revision: ScopeRevision) -> ImportSummary:
    eligible = sum(1 for asset in revision.assets if asset.eligible_for_submission)
    return ImportSummary(
        handle=revision.handle,
        total_assets=len(revision.assets),
        eligible=eligible,
        ineligible=len(revision.assets) - eligible,
        allows=sum(1 for asset in revision.assets if asset.eligible_for_submission and asset.type.targetable),
        denies=sum(1 for asset in revision.assets if not asset.eligible_for_submission),
        automation=revision.automation_verdict.value,
        revision=revision.revision_hash,
    )


def write_revision(revision: ScopeRevision, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(revision.to_yaml(), encoding="utf-8")
    try:
        destination.chmod(0o600)
    except OSError:
        pass
    return destination


def import_payload(
    payload: Any,
    handle: str,
    output: str | Path,
    **kwargs: Any,
) -> tuple[ScopeRevision, ImportSummary]:
    revision = build_revision(payload, handle, **kwargs)
    write_revision(revision, output)
    return revision, summarize(revision)


def import_json_file(
    path: str | Path,
    handle: str,
    output: str | Path,
    **kwargs: Any,
) -> tuple[ScopeRevision, ImportSummary]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return import_payload(payload, handle, output, **kwargs)


__all__ = [
    "DEFAULT_FORBIDDEN",
    "DEFAULT_PORTS",
    "ImportSummary",
    "build_revision",
    "import_json_file",
    "import_payload",
    "load_blocklist",
    "summarize",
    "write_revision",
]
