from __future__ import annotations

import json
from pathlib import Path

import pytest

from bbguy.scope.importer import (
    build_revision,
    import_json_file,
    load_blocklist,
    summarize,
    write_revision,
)
from bbguy.scope.models import AssetType, AutomationVerdict, ScopeError, ScopeRevision
from bbguy.scope.render import render_policy

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def payload() -> dict:
    return json.loads((FIXTURES / "hackerone_acme_structured_scopes.json").read_text())


def policy_text() -> str:
    return (FIXTURES / "policy_acme.txt").read_text()


def make_revision(**kwargs) -> ScopeRevision:
    kwargs.setdefault("policy_text", policy_text())
    kwargs.setdefault("policy_text_ref", "policy_acme.txt")
    return build_revision(
        payload(),
        "acme",
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://acme",
        **kwargs,
    )


def test_import_preserves_every_row() -> None:
    revision = make_revision()
    assert len(revision.assets) == 12
    assert len({asset.id for asset in revision.assets}) == 12
    assert [asset.id for asset in revision.assets if not asset.eligible_for_submission] == [
        "as_03",
        "as_04",
        "as_06",
        "as_11",
    ]


def test_import_derives_denies_including_nested_ineligible_wildcard() -> None:
    revision = make_revision()
    assert "stg.acme.example" in revision.deny
    assert "*.stg.acme.example" in revision.deny
    assert "https://portal.example.net/admin/" in revision.deny
    assert "internal.acme.example" in revision.deny
    assert revision.automation_verdict is AutomationVerdict.ALLOWED
    assert revision.accounts_allowed is True
    assert revision.third_party_ai == "forbidden"


def test_source_code_and_other_are_retained_but_not_allowlisted() -> None:
    revision = make_revision()
    assert revision.asset("as_09").type is AssetType.SOURCE_CODE
    assert revision.asset("as_10").type is AssetType.OTHER
    policy = render_policy(revision)
    serialized = json.dumps(policy)
    assert "github.com" not in json.dumps(policy["target"])
    assert "com.acme.app" not in json.dumps(policy["target"])
    assert len(policy["target"]["allows"]) == 6
    assert {item["id"] for item in policy["recorded_only"]} == {"as_09", "as_10"}
    assert serialized  # the render is JSON-serialisable


def test_yaml_round_trip_is_stable(tmp_path: Path) -> None:
    revision = make_revision()
    path = write_revision(revision, tmp_path / "acme.yaml")
    loaded = ScopeRevision.from_yaml(path)
    assert loaded.revision_hash == revision.revision_hash
    assert loaded.to_dict() == revision.to_dict()


def test_edited_yaml_is_refused(tmp_path: Path) -> None:
    revision = make_revision()
    path = write_revision(revision, tmp_path / "acme.yaml")
    data = json.loads(json.dumps(revision.to_dict()))
    data["assets"][0]["asset"] = "evil.example"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScopeError, match="hash mismatch"):
        ScopeRevision.from_yaml(path)


def test_missing_eligibility_fails_closed() -> None:
    revision = build_revision(
        {
            "data": [
                {
                    "id": 1,
                    "attributes": {
                        "asset_identifier": "x.example",
                        "asset_type": "domain",
                        "instruction": "Ask first.",
                    },
                }
            ]
        },
        "lab",
        policy_text=None,
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://lab",
    )
    assert revision.asset("as_01").eligible_for_submission is False
    assert revision.automation_verdict is AutomationVerdict.UNKNOWN
    assert revision.accounts_allowed is True


def test_flat_list_shape_and_type_normalisation() -> None:
    revision = build_revision(
        [
            {"asset_identifier": "*.x.example", "asset_type": "domain"},
            {"asset_identifier": "1.2.3.4", "asset_type": "domain"},
            {"asset_identifier": "10.0.0.0/8", "asset_type": "domain"},
            {"asset_identifier": "https://x.example/app", "asset_type": "domain"},
        ],
        "lab",
        policy_text="Automated scanning is allowed.",
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://lab",
    )
    assert [asset.type for asset in revision.assets] == [
        AssetType.WILDCARD,
        AssetType.IP_ADDRESS,
        AssetType.CIDR,
        AssetType.URL,
    ]


def test_duplicate_ids_get_suffixes() -> None:
    revision = build_revision(
        [
            {"id": "1", "asset_identifier": "a.example", "asset_type": "domain"},
            {"id": "1", "asset_identifier": "b.example", "asset_type": "domain"},
        ],
        "lab",
        policy_text="Automated scanning is allowed.",
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://lab",
    )
    assert [asset.id for asset in revision.assets] == ["1", "1_2"]


def test_url_without_scheme_is_an_error() -> None:
    with pytest.raises(ScopeError, match="without scheme"):
        build_revision(
            [{"asset_identifier": "x.example/app", "asset_type": "url"}],
            "lab",
            policy_text="Automated scanning is allowed.",
            fetched_at="2026-11-09T18:00:00Z",
            source="fixture://lab",
        )


def test_forbidden_policy_turns_accounts_off() -> None:
    revision = make_revision(policy_text="Automated scanning is not allowed.")
    assert revision.automation_verdict is AutomationVerdict.FORBIDDEN
    assert revision.accounts_allowed is False


def test_forbidden_policy_cannot_keep_accounts_on() -> None:
    with pytest.raises(ScopeError, match="accounts_allowed"):
        make_revision(policy_text="Automated scanning is not allowed.", accounts_allowed=True)


def test_blocklist_forces_accounts_off() -> None:
    revision = make_revision(blocklist={"acme"})
    assert revision.accounts_allowed is False


def test_blocklist_loader(tmp_path: Path) -> None:
    path = tmp_path / "blocklist.yaml"
    path.write_text("handles:\n  - ACME\n  - Other\n", encoding="utf-8")
    assert load_blocklist(path) == {"acme", "other"}


def test_summary_counts() -> None:
    summary = summarize(make_revision())
    assert summary.total_assets == 12
    assert summary.eligible == 8
    assert summary.ineligible == 4
    assert summary.allows == 6
    assert summary.denies == 4
    assert summary.automation == "allowed"


def test_import_json_file_writes_output(tmp_path: Path) -> None:
    revision, summary = import_json_file(
        FIXTURES / "hackerone_acme_structured_scopes.json",
        "acme",
        tmp_path / "acme.yaml",
        policy_text=policy_text(),
        fetched_at="2026-11-09T18:00:00Z",
        source="fixture://acme",
    )
    assert summary.total_assets == 12
    assert (tmp_path / "acme.yaml").exists()
    assert ScopeRevision.from_yaml(tmp_path / "acme.yaml").revision_hash == revision.revision_hash
