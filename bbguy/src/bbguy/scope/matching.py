"""Pure scope matching.

No I/O, no DNS, no time. `check_url` is the function the executor calls before a
socket opens; `bbguy scope explain` calls the same function, so an explanation
cannot disagree with an enforcement decision.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

from .canonical import (
    CanonicalHost,
    CanonicalUrl,
    HostRejected,
    UrlRejected,
    canonicalize_host,
    canonicalize_url,
    denied_ip_reason,
    path_has_prefix,
)
from .models import Asset, AssetType, ScopeError, ScopeRevision


@dataclass(frozen=True)
class Decision:
    allowed: bool
    connect_allowed: bool
    request_allowed: bool
    reason: str
    detail: str
    matched_asset: str | None
    matched_deny: str | None
    canonical_host: str | None
    canonical_path: str | None
    port: int | None
    constraints: dict[str, Any] = field(default_factory=dict)
    revision_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "connect_allowed": self.connect_allowed,
            "request_allowed": self.request_allowed,
            "reason": self.reason,
            "detail": self.detail,
            "matched_asset": self.matched_asset,
            "matched_deny": self.matched_deny,
            "canonical_host": self.canonical_host,
            "canonical_path": self.canonical_path,
            "port": self.port,
            "constraints": self.constraints,
            "revision": self.revision_hash,
        }


@dataclass(frozen=True)
class _Allow:
    asset: Asset
    kind: str
    host: str | None = None
    base: str | None = None
    path: str | None = None
    port: int | None = None
    network: ipaddress.IPv4Network | ipaddress.IPv6Network | None = None
    specificity: int = 0


@dataclass(frozen=True)
class _Deny:
    label: str
    kind: str
    host: str | None = None
    base: str | None = None
    path: str | None = None
    port: int | None = None
    network: ipaddress.IPv4Network | ipaddress.IPv6Network | None = None
    include_apex: bool = False


def _host_subtree(host: str, base: str) -> bool:
    return host == base or host.endswith("." + base)


def _host_wildcard(host: str, base: str, include_apex: bool) -> bool:
    if include_apex and host == base:
        return True
    return host.endswith("." + base)


def _parse_network(value: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None


class ScopeMatcher:
    def __init__(self, revision: ScopeRevision, allow_private_ips: bool = False) -> None:
        revision.validate()
        if not revision.verify_hash():
            raise ScopeError("scope revision hash is missing or does not match its contents")
        self.revision = revision
        self.allow_private_ips = allow_private_ips
        self._allows: list[_Allow] = []
        self._denies: list[_Deny] = []
        self._build()

    def _build(self) -> None:
        for asset in self.revision.assets:
            if asset.is_deny:
                deny = self._deny_from_asset(asset)
                if deny is not None:
                    self._denies.append(deny)
                continue
            allow = self._allow_from_asset(asset)
            if allow is not None:
                self._allows.append(allow)

        for value in self.revision.deny:
            deny = self._deny_from_value(value)
            if deny is not None:
                self._denies.append(deny)

    def _allow_from_asset(self, asset: Asset) -> _Allow | None:
        if asset.type is AssetType.DOMAIN:
            host = canonicalize_host(asset.value).host
            return _Allow(asset, "domain", host=host, specificity=300 + len(host))
        if asset.type is AssetType.WILDCARD:
            base = canonicalize_host(asset.value[2:]).host
            return _Allow(
                asset,
                "wildcard",
                base=base,
                specificity=200 + len(base),
                host=base,
            )
        if asset.type is AssetType.URL:
            url = canonicalize_url(asset.value)
            return _Allow(
                asset,
                "url",
                host=url.host.host,
                path=url.path,
                port=url.port,
                specificity=100 + len(url.path),
            )
        if asset.type is AssetType.IP_ADDRESS:
            ip = canonicalize_host(asset.value).ip
            assert ip is not None
            return _Allow(
                asset,
                "ip",
                host=str(ip),
                network=ipaddress.ip_network(ip),
                specificity=500 + ip.max_prefixlen,
            )
        if asset.type is AssetType.CIDR:
            network = _parse_network(asset.value)
            assert network is not None
            return _Allow(
                asset,
                "cidr",
                network=network,
                specificity=400 + network.prefixlen,
            )
        return None

    def _deny_from_asset(self, asset: Asset) -> _Deny | None:
        label = f"{asset.id} ({asset.type.value} {asset.value})"
        if asset.type is AssetType.DOMAIN:
            base = canonicalize_host(asset.value).host
            return _Deny(label, "subtree", base=base)
        if asset.type is AssetType.WILDCARD:
            base = canonicalize_host(asset.value[2:]).host
            return _Deny(label, "wildcard", base=base, include_apex=asset.include_apex)
        if asset.type is AssetType.URL:
            url = canonicalize_url(asset.value)
            return _Deny(
                label, "url", host=url.host.host, path=url.path, port=url.port
            )
        if asset.type is AssetType.IP_ADDRESS:
            ip = canonicalize_host(asset.value).ip
            assert ip is not None
            return _Deny(label, "ip", network=ipaddress.ip_network(ip))
        if asset.type is AssetType.CIDR:
            network = _parse_network(asset.value)
            assert network is not None
            return _Deny(label, "cidr", network=network)
        return None

    def _deny_from_value(self, value: str) -> _Deny | None:
        label = f"deny {value}"
        if value.startswith("*."):
            try:
                base = canonicalize_host(value[2:]).host
            except HostRejected:
                return None
            return _Deny(label, "wildcard", base=base)
        if value.lower().startswith(("http://", "https://")):
            try:
                url = canonicalize_url(value)
            except UrlRejected:
                return None
            return _Deny(label, "url", host=url.host.host, path=url.path, port=url.port)
        if "/" in value:
            network = _parse_network(value)
            if network is not None:
                return _Deny(label, "cidr", network=network)
        try:
            host = canonicalize_host(value)
        except HostRejected:
            return None
        if host.is_ip:
            assert host.ip is not None
            return _Deny(label, "ip", network=ipaddress.ip_network(host.ip))
        return _Deny(label, "subtree", base=host.host)

    def _match_deny(
        self, host: CanonicalHost, url: CanonicalUrl | None
    ) -> _Deny | None:
        for deny in self._denies:
            if deny.kind == "subtree":
                if not host.is_ip and deny.base and _host_subtree(host.host, deny.base):
                    return deny
            elif deny.kind == "wildcard":
                if (
                    not host.is_ip
                    and deny.base
                    and _host_wildcard(host.host, deny.base, deny.include_apex)
                ):
                    return deny
            elif deny.kind == "ip" or deny.kind == "cidr":
                if host.ip is not None and deny.network is not None and host.ip in deny.network:
                    return deny
            elif deny.kind == "url":
                if url is None or host.is_ip:
                    continue
                if host.host != deny.host or url.port != deny.port:
                    continue
                if deny.path is not None and path_has_prefix(url.path, deny.path):
                    return deny
        return None

    def _allowed_constraints(self, asset: Asset) -> dict[str, Any]:
        return {
            "automation": self.revision.automation_for(asset),
            "accounts": self.revision.accounts_for(asset),
            "dns_active": asset.constraints.get("dns_active", "unknown"),
            "portscan": asset.constraints.get("portscan", "unknown"),
            "third_party_ai": asset.constraints.get(
                "third_party_ai", self.revision.third_party_ai
            ),
            "rate": self.revision.constraint_for(asset, "rate"),
            "forbidden_classes": list(self.revision.forbidden),
        }

    def _deny(
        self,
        reason: str,
        detail: str,
        host: CanonicalHost | None = None,
        url: CanonicalUrl | None = None,
        port: int | None = None,
        matched_deny: str | None = None,
    ) -> Decision:
        return Decision(
            allowed=False,
            connect_allowed=False,
            request_allowed=False,
            reason=reason,
            detail=detail,
            matched_asset=None,
            matched_deny=matched_deny,
            canonical_host=host.host if host else None,
            canonical_path=url.path if url else None,
            port=port,
            revision_hash=self.revision.revision_hash,
        )

    def check_host(self, host: str, port: int | None = None) -> Decision:
        try:
            canonical = canonicalize_host(host)
        except HostRejected as exc:
            return self._deny("invalid_host", str(exc))
        return self._decide(canonical, None, port)

    def check_url(self, url: str) -> Decision:
        try:
            canonical = canonicalize_url(url)
        except UrlRejected as exc:
            return self._deny("invalid_url", str(exc))
        if canonical.port is None:  # pragma: no cover - canonicalize_url always sets it
            return self._deny("invalid_url", "missing port")
        return self._decide(canonical.host, canonical, canonical.port)

    def _decide(
        self, host: CanonicalHost, url: CanonicalUrl | None, port: int | None
    ) -> Decision:
        port = port if port is not None else (url.port if url else None)

        if host.is_ip and not self.allow_private_ips:
            assert host.ip is not None
            reason = denied_ip_reason(host.ip)
            if reason is not None:
                return self._deny(
                    "private_or_reserved_ip",
                    f"{host.host} is not a public address ({reason})",
                    host=host,
                    url=url,
                    port=port,
                )

        if port is not None and port not in self.revision.ports:
            return self._deny(
                "port_not_allowed",
                f"port {port} is not in the signed scope port list",
                host=host,
                url=url,
                port=port,
            )

        denied = self._match_deny(host, url)
        if denied is not None:
            return self._deny(
                "denied_by_scope",
                f"matched deny entry {denied.label}",
                host=host,
                url=url,
                port=port,
                matched_deny=denied.label,
            )

        if host.is_ip:
            return self._decide_ip(host, url, port)

        request_candidates: list[_Allow] = []
        connect_only: list[tuple[_Allow, str]] = []

        for allow in self._allows:
            if allow.kind == "domain" and allow.host == host.host or allow.kind == "wildcard" and allow.base and _host_wildcard(
                host.host, allow.base, allow.asset.include_apex
            ):
                request_candidates.append(allow)
            elif allow.kind == "url" and allow.host == host.host:
                if port is not None and allow.port != port:
                    connect_only.append((allow, "url_port_mismatch"))
                    continue
                if url is not None and allow.path is not None and path_has_prefix(
                    url.path, allow.path
                ):
                    request_candidates.append(allow)
                elif url is not None:
                    connect_only.append((allow, "url_path_outside_prefix"))
                else:
                    connect_only.append((allow, "url_requires_request_path"))

        best = max(request_candidates, key=lambda item: item.specificity, default=None)
        if best is not None:
            return Decision(
                allowed=True,
                connect_allowed=True,
                request_allowed=True,
                reason=f"matched_{best.kind}",
                detail=f"asset {best.asset.id} allows this host and path",
                matched_asset=best.asset.id,
                matched_deny=None,
                canonical_host=host.host,
                canonical_path=url.path if url else None,
                port=port,
                constraints=self._allowed_constraints(best.asset),
                revision_hash=self.revision.revision_hash,
            )

        if connect_only:
            allow, why = max(connect_only, key=lambda item: item[0].specificity)
            detail = {
                "url_path_outside_prefix": (
                    f"asset {allow.asset.id} allows {allow.asset.value}; the request path "
                    f"{url.path if url else '(none)'} is outside it"
                ),
                "url_port_mismatch": (
                    f"asset {allow.asset.id} is bound to port {allow.port}, not {port}"
                ),
                "url_requires_request_path": (
                    f"asset {allow.asset.id} is path-scoped; a host-only decision cannot "
                    "authorise a request"
                ),
            }[why]
            return Decision(
                allowed=False,
                connect_allowed=True,
                request_allowed=False,
                reason=why,
                detail=detail,
                matched_asset=allow.asset.id,
                matched_deny=None,
                canonical_host=host.host,
                canonical_path=url.path if url else None,
                port=port,
                constraints=self._allowed_constraints(allow.asset),
                revision_hash=self.revision.revision_hash,
            )

        return self._deny(
            "no_matching_asset",
            f"no allow entry matches {host.host}",
            host=host,
            url=url,
            port=port,
        )

    def _decide_ip(
        self, host: CanonicalHost, url: CanonicalUrl | None, port: int | None
    ) -> Decision:
        assert host.ip is not None
        candidates: list[_Allow] = []
        for allow in self._allows:
            if allow.network is not None and host.ip in allow.network:
                candidates.append(allow)
        best = max(candidates, key=lambda item: item.specificity, default=None)
        if best is None:
            return self._deny(
                "no_matching_asset",
                f"no allow entry matches address {host.host}",
                host=host,
                url=url,
                port=port,
            )
        return Decision(
            allowed=True,
            connect_allowed=True,
            request_allowed=True,
            reason="matched_ip" if best.kind == "ip" else "matched_cidr",
            detail=f"asset {best.asset.id} covers {host.host}",
            matched_asset=best.asset.id,
            matched_deny=None,
            canonical_host=host.host,
            canonical_path=url.path if url else None,
            port=port,
            constraints=self._allowed_constraints(best.asset),
            revision_hash=self.revision.revision_hash,
        )
