"""Diff two signed scope revisions.

Phase 1's gate asks for a human-readable list of what entered and left scope.
The diff keys assets on `(type, value)` rather than id, because an id is a row
number in one export and can move between imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Asset, ScopeRevision


def _key(asset: Asset) -> tuple[str, str]:
    return (asset.type.value, asset.value)


@dataclass(frozen=True)
class ScopeDiff:
    old_revision: str
    new_revision: str
    assets_added: tuple[dict[str, Any], ...]
    assets_removed: tuple[dict[str, Any], ...]
    assets_changed: tuple[dict[str, Any], ...]
    denies_added: tuple[str, ...]
    denies_removed: tuple[str, ...]
    ports_added: tuple[int, ...]
    ports_removed: tuple[int, ...]
    automation: tuple[str, str] | None
    accounts: tuple[bool, bool] | None

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.assets_added,
                self.assets_removed,
                self.assets_changed,
                self.denies_added,
                self.denies_removed,
                self.ports_added,
                self.ports_removed,
                self.automation,
                self.accounts,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_revision": self.old_revision,
            "new_revision": self.new_revision,
            "assets_added": list(self.assets_added),
            "assets_removed": list(self.assets_removed),
            "assets_changed": list(self.assets_changed),
            "denies_added": list(self.denies_added),
            "denies_removed": list(self.denies_removed),
            "ports_added": list(self.ports_added),
            "ports_removed": list(self.ports_removed),
            "automation": self.automation,
            "accounts": self.accounts,
            "empty": self.is_empty,
        }


def _public(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "asset": asset.value,
        "type": asset.type.value,
        "eligible_for_submission": asset.eligible_for_submission,
        "instruction": asset.instruction,
    }


def diff_revisions(old: ScopeRevision, new: ScopeRevision) -> ScopeDiff:
    old_by_key = {_key(asset): asset for asset in old.assets}
    new_by_key = {_key(asset): asset for asset in new.assets}

    added = tuple(_public(new_by_key[key]) for key in sorted(new_by_key.keys() - old_by_key.keys()))
    removed = tuple(
        _public(old_by_key[key]) for key in sorted(old_by_key.keys() - new_by_key.keys())
    )

    changed: list[dict[str, Any]] = []
    for key in sorted(old_by_key.keys() & new_by_key.keys()):
        before = old_by_key[key]
        after = new_by_key[key]
        if before.to_dict() != after.to_dict():
            changed.append(
                {
                    "key": list(key),
                    "before": _public(before),
                    "after": _public(after),
                    "eligibility_changed": before.eligible_for_submission
                    != after.eligible_for_submission,
                }
            )

    old_denies = set(old.deny)
    new_denies = set(new.deny)
    automation = None
    if old.automation_verdict is not new.automation_verdict:
        automation = (old.automation_verdict.value, new.automation_verdict.value)
    accounts = None
    if old.accounts_allowed is not new.accounts_allowed:
        accounts = (old.accounts_allowed, new.accounts_allowed)

    return ScopeDiff(
        old_revision=old.revision_hash,
        new_revision=new.revision_hash,
        assets_added=added,
        assets_removed=removed,
        assets_changed=tuple(changed),
        denies_added=tuple(sorted(new_denies - old_denies)),
        denies_removed=tuple(sorted(old_denies - new_denies)),
        ports_added=tuple(sorted(set(new.ports) - set(old.ports))),
        ports_removed=tuple(sorted(set(old.ports) - set(new.ports))),
        automation=automation,
        accounts=accounts,
    )


__all__ = ["ScopeDiff", "diff_revisions"]
