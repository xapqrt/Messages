from __future__ import annotations

import json
from pathlib import Path

import yaml

from bbguy.cli import EXIT_ERROR, EXIT_GATE, EXIT_OK, main
from bbguy.scope.models import ScopeRevision

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def import_scope(home: Path, out: Path) -> int:
    return main(
        [
            "--home",
            str(home),
            "scope",
            "import",
            "--structured-scopes",
            str(FIXTURES / "hackerone_acme_structured_scopes.json"),
            "--handle",
            "acme",
            "--out",
            str(out),
            "--policy",
            str(FIXTURES / "policy_acme.txt"),
            "--policy-ref",
            "policy_acme.txt",
            "--fetched-at",
            "2026-11-09T18:00:00Z",
            "--source",
            "fixture://acme",
        ]
    )


def test_doctor_json(tmp_path: Path, capsys) -> None:
    assert main(["--home", str(tmp_path), "doctor", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    required = [item for item in payload["checks"] if item["required"]]
    assert all(item["ok"] for item in required)
    skipped = [item for item in payload["checks"] if not item["required"]]
    assert {item["name"] for item in skipped} == {
        "tailscale",
        "policy_proxy",
        "dnsgate",
        "job_machine",
    }


def test_doctor_strict_fails_on_unbuilt_components(tmp_path: Path, capsys) -> None:
    assert main(["--home", str(tmp_path), "doctor", "--strict"]) == EXIT_GATE
    output = capsys.readouterr().out
    assert "[SKIP] tailscale" in output


def test_db_migrate(tmp_path: Path, capsys) -> None:
    assert main(["--home", str(tmp_path), "db", "migrate", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == 1
    assert payload["journal_mode"] == "wal"
    assert Path(payload["db"]).exists()


def test_program_add_list_and_duplicate(tmp_path: Path, capsys) -> None:
    assert main(["--home", str(tmp_path), "program", "add", "Acme"]) == EXIT_OK
    assert "added acme" in capsys.readouterr().out
    assert main(["--home", str(tmp_path), "program", "add", "acme"]) == EXIT_ERROR
    assert main(["--home", str(tmp_path), "program", "list", "--json"]) == EXIT_OK
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["handle"] == "acme"


def test_scope_import_verify_explain_and_render(tmp_path: Path, capsys) -> None:
    scope = tmp_path / "acme.yaml"
    assert import_scope(tmp_path, scope) == EXIT_OK
    capsys.readouterr()
    assert scope.exists()
    revision = ScopeRevision.from_yaml(scope)
    assert revision.verify_hash()

    assert main(["--home", str(tmp_path), "scope", "verify", str(scope), "--json"]) == EXIT_OK
    verified = json.loads(capsys.readouterr().out)
    assert verified["handle"] == "acme"
    assert verified["allows"] == 6
    assert verified["denies"] == 4

    assert main(
        [
            "--home",
            str(tmp_path),
            "scope",
            "explain",
            str(scope),
            "https://portal.example.net/api/v2/x",
            "--json",
        ]
    ) == EXIT_OK
    decision = json.loads(capsys.readouterr().out)
    assert decision["allowed"] is True
    assert decision["matched_asset"] == "as_05"

    assert main(
        [
            "--home",
            str(tmp_path),
            "scope",
            "explain",
            str(scope),
            "https://portal.example.net/admin/x",
        ]
    ) == EXIT_GATE
    assert "DENY" in capsys.readouterr().out

    out = tmp_path / "policy.json"
    assert main(
        ["--home", str(tmp_path), "scope", "render", str(scope), "--out", str(out)]
    ) == EXIT_OK
    rendered = json.loads(out.read_text())
    assert rendered["target"]["allows"]
    assert "github.com" not in json.dumps(rendered["target"])


def test_scope_show_and_tamper_detection(tmp_path: Path, capsys) -> None:
    scope = tmp_path / "acme.yaml"
    assert import_scope(tmp_path, scope) == EXIT_OK
    capsys.readouterr()
    assert main(["--home", str(tmp_path), "scope", "show", str(scope), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["revision"].startswith("sha256:")

    data = yaml.safe_load(scope.read_text())
    data["assets"][0]["asset"] = "evil.example"
    scope.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert main(["--home", str(tmp_path), "scope", "verify", str(scope)]) == EXIT_ERROR
    assert "hash mismatch" in capsys.readouterr().err


def test_scope_explain_invalid_target_is_a_deny(tmp_path: Path, capsys) -> None:
    scope = tmp_path / "acme.yaml"
    assert import_scope(tmp_path, scope) == EXIT_OK
    capsys.readouterr()
    assert main(
        ["--home", str(tmp_path), "scope", "explain", str(scope), "https://user@acme.example/x"]
    ) == EXIT_GATE
    output = capsys.readouterr().out
    assert "invalid_url" in output


def test_missing_scope_file_is_an_error(tmp_path: Path, capsys) -> None:
    assert main(["--home", str(tmp_path), "scope", "verify", str(tmp_path / "nope.yaml")]) == EXIT_ERROR
    assert "error:" in capsys.readouterr().err


def test_scope_show_diff_against_itself(tmp_path: Path, capsys) -> None:
    scope = tmp_path / "acme.yaml"
    assert import_scope(tmp_path, scope) == EXIT_OK
    capsys.readouterr()
    assert main(
        [
            "--home",
            str(tmp_path),
            "scope",
            "show",
            str(scope),
            "--diff",
            str(scope),
            "--json",
        ]
    ) == EXIT_OK
    difference = json.loads(capsys.readouterr().out)
    assert difference["empty"] is True
    assert difference["old_revision"] == difference["new_revision"]
