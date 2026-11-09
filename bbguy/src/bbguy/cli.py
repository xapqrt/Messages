"""bbguy command line.

Only Phase 0/1 verbs exist here. `run`, `proof` and `pack` are deliberately
absent: a command that cannot reach a real target is worse than no command.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import __version__, db
from .clock import Clock, monotonic_ns
from .config import ConfigError, Settings, disk_free_gb, load_settings
from .scope.diff import diff_revisions
from .scope.importer import import_json_file, load_blocklist
from .scope.matching import ScopeMatcher
from .scope.models import ScopeError, ScopeRevision
from .scope.render import render_policy

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_GATE = 2


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _settings(args: argparse.Namespace) -> Settings:
    settings = load_settings(getattr(args, "home", None))
    if getattr(args, "db", None):
        settings = Settings(
            home=settings.home,
            db_path=Path(args.db).expanduser().resolve(),
            scope_dir=settings.scope_dir,
            evidence_dir=settings.evidence_dir,
            bundles_dir=settings.bundles_dir,
            log_dir=settings.log_dir,
        )
    return settings


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = _settings(args)
    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, detail: str, required: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "required": required})

    add("python", sys.version_info >= (3, 11), sys.version.split()[0])
    add("sqlite", sqlite3.sqlite_version_info >= (3, 35), sqlite3.sqlite_version)

    try:
        import idna

        add("idna", True, idna.__version__)
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - dependency is declared
        add("idna", False, repr(exc))

    start = monotonic_ns()
    time.sleep(0.02)
    after = monotonic_ns()
    add("monotonic_clock", after > start, f"{start} -> {after}, boot {Clock.read().boot_id}")

    try:
        settings.ensure_dirs()
        free = disk_free_gb(settings.home)
        add(
            "disk_free",
            free >= settings.disk_floor_gb,
            f"{free:.2f} GiB free, floor {settings.disk_floor_gb:.2f} GiB",
        )
    except Exception as exc:  # noqa: BLE001
        add("disk_free", False, repr(exc))

    try:
        scratch = settings.home / "doctor-state.db"
        if scratch.exists():
            scratch.unlink()
        conn = db.open_state_db(scratch)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        version = db.schema_version(conn)
        integrity = db.integrity_check(conn)
        conn.close()
        for suffix in ("", "-wal", "-shm"):
            try:
                Path(str(scratch) + suffix).unlink()
            except OSError:
                pass
        add("state_db", mode == "wal" and integrity == "ok", f"schema v{version}, journal {mode}, {integrity}")
    except Exception as exc:  # noqa: BLE001
        add("state_db", False, repr(exc))

    for name in ("tailscale", "policy_proxy", "dnsgate", "job_machine"):
        add(name, False, "not built in this milestone (Phase 1/2)", required=False)

    failures = [check for check in checks if check["required"] and not check["ok"]]
    skipped = [check for check in checks if not check["required"] and not check["ok"]]
    if args.json:
        _print_json({"checks": checks, "ok": not failures, "strict": args.strict})
    else:
        for check in checks:
            if check["ok"]:
                label = "PASS"
            elif check["required"]:
                label = "FAIL"
            else:
                label = "SKIP"
            print(f"[{label}] {check['name']}: {check['detail']}")
        print(
            f"\nPhase 0 doctor: {len(checks) - len(failures) - len(skipped)} passed, "
            f"{len(failures)} failed, {len(skipped)} not built."
        )
    if failures:
        return EXIT_ERROR
    if args.strict and skipped:
        return EXIT_GATE
    return EXIT_OK


def cmd_db_migrate(args: argparse.Namespace) -> int:
    settings = _settings(args).ensure_dirs()
    conn = db.open_state_db(settings.db_path)
    version = db.schema_version(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    if args.json:
        _print_json({"db": str(settings.db_path), "schema": version, "journal_mode": mode})
    else:
        print(f"migrated {settings.db_path} to schema v{version} (journal={mode})")
    return EXIT_OK


def cmd_program_add(args: argparse.Namespace) -> int:
    settings = _settings(args).ensure_dirs()
    handle = args.handle.strip().lower()
    if not handle:
        print("program handle is empty", file=sys.stderr)
        return EXIT_ERROR
    conn = db.open_state_db(settings.db_path)
    try:
        conn.execute(
            "INSERT INTO program(id, handle, platform, created_at, automation_verdict, accounts_allowed) "
            "VALUES (?, ?, ?, ?, 'unknown', 0)",
            (uuid.uuid4().hex, handle, args.platform, _now_iso()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"program {handle!r} already exists", file=sys.stderr)
        return EXIT_ERROR
    finally:
        conn.close()
    if args.json:
        _print_json({"handle": handle, "platform": args.platform})
    else:
        print(f"added {handle} ({args.platform})")
    return EXIT_OK


def cmd_program_list(args: argparse.Namespace) -> int:
    settings = _settings(args).ensure_dirs()
    conn = db.open_state_db(settings.db_path)
    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT handle, platform, automation_verdict, accounts_allowed, created_at "
            "FROM program ORDER BY handle"
        )
    ]
    conn.close()
    if args.json:
        _print_json(rows)
        return EXIT_OK
    if not rows:
        print("no programs")
        return EXIT_OK
    print(f"{'HANDLE':30} {'PLATFORM':12} {'AUTOMATION':10} {'ACCOUNTS':8} CREATED")
    for row in rows:
        accounts = "allowed" if row["accounts_allowed"] else "forbidden"
        print(
            f"{row['handle']:30} {row['platform']:12} {row['automation_verdict']:10} "
            f"{accounts:8} {row['created_at']}"
        )
    return EXIT_OK


def cmd_scope_import(args: argparse.Namespace) -> int:
    policy_text = None
    if args.policy:
        policy_text = Path(args.policy).read_text(encoding="utf-8")
    blocklist_path = args.blocklist
    if blocklist_path is None:
        packaged = Path(__file__).resolve().parents[2] / "config/programs/blocklist.yaml"
        blocklist_path = packaged if packaged.exists() else None
    blocklist = load_blocklist(blocklist_path) if blocklist_path else set()
    accounts_allowed = None
    if args.accounts == "allowed":
        accounts_allowed = True
    elif args.accounts == "forbidden":
        accounts_allowed = False

    revision, summary = import_json_file(
        args.structured_scopes,
        args.handle,
        args.out,
        policy_text=policy_text,
        policy_text_ref=args.policy_ref or args.policy,
        fetched_at=args.fetched_at,
        source=args.source,
        platform=args.platform,
        accounts_allowed=accounts_allowed,
        blocklist=blocklist,
    )
    if args.policy:
        from .scope.policy import classify_policy

        verdict = classify_policy(policy_text)
        print(f"policy: {verdict.verdict.value} ({verdict.explanation})", file=sys.stderr)

    if args.json:
        _print_json({**summary.__dict__, "out": str(args.out)})
    else:
        print(
            f"imported {summary.handle}: {summary.total_assets} assets "
            f"({summary.eligible} eligible, {summary.ineligible} ineligible), "
            f"automation={summary.automation}"
        )
        print(f"revision {revision.revision_hash}")
        print(f"wrote {args.out}")
    return EXIT_OK


def cmd_scope_verify(args: argparse.Namespace) -> int:
    revision = ScopeRevision.from_yaml(args.scope)
    assert revision.verify_hash()
    policy = render_policy(revision)
    if args.json:
        _print_json(
            {
                "handle": revision.handle,
                "revision": revision.revision_hash,
                "assets": len(revision.assets),
                "allows": len(policy["target"]["allows"]),
                "denies": len(policy["deny"]),
                "ports": policy["target"]["ports"],
            }
        )
    else:
        print(f"OK {revision.handle} {revision.revision_hash}")
        print(
            f"assets={len(revision.assets)} allows={len(policy['target']['allows'])} "
            f"denies={len(policy['deny'])} ports={policy['target']['ports']}"
        )
    return EXIT_OK


def cmd_scope_show(args: argparse.Namespace) -> int:
    revision = ScopeRevision.from_yaml(args.scope)
    if args.diff:
        previous = ScopeRevision.from_yaml(args.diff)
        difference = diff_revisions(previous, revision)
        if args.json:
            _print_json(difference.to_dict())
        else:
            print(f"{difference.old_revision} -> {difference.new_revision}")
            if difference.is_empty:
                print("no changes")
            for item in difference.assets_added:
                print(f"+ {item['type']:10} {item['asset']} ({item['id']})")
            for item in difference.assets_removed:
                print(f"- {item['type']:10} {item['asset']} ({item['id']})")
            for item in difference.assets_changed:
                print(f"~ {item['key'][1]} ({item['before']['id']} -> {item['after']['id']})")
            for value in difference.denies_added:
                print(f"+ deny {value}")
            for value in difference.denies_removed:
                print(f"- deny {value}")
            if difference.automation:
                print(f"~ automation {difference.automation[0]} -> {difference.automation[1]}")
            if difference.accounts:
                print(f"~ accounts {difference.accounts[0]} -> {difference.accounts[1]}")
            if difference.ports_added:
                print(f"+ ports {list(difference.ports_added)}")
            if difference.ports_removed:
                print(f"- ports {list(difference.ports_removed)}")
        return EXIT_OK
    if args.json:
        _print_json(revision.to_dict())
    else:
        sys.stdout.write(revision.to_yaml())
    return EXIT_OK


def cmd_scope_explain(args: argparse.Namespace) -> int:
    revision = ScopeRevision.from_yaml(args.scope)
    matcher = ScopeMatcher(revision, allow_private_ips=args.allow_private)
    if args.target.lower().startswith(("http://", "https://")):
        decision = matcher.check_url(args.target)
    else:
        decision = matcher.check_host(args.target, args.port)
    if args.json:
        _print_json(decision.to_dict())
    else:
        verdict = "ALLOW" if decision.allowed else "DENY"
        print(f"{verdict} {args.target}")
        print(f"  reason: {decision.reason} ({decision.detail})")
        print(
            f"  matched asset: {decision.matched_asset or '-'}  "
            f"deny: {decision.matched_deny or '-'}"
        )
        print(
            f"  connect={decision.connect_allowed} request={decision.request_allowed} "
            f"port={decision.port}"
        )
        print(f"  revision: {decision.revision_hash}")
        if decision.constraints:
            print(f"  constraints: {json.dumps(decision.constraints, sort_keys=True)}")
            automation = decision.constraints.get("automation")
            if decision.allowed and automation != "allowed":
                print(
                    f"  note: address/path is in scope, but active verbs are "
                    f"{automation}; passive reconnaissance only"
                )
    return EXIT_OK if decision.allowed else EXIT_GATE


def cmd_scope_render(args: argparse.Namespace) -> int:
    revision = ScopeRevision.from_yaml(args.scope)
    policy = render_policy(revision)
    if args.out:
        Path(args.out).write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        _print_json(policy)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bbguy",
        description="Authorized bug-bounty scope authority (Phase 0/1 build).",
    )
    parser.add_argument("--version", action="version", version=f"bbguy {__version__}")
    parser.add_argument("--home", help="state directory (default: $BBGUY_HOME or ~/.bbguy)")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check local prerequisites")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--strict", action="store_true", help="fail on checks not built yet")
    doctor.set_defaults(func=cmd_doctor)

    db_parser = sub.add_parser("db", help="state database")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_migrate = db_sub.add_parser("migrate", help="create or upgrade the state database")
    db_migrate.add_argument("--db")
    db_migrate.add_argument("--json", action="store_true")
    db_migrate.set_defaults(func=cmd_db_migrate)

    program = sub.add_parser("program", help="program registry")
    program_sub = program.add_subparsers(dest="program_command", required=True)
    add = program_sub.add_parser("add", help="register a program handle")
    add.add_argument("handle")
    add.add_argument("--platform", default="hackerone")
    add.add_argument("--json", action="store_true")
    add.set_defaults(func=cmd_program_add)
    listing = program_sub.add_parser("list", help="list registered programs")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_program_list)

    scope = sub.add_parser("scope", help="signed scope revisions")
    scope_sub = scope.add_subparsers(dest="scope_command", required=True)

    imp = scope_sub.add_parser("import", help="import a structured-scopes export")
    imp.add_argument("--structured-scopes", required=True)
    imp.add_argument("--handle", required=True)
    imp.add_argument("--out", required=True)
    imp.add_argument("--policy")
    imp.add_argument("--policy-ref")
    imp.add_argument("--source")
    imp.add_argument("--fetched-at")
    imp.add_argument("--platform", default="hackerone")
    imp.add_argument("--accounts", choices=("auto", "allowed", "forbidden"), default="auto")
    imp.add_argument("--blocklist", help="YAML file of handles that may not create accounts")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_scope_import)

    verify = scope_sub.add_parser("verify", help="verify a revision hash and render it")
    verify.add_argument("scope")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=cmd_scope_verify)

    show = scope_sub.add_parser("show", help="print a scope revision")
    show.add_argument("scope")
    show.add_argument("--diff", help="print what changed from an earlier revision")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_scope_show)

    explain = scope_sub.add_parser("explain", help="explain a host or URL decision")
    explain.add_argument("scope")
    explain.add_argument("target")
    explain.add_argument("--port", type=int)
    explain.add_argument("--allow-private", action="store_true", help="lab targets only")
    explain.add_argument("--json", action="store_true")
    explain.set_defaults(func=cmd_scope_explain)

    render = scope_sub.add_parser("render", help="render proxy/executor policy as JSON")
    render.add_argument("scope")
    render.add_argument("--out")
    render.set_defaults(func=cmd_scope_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ScopeError, ConfigError, db.MigrationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
