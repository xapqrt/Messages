"""SQLite state store and versioned migrations.

WAL plus `synchronous=FULL` is not enough on macOS: the drive cache needs
`fullfsync` and `checkpoint_fullfsync`. The migration runner treats an edited
already-applied migration as an error rather than silently diverging.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class MigrationError(RuntimeError):
    pass


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    for pragma in ("fullfsync", "checkpoint_fullfsync"):
        try:
            conn.execute(f"PRAGMA {pragma}=ON")
        except sqlite3.DatabaseError:
            # Older SQLite builds without the Darwin-specific pragmas still work;
            # doctor reports the effective setting.
            pass
    return conn


def _migration_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _execute_script(conn: sqlite3.Connection, sql: str) -> None:
    pending = ""
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            if statement:
                conn.execute(statement)
            pending = ""
    if pending.strip():
        conn.execute(pending)


def migrate(conn: sqlite3.Connection, directory: str | Path | None = None) -> int:
    root = Path(directory) if directory is not None else MIGRATIONS_DIR
    files = _migration_files(root)
    if not files:
        raise MigrationError(f"no migrations found in {root}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration (
            version    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            sha256     TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    applied = {
        row["version"]: row for row in conn.execute("SELECT * FROM schema_migration")
    }

    for version, path in enumerate(files, start=1):
        digest = _sha256(path)
        if version in applied:
            if applied[version]["sha256"] != digest:
                raise MigrationError(
                    f"migration {path.name} changed after it was applied "
                    f"({applied[version]['sha256'][:12]} -> {digest[:12]})"
                )
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            conn.execute("BEGIN IMMEDIATE")
            _execute_script(conn, sql)
            conn.execute(
                "INSERT INTO schema_migration(version, name, sha256, applied_at) "
                "VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (version, path.name, digest),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise MigrationError(f"migration {path.name} failed: {exc}") from exc

    return len(files)


def open_state_db(path: str | Path) -> sqlite3.Connection:
    conn = connect(path)
    migrate(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migration").fetchone()
    return int(row["version"] or 0)


def checkpoint(conn: sqlite3.Connection, mode: str = "TRUNCATE") -> tuple[int, int, int]:
    row = conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
    return (int(row[0]), int(row[1]), int(row[2]))


def integrity_check(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0])
