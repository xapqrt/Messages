from __future__ import annotations

from dataclasses import replace

from bbguy.scope.diff import diff_revisions
from bbguy.scope.models import AssetType, AutomationVerdict

from .support import acme_revision, asset, revision


def changed_revision():
    assets = tuple(
        replace(item, eligible_for_submission=False) if item.id == "as_02" else item
        for item in acme_revision().assets
        if item.id != "as_11"
    ) + (asset("as_20", "new.example", AssetType.DOMAIN),)
    return revision(
        assets,
        automation=AutomationVerdict.UNKNOWN,
        accounts=False,
        deny=("*.blocked.example",),
        ports=(80, 443, 8443, 8080),
    )


def test_diff_reports_asset_and_policy_changes() -> None:
    old = acme_revision()
    new = changed_revision()
    difference = diff_revisions(old, new)
    assert difference.is_empty is False
    assert [item["asset"] for item in difference.assets_added] == ["new.example"]
    assert [item["id"] for item in difference.assets_removed] == ["as_11"]
    assert len(difference.assets_changed) == 1
    assert difference.assets_changed[0]["key"] == ["wildcard", "*.acme.example"]
    assert difference.assets_changed[0]["eligibility_changed"] is True
    assert difference.denies_added == ("*.blocked.example",)
    assert difference.ports_added == (8080,)
    assert difference.automation == ("allowed", "unknown")
    assert difference.accounts == (True, False)
    assert difference.old_revision != difference.new_revision


def test_diff_of_identical_revisions_is_empty() -> None:
    revision_ = acme_revision()
    difference = diff_revisions(revision_, revision_)
    assert difference.is_empty is True
    assert difference.to_dict()["empty"] is True
