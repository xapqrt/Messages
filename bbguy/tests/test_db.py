from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bbguy import db

EXPECTED_TABLES = {
    "program",
    "scope_revision",
    "scope_asset",
    "run",
    "run_grant",
    "control_epoch",
    "job",
    "job_step",
    "asset",
    "asset_change",
    "service",
    "endpoint",
    "fixture",
    "oracle",
    "hypothesis",
    "hypothesis_evidence",
    "hypothesis_verdict",
    "finding",
    "finding_evidence",
    "finding_reproduction",
    "evidence_blob",
    "manifest_head",
    "approval_request",
}


def test_migration_creates_every_table(tmp_path: Path) -> None:
    conn = db.open_state_db(tmp_path / "state.db")
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= tables
    assert db.schema_version(conn) == 1
    assert db.integrity_check(conn) == "ok"
    conn.close()


def test_wal_and_checkpoint(tmp_path: Path) -> None:
    conn = db.open_state_db(tmp_path / "state.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute(
        "INSERT INTO program(id, handle, platform, created_at) VALUES ('p1','acme','hackerone','now')"
    )
    conn.commit()
    assert db.checkpoint(conn)[0] == 0
    conn.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    conn = db.open_state_db(path)
    assert db.migrate(conn) == 1
    assert db.migrate(conn) == 1
    assert db.schema_version(conn) == 1
    conn.close()
    conn = db.open_state_db(path)
    assert db.schema_version(conn) == 1
    conn.close()


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    conn = db.open_state_db(tmp_path / "state.db")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO scope_revision(id, program_id, revision_hash, fetched_at, yaml_blob) "
            "VALUES ('s1','missing','sha256:x','now','{}')"
        )
    conn.rollback()
    conn.close()


def test_edited_migration_is_refused(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "0001_init.sql"
    migration.write_text("CREATE TABLE first(a INTEGER);", encoding="utf-8")
    conn = db.connect(tmp_path / "state.db")
    assert db.migrate(conn, migrations) == 1
    migration.write_text("CREATE TABLE first(a INTEGER, b INTEGER);", encoding="utf-8")
    with pytest.raises(db.MigrationError, match="changed after it was applied"):
        db.migrate(conn, migrations)
    conn.close()


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_init.sql").write_text("CREATE TABLE first(a INTEGER);", encoding="utf-8")
    (migrations / "0002_bad.sql").write_text(
        "CREATE TABLE second(a INTEGER);\nTHIS IS NOT SQL;\n", encoding="utf-8"
    )
    conn = db.connect(tmp_path / "state.db")
    with pytest.raises(db.MigrationError, match="0002_bad.sql"):
        db.migrate(conn, migrations)
    assert db.schema_version(conn) == 1
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "first" in tables
    assert "second" not in tables
    conn.close()


def test_program_and_scope_revision_round_trip(tmp_path: Path) -> None:
    conn = db.open_state_db(tmp_path / "state.db")
    conn.execute(
        "INSERT INTO program(id, handle, platform, created_at) "
        "VALUES ('p1','acme','hackerone','2026-11-09T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO scope_revision(id, program_id, revision_hash, fetched_at, yaml_blob, signature) "
        "VALUES ('s1','p1','sha256:abc','2026-11-09T00:00:00Z','program: acme','sig')"
    )
    conn.execute(
        "INSERT INTO scope_asset(id, scope_revision_id, asset, type, eligible_for_submission, "
        "eligible_for_bounty, is_deny) VALUES ('as_1','s1','acme.example','domain',1,1,0)"
    )
    conn.commit()
    row = conn.execute(
        "SELECT p.handle, s.revision_hash, a.asset FROM program p "
        "JOIN scope_revision s ON s.program_id=p.id JOIN scope_asset a ON a.scope_revision_id=s.id"
    ).fetchone()
    assert tuple(row) == ("acme", "sha256:abc", "acme.example")
    conn.execute("DELETE FROM program WHERE id='p1'")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM scope_revision").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM scope_asset").fetchone()[0] == 0
    conn.close()


def test_job_state_check(tmp_path: Path) -> None:
    conn = db.open_state_db(tmp_path / "state.db")
    conn.execute(
        "INSERT INTO program(id, handle, platform, created_at) VALUES ('p1','acme','hackerone','now')"
    )
    conn.execute(
        "INSERT INTO run(id, program_id, profile, started_at, state) "
        "VALUES ('r1','p1','recon','now','running')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO job(id, run_id, kind, state) VALUES ('j1','r1','recon','not-a-state')"
        )
    conn.rollback()
    conn.close()
