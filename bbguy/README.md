# bbguy — Phase 0/1 build

A self-hosted, authorized bug-bounty scope authority and recon ledger. This
checkout implements the part of PRD v3 that can be proven without a target:
**Phase 0 (scope core, schema, clock, skeleton)** and the pure-logic half of
**Phase 1 (structured-scope intake, policy verdict, rendering and diff)**.

It is **not** the full system described in PRD §1. There is no recon, no proxy,
no `dnsgate`, no InstaBox machine, no LLM, no proof bundle, no dashboard and no
submission path. No code here makes a network request. The only command that
touches a target is a pure function that decides whether a target *would* be
allowed.

> The PRD's anti-Horizon rule governs this build: a component that cannot be
> demonstrated is not done. The scope core is demonstrated by its test suite.
> The live HackerOne import is not, because no credentialed export is available
> in this environment.

## Quick start

```bash
cd bbguy
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

pytest -q
coverage run -m pytest -q && coverage report -m

bbguy doctor
```

`bbguy doctor` exits non-zero on a required Phase 0 failure and prints the
Phase 1/2 components as `[SKIP] not built`. `--strict` turns those skips into a
non-zero exit, which is the honest CI setting until Phase 1 lands.

## Try the scope core

```bash
bbguy --home .bbguy scope import \
  --structured-scopes fixtures/hackerone_acme_structured_scopes.json \
  --handle acme \
  --out .bbguy/scope/acme.yaml \
  --policy fixtures/policy_acme.txt \
  --policy-ref policy_acme.txt \
  --fetched-at 2026-11-09T18:00:00Z \
  --source fixture://acme

bbguy --home .bbguy scope verify .bbguy/scope/acme.yaml
bbguy --home .bbguy scope explain .bbguy/scope/acme.yaml \
  https://portal.example.net/api/v2/accounts/1       # exit 0, ALLOW
bbguy --home .bbguy scope explain .bbguy/scope/acme.yaml \
  x.stg.acme.example                                  # exit 2, DENY
bbguy --home .bbguy scope show .bbguy/scope/acme.yaml \
  --diff .bbguy/scope/acme.yaml                       # no changes
bbguy --home .bbguy scope render .bbguy/scope/acme.yaml --out policy.json
```

A deny exits `2`, an internal error exits `1`, and an allow exits `0`, so
`scope explain` can be used directly as a deployment gate. An `ALLOW` means the
host and path matched the signed scope; the printed constraints still decide
whether active verbs may run. The fixture API asset carries a prose instruction,
so its `automation` is `unknown` and the explanation prints "passive
reconnaissance only" until a human classifies it.

## Scope semantics that are enforced

- **Every export row is retained.** `eligible_for_submission: false` becomes a
  deny; it is never filtered out. A wildcard allow with an ineligible child
  denies the child (tested by id).
- **Canonicalisation is one function.** Lowercase, exactly one trailing dot
  stripped, IDNA/UTS-46, label and total-length checks, IPv4/IPv6 literals
  parsed, and alternate numeric spellings (`2130706433`, `0x7f000001`, `127.1`,
  `1.2.3.999`) rejected rather than treated as DNS names.
- **Wildcards are label-boundary aware.** `*.acme.example` matches
  `a.acme.example` and `a.b.acme.example`, never `evilacme.example` or
  `acme.example.evil.com`. The apex is not implicit; `include_apex` is explicit.
- **URL assets are path-scoped.** `/api/v2` matches `/api/v2/x`, not `/api/v20`.
  Paths are decoded exactly once, `//` and dot segments are collapsed, and
  encoded separators (`%2f`, `%5c`, double-encoded) are rejected.
- **Deny wins.** A deny matches before any allow, regardless of specificity.
- **Private and reserved addresses are denied by default**, including loopback,
  link-local (`169.254.169.254`), RFC1918, CGNAT `100.64/10`, multicast and the
  Tailscale ULA. `--allow-private` exists only for a lab target.
- **Ports are signed.** A port outside the revision's list is denied even when
  the host matches.
- **Prose does not grant permission.** An asset with an `instruction` but no
  human-classified `constraints.automation` reports `automation: unknown`, which
  turns every active verb off. A program-level verdict of `allowed` does not
  overrule that. Accounts follow the same rule: they are effectively forbidden
  until automation is permitted for that asset.
- **Edits are detectable.** The revision hash covers every asset, deny, port,
  policy digest and verdict. Loading an edited YAML fails with
  `revision hash mismatch`. Ed25519 signing and verification are Phase 2; the
  `signature` field is carried but not trusted.
- **`source_code` and `other` assets never become allowlist entries.** A GitHub
  URL in scope is recorded for source review, not turned into a host to scan.

## Commands implemented

| Command | Purpose |
|---|---|
| `bbguy doctor [--json] [--strict]` | Python/SQLite/idna/clock/disk/state-DB checks |
| `bbguy db migrate [--db PATH]` | Create or upgrade `state.db` |
| `bbguy program add/list` | Program registry in SQLite |
| `bbguy scope import` | Structured-scopes JSON → signed-by-hash revision YAML |
| `bbguy scope verify` | Verify the revision hash and render counts |
| `bbguy scope show [--diff FILE]` | Print a revision, or what changed |
| `bbguy scope explain FILE TARGET` | The same decision function the executor uses |
| `bbguy scope render FILE --out PATH` | Proxy/executor allow/deny JSON |

Not implemented on purpose: `run`, `job`, `proof`, `pack`, `triage`, `gc`.
Adding a command that cannot reach a real target would repeat the failure mode
the PRD was written to prevent.

## Evidence

```text
$ pytest -q
453 passed

$ coverage report -m
src/bbguy/scope/matching.py   228 statements   0 missed   99% line
TOTAL                         1459 statements   ...        85% line
```

- **453 tests**, of which **234 are adversarial scope cases** (the PRD Phase 0
  gate asks for 200+).
- `scope/matching.py` is at **99% line coverage**, above the PRD's N8 95%
  requirement for scope matching.
- The DB suite covers all 23 Phase 1 tables, WAL, foreign keys, idempotent
  migration, edited-migration refusal and rollback of a failed migration.
- The CLI suite exercises every implemented command, including deny exit codes
  and hash-tamper refusal.

Run it yourself; the numbers are not a claim in a document.

## Layout

```text
bbguy/
├── pyproject.toml
├── README.md
├── BUILD-REPORT.md            # PRD phase mapping and the gates that are/aren't met
├── config/programs/blocklist.yaml
├── fixtures/                  # HackerOne-shaped export + policy text
├── src/bbguy/
│   ├── cli.py
│   ├── clock.py               # C CLOCK_MONOTONIC + boot id
│   ├── config.py
│   ├── db.py                  # WAL/fullfsync + versioned migrations
│   ├── migrations/0001_init.sql
│   └── scope/
│       ├── canonical.py       # host / path / URL normalisation
│       ├── models.py          # signed revision, assets, denies, validation
│       ├── matching.py        # the only decision function
│       ├── policy.py          # policy prose → allowed/unknown/forbidden
│       ├── importer.py        # structured scopes → revision; keeps denies
│       ├── render.py          # revision → proxy/executor config
│       └── diff.py            # revision-to-revision diff
└── tests/
```

## Safety

- No network calls, no HackerOne token, no submission code path.
- No credentials are read from the environment or written to the database.
- `bbguy doctor` and all tests operate on a temporary `BBGUY_HOME`.
- `scope import` never widens scope: eligibility is required to be a JSON
  boolean and missing eligibility fails closed to `false`.

## Next gates

Phase 1's gate is **not** met: it requires a real public program imported from
the live structured-scopes API, with `scope show --diff` naming the explicit
denies. That needs a HackerOne API token and a verified field set (PRD §21,
open question 6), neither of which is available here. See `BUILD-REPORT.md` for
the exact blocker and the next step.
