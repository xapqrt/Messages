"""Typed, signed scope revisions.

The model preserves every row from the program export, including ineligible
assets. An ineligible row is a deny, never something to filter out: HackerOne
expresses out-of-scope subtrees as `eligible_for_submission: false`, so dropping
them silently widens a wildcard.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .canonical import canonicalize_host, canonicalize_url

SCHEMA = 1
SEVERITIES = ("critical", "high", "medium", "low", "info", "none")
CONSTRAINT_KEYS = frozenset(
    {
        "automation",
        "dns_active",
        "portscan",
        "accounts",
        "rate",
        "forbidden_classes",
        "third_party_ai",
    }
)
_TRI_STATE = frozenset({"allowed", "unknown", "forbidden"})


class ScopeError(ValueError):
    pass


class AssetType(str, Enum):
    DOMAIN = "domain"
    WILDCARD = "wildcard"
    URL = "url"
    IP_ADDRESS = "ip_address"
    CIDR = "cidr"
    SOURCE_CODE = "source_code"
    OTHER = "other"

    @property
    def targetable(self) -> bool:
        return self not in (AssetType.SOURCE_CODE, AssetType.OTHER)


class AutomationVerdict(str, Enum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    FORBIDDEN = "forbidden"


def _as_bool(value: Any, name: str, default: bool | None = None) -> bool:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ScopeError(f"{name} must be a boolean")


def _as_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ScopeError(f"{name} must be a non-empty string")
    return value


def _as_verdict(value: Any) -> AutomationVerdict:
    try:
        return AutomationVerdict(value)
    except (ValueError, TypeError) as exc:
        raise ScopeError(f"unknown automation verdict {value!r}") from exc


def _as_port(value: Any) -> int:
    try:
        port = int(value)
    except (ValueError, TypeError) as exc:
        raise ScopeError(f"invalid port {value!r}") from exc
    return port


@dataclass
class Asset:
    id: str
    value: str
    type: AssetType
    eligible_for_submission: bool = True
    eligible_for_bounty: bool = False
    instruction: str | None = None
    include_apex: bool = False
    max_severity: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)

    @property
    def is_deny(self) -> bool:
        return not self.eligible_for_submission

    def validate(self) -> None:
        _as_text(self.id, "asset.id")
        if not isinstance(self.type, AssetType):
            raise ScopeError(f"{self.id}: unknown asset type {self.type!r}")
        if not isinstance(self.value, str) or not self.value:
            raise ScopeError(f"{self.id}: asset value must be non-empty")
        if self.max_severity is not None and self.max_severity not in SEVERITIES:
            raise ScopeError(f"{self.id}: unknown max_severity {self.max_severity!r}")
        unknown = set(self.constraints) - CONSTRAINT_KEYS
        if unknown:
            raise ScopeError(f"{self.id}: unknown constraint keys {sorted(unknown)}")
        for key in ("automation", "dns_active", "portscan", "accounts"):
            if key in self.constraints and self.constraints[key] not in _TRI_STATE:
                raise ScopeError(f"{self.id}: {key} must be allowed|unknown|forbidden")
        if "third_party_ai" in self.constraints and self.constraints["third_party_ai"] not in {
            "allowed",
            "unknown",
            "forbidden",
            "deepseek_only",
        }:
            raise ScopeError(f"{self.id}: third_party_ai policy is not recognised")
        if "rate" in self.constraints and not isinstance(self.constraints["rate"], dict):
            raise ScopeError(f"{self.id}: rate must be an object")
        if "forbidden_classes" in self.constraints and not isinstance(
            self.constraints["forbidden_classes"], list
        ):
            raise ScopeError(f"{self.id}: forbidden_classes must be a list")

        if self.type == AssetType.DOMAIN:
            if "*" in self.value:
                raise ScopeError(f"{self.id}: domain asset contains a wildcard")
            host = canonicalize_host(self.value)
            if host.is_ip:
                raise ScopeError(f"{self.id}: IP literal cannot be a domain asset")
        elif self.type == AssetType.WILDCARD:
            if not self.value.startswith("*.") or self.value.count("*") != 1:
                raise ScopeError(f"{self.id}: wildcard must be a single leading '*.'")
            canonicalize_host(self.value[2:])
        elif self.type == AssetType.URL:
            canonicalize_url(self.value)
        elif self.type == AssetType.IP_ADDRESS:
            host = canonicalize_host(self.value)
            if not host.is_ip:
                raise ScopeError(f"{self.id}: ip_address asset is not an IP")
        elif self.type == AssetType.CIDR:
            try:
                ipaddress.ip_network(self.value, strict=False)
            except ValueError as exc:
                raise ScopeError(f"{self.id}: invalid CIDR {self.value!r}") from exc
        elif self.type in (AssetType.SOURCE_CODE, AssetType.OTHER):
            pass
        else:  # pragma: no cover - enum is closed
            raise ScopeError(f"{self.id}: unhandled asset type {self.type}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset": self.value,
            "type": self.type.value,
            "eligible_for_submission": self.eligible_for_submission,
            "eligible_for_bounty": self.eligible_for_bounty,
            "instruction": self.instruction,
            "include_apex": self.include_apex,
            "max_severity": self.max_severity,
            "constraints": dict(self.constraints),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Asset:
        if not isinstance(raw, dict):
            raise ScopeError("asset must be an object")
        value = raw.get("asset", raw.get("value", raw.get("identifier")))
        type_value = raw.get("type", raw.get("asset_type"))
        try:
            asset_type = AssetType(type_value)
        except (ValueError, TypeError) as exc:
            raise ScopeError(f"unknown asset type {type_value!r}") from exc
        asset = cls(
            id=str(raw.get("id", "")),
            value=str(value) if value is not None else "",
            type=asset_type,
            eligible_for_submission=_as_bool(
                raw.get("eligible_for_submission"), "eligible_for_submission", True
            ),
            eligible_for_bounty=_as_bool(
                raw.get("eligible_for_bounty"), "eligible_for_bounty", False
            ),
            instruction=raw.get("instruction"),
            include_apex=_as_bool(raw.get("include_apex"), "include_apex", False),
            max_severity=raw.get("max_severity"),
            constraints=dict(raw.get("constraints") or {}),
        )
        asset.validate()
        return asset


@dataclass
class RateLimit:
    default_rps: float = 2.0
    burst: int = 10
    per_host: dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.default_rps, (int, float)) or self.default_rps <= 0:
            raise ScopeError("default_rps must be positive")
        if not isinstance(self.burst, int) or self.burst <= 0:
            raise ScopeError("burst must be a positive integer")
        for host, rps in self.per_host.items():
            if not isinstance(rps, (int, float)) or rps <= 0:
                raise ScopeError(f"per_host rate for {host!r} must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_rps": self.default_rps,
            "burst": self.burst,
            "per_host": dict(sorted(self.per_host.items())),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> RateLimit:
        raw = raw or {}
        rate = cls(
            default_rps=float(raw.get("default_rps", 2.0)),
            burst=int(raw.get("burst", 10)),
            per_host={str(k): float(v) for k, v in (raw.get("per_host") or {}).items()},
        )
        rate.validate()
        return rate


@dataclass
class ScopeRevision:
    program: str
    platform: str
    handle: str
    fetched_at: str
    source: str
    assets: tuple[Asset, ...]
    automation_verdict: AutomationVerdict = AutomationVerdict.UNKNOWN
    accounts_allowed: bool = True
    deny: tuple[str, ...] = ()
    ports: tuple[int, ...] = (80, 443)
    rate_limits: RateLimit = field(default_factory=RateLimit)
    forbidden: tuple[str, ...] = ()
    policy_digest: str | None = None
    policy_text_ref: str | None = None
    third_party_ai: str = "unknown"
    signature: dict[str, Any] = field(default_factory=dict)
    revision_hash: str = ""

    def validate(self) -> None:
        _as_text(self.program, "program")
        _as_text(self.platform, "platform")
        _as_text(self.handle, "handle")
        _as_text(self.fetched_at, "fetched_at")
        _as_text(self.source, "source")
        if not isinstance(self.automation_verdict, AutomationVerdict):
            try:
                self.automation_verdict = AutomationVerdict(self.automation_verdict)
            except ValueError as exc:
                raise ScopeError(f"unknown automation verdict {self.automation_verdict!r}") from exc
        if self.automation_verdict is AutomationVerdict.FORBIDDEN and self.accounts_allowed:
            raise ScopeError("accounts_allowed cannot be true when automation is forbidden")
        if self.third_party_ai not in {"allowed", "unknown", "forbidden", "deepseek_only"}:
            raise ScopeError(f"unknown third_party_ai policy {self.third_party_ai!r}")
        if not self.assets:
            raise ScopeError("scope revision has no assets")
        seen: set[str] = set()
        for asset in self.assets:
            asset.validate()
            if asset.id in seen:
                raise ScopeError(f"duplicate asset id {asset.id!r}")
            seen.add(asset.id)
        if not self.ports:
            raise ScopeError("scope revision has no ports")
        if len(set(self.ports)) != len(self.ports):
            raise ScopeError("duplicate ports")
        for port in self.ports:
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise ScopeError(f"invalid port {port!r}")
        for item in self.deny:
            _as_text(item, "deny entry")
        self.rate_limits.validate()
        if self.policy_digest is not None and not self.policy_digest.startswith("sha256:"):
            raise ScopeError("policy_digest must be 'sha256:<hex>'")

    @property
    def targetable_assets(self) -> tuple[Asset, ...]:
        return tuple(asset for asset in self.assets if asset.type.targetable)

    def asset(self, asset_id: str) -> Asset | None:
        for item in self.assets:
            if item.id == asset_id:
                return item
        return None

    def automation_for(self, asset: Asset) -> str:
        if self.automation_verdict is AutomationVerdict.FORBIDDEN:
            return "forbidden"
        explicit = asset.constraints.get("automation")
        if explicit in _TRI_STATE:
            return str(explicit)
        if asset.instruction:
            # Prose a human has not classified is not permission.
            return "unknown"
        return self.automation_verdict.value

    def accounts_for(self, asset: Asset) -> str:
        explicit = asset.constraints.get("accounts")
        if explicit in _TRI_STATE:
            return str(explicit)
        # D8 (policy silent => passive only) is stronger than D7's default:
        # an account is an active test, so it stays off until automation is
        # permitted for this asset.
        if self.automation_for(asset) != "allowed":
            return "forbidden"
        return "allowed" if self.accounts_allowed else "forbidden"

    def constraint_for(self, asset: Asset, name: str) -> Any:
        if name == "automation":
            return self.automation_for(asset)
        if name == "accounts":
            return self.accounts_for(asset)
        if name == "rate":
            return asset.constraints.get("rate") or self.rate_limits.to_dict()
        return asset.constraints.get(name, "unknown")

    def _hash_payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "program": self.program,
            "platform": self.platform,
            "handle": self.handle,
            "fetched_at": self.fetched_at,
            "source": self.source,
            "automation_verdict": self.automation_verdict.value,
            "accounts_allowed": self.accounts_allowed,
            "assets": [asset.to_dict() for asset in sorted(self.assets, key=lambda a: a.id)],
            "deny": sorted(self.deny),
            "ports": sorted(self.ports),
            "rate_limits": self.rate_limits.to_dict(),
            "forbidden": sorted(self.forbidden),
            "policy_digest": self.policy_digest,
            "policy_text_ref": self.policy_text_ref,
            "third_party_ai": self.third_party_ai,
        }

    def compute_hash(self) -> str:
        payload = json.dumps(
            self._hash_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def finalize(self) -> ScopeRevision:
        self.validate()
        self.revision_hash = self.compute_hash()
        return self

    def verify_hash(self) -> bool:
        return bool(self.revision_hash) and self.revision_hash == self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "program": self.program,
            "platform": self.platform,
            "handle": self.handle,
            "revision": self.revision_hash,
            "fetched_at": self.fetched_at,
            "source": self.source,
            "automation_verdict": self.automation_verdict.value,
            "accounts_allowed": self.accounts_allowed,
            "policy": {
                "digest": self.policy_digest,
                "text_ref": self.policy_text_ref,
                "third_party_ai": self.third_party_ai,
            },
            "assets": [asset.to_dict() for asset in self.assets],
            "deny": list(self.deny),
            "ports": list(self.ports),
            "rate_limits": self.rate_limits.to_dict(),
            "forbidden": list(self.forbidden),
            "signature": dict(self.signature),
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False, width=100, allow_unicode=True)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], strict_hash: bool = True) -> ScopeRevision:
        if not isinstance(raw, dict):
            raise ScopeError("scope revision must be an object")
        policy = raw.get("policy") or {}
        assets_raw = raw.get("assets")
        if not isinstance(assets_raw, list) or not assets_raw:
            raise ScopeError("scope revision must contain a non-empty assets list")
        revision = cls(
            program=str(raw.get("program", "")),
            platform=str(raw.get("platform", "")),
            handle=str(raw.get("handle", "")),
            fetched_at=str(raw.get("fetched_at", "")),
            source=str(raw.get("source", "")),
            assets=tuple(Asset.from_dict(item) for item in assets_raw),
            automation_verdict=_as_verdict(raw.get("automation_verdict", "unknown")),
            accounts_allowed=_as_bool(raw.get("accounts_allowed"), "accounts_allowed", True),
            deny=tuple(str(item) for item in (raw.get("deny") or ())),
            ports=tuple(_as_port(item) for item in (raw.get("ports") or (80, 443))),
            rate_limits=RateLimit.from_dict(raw.get("rate_limits")),
            forbidden=tuple(str(item).lower() for item in (raw.get("forbidden") or ())),
            policy_digest=policy.get("digest"),
            policy_text_ref=policy.get("text_ref"),
            third_party_ai=str(policy.get("third_party_ai", "unknown")),
            signature=dict(raw.get("signature") or {}),
            revision_hash=str(raw.get("revision", "")),
        )
        revision.validate()
        expected = revision.compute_hash()
        if revision.revision_hash:
            if strict_hash and revision.revision_hash != expected:
                raise ScopeError(
                    "revision hash mismatch: the revision was edited after it was generated "
                    f"(expected {expected})"
                )
        else:
            revision.revision_hash = expected
        return revision

    @classmethod
    def from_yaml(cls, path: str | Path, strict_hash: bool = True) -> ScopeRevision:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw, strict_hash=strict_hash)


def digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "Asset",
    "AssetType",
    "AutomationVerdict",
    "RateLimit",
    "ScopeError",
    "ScopeRevision",
    "digest_text",
]
