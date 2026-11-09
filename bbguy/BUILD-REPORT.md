# Build report — bbguy Phase 0/1

Date: 2026-11-09
Base commit: `e1c8e2a464642d669dba77a27276875baafe2e64`
Branch: `arena/a73aa21b-messages`
Environment: Python 3.11.2, SQLite 3.40.1, idna 3.20, PyYAML 6.0.3, pytest 9.2.0

This report is deliberately a gate report, not a feature list. The PRD is the
contract; §18 defines the phases, and a phase that touches I/O may not pass on a
unit test. Phase 0 is pure logic (plus local SQLite), so its test file is the
demonstration. Phase 1's live gate is not met, and says so below.

---

## 1. Phase 0 — Foundations

PRD §18 Phase 0: "Repo skeleton, `pyproject.toml`, settings, schema and
migrations, `scope/matching.py`, adversarial test file."

| Deliverable | State | Where |
|---|---|---|
| Repo skeleton | Done | `bbguy/pyproject.toml`, `src/bbguy/`, `tests/` |
| Settings | Done | `src/bbguy/config.py` (`BBGUY_HOME`, disk floor, 0700 dirs) |
| Schema and migrations | Done | `src/bbguy/migrations/0001_init.sql`, `src/bbguy/db.py` |
| Scope matching | Done | `src/bbguy/scope/canonical.py`, `models.py`, `matching.py` |
| Adversarial test file | Done, 234 cases | `tests/scope/test_adversarial.py` |
| Clock (`CLOCK_MONOTONIC`, boot id) | Done | `src/bbguy/clock.py` |
| Minimal CLI / doctor | Done | `src/bbguy/cli.py` |

### Gate command

```bash
cd bbguy
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest -q tests/scope
coverage run -m pytest -q && coverage report -m
bbguy doctor
```

### Gate result: **PASS for the local Phase 0 definition**

Observed:

```text
pytest -q                 -> 453 passed
adversarial cases         -> 234  (PRD asks 200+)
scope/matching.py         -> 228 statements, 0 missed, 99% line coverage
                             (PRD N8 asks >= 95%)
scope/canonical.py        -> 95% line coverage
TOTAL                     -> 1459 statements, 85% line coverage
```

What the tests actually cover:

- Exact, wildcard and longest-wildcard matching; apex exclusion and explicit
  `include_apex`; suffix-boundary negatives (`evilacme.example`,
  `acme.example.evil.com`).
- Ineligible rows retained as denies, including an ineligible wildcard nested
  under an eligible wildcard; deny wins over a more specific allow.
- URL prefix matching on segment boundaries (`/api/v2` vs `/api/v20`), dot-segment
  resolution, double-slash collapse, encoded separators (`%2f`, `%5c`,
  double-encoded), query strings, scheme and port binding.
- IPv4/IPv6 allowlists and CIDRs; rejection of loopback, link-local, RFC1918,
  CGNAT `100.64/10`, multicast, unspecified and Tailscale ULA addresses.
- Alternate numeric spellings (`2130706433`, `0x7f000001`, `017700000001`,
  `127.1`, `1.2.3.999`) and IDNA/homograph handling.
- Revision hash tamper detection; YAML round trip; edited YAML refused.
- SQLite: all 23 data-model tables, WAL, foreign keys, idempotent migration,
  edited-migration refusal, rollback of a failed migration, cascade behaviour.
- Clock advance across sleep; boot id stability; secret-free child environment.
- Every implemented CLI command, including deny exit code `2` and hash-tamper
  exit `1`.

### Reviewer break attempt (self-review)

The PRD asks a reviewer to attempt to break `host_match` and document it. The
adversarial suite is that attempt in executable form. The classes tried:

| Attempt | Result |
|---|---|
| `evilacme.example` against `*.acme.example` | denied, boundary check |
| `acme.example.evil.com` | denied, suffix check |
| `user@acme.example`, `acme.example:443` | invalid host, denied |
| `2130706433`, `0x7f000001`, `127.1` | invalid/ambiguous host, denied |
| `%2f`, `%252f`, `%5c`, `..`, `//` in a URL path | rejected or normalised before prefix comparison |
| `portal.example.net.evil.com` | no matching asset |
| ineligible child under eligible wildcard | deny by asset id |
| in-scope name resolving to `169.254.169.254` | private/reserved deny |
| edit a signed revision | hash mismatch, matcher refuses to construct |
| port 22 on an allowed host | denied by signed port list |

No bypass was found in this suite. **A second human reviewer has not yet done
this exercise**; that remains part of the gate as written, and this report does
not claim it.

### Known limits of the Phase 0 claim

- The SHA-256 revision hash detects accidental or casual edits. It is **not a
  signature**. Anyone who can write the file can recompute the hash. Ed25519
  signing/verification is a Phase 2 item (PRD §7.6, deliverable "signed grants" /
  Architecture v2's off-VPS signing key).
- `scope explain` and the future executor share `ScopeMatcher`; no executor
  exists yet to prove the shared-function claim end to end.
- The DB migration was exercised on SQLite 3.40 on Linux. `fullfsync` and
  `checkpoint_fullfsync` are issued, but their macOS effect was not measured
  here. That measurement belongs to the Mac control-plane gate.

---

## 2. Phase 1 — Scope intake

PRD §18 Phase 1: "HackerOne importer preserving every asset type and
eligibility, policy fetch and verdict extraction, per-asset instructions,
rendering to proxy and executor config."

| Deliverable | State | Where |
|---|---|---|
| Structured-scope importer | Implemented against a fixture; **live API not exercised** | `src/bbguy/scope/importer.py` |
| Every asset type + eligibility retained | Done + tested | `tests/scope/test_importer.py` |
| Ineligible rows become denies | Done + tested | `importer.build_revision` |
| Per-asset instruction retained | Done + tested | `Asset.instruction`, `automation_for` |
| Policy verdict extraction | Implemented, conservative; human confirmation still required | `src/bbguy/scope/policy.py` |
| Rendering to proxy/executor config | Done + tested | `src/bbguy/scope/render.py` |
| Scope diff | Done + tested | `src/bbguy/scope/diff.py`, `scope show --diff` |
| Real public program imported | **Not done** | blocked, see §2.1 |

### 2.1 Why the Phase 1 gate is not met

The gate is: a real public program imports; `scope show --diff` lists in-scope
assets and explicitly denies the ineligible assets; the rendered config denies
them.

The importer can do the last two on a fixture, and the CLI demonstrates it. The
first clause needs:

1. a HackerOne API token with access to the program's structured scopes;
2. the exact live field set, which PRD §21 open question 6 marks **[verify]**;
3. the program's policy page and a human confirmation of the automation verdict.

None is available in this environment. The importer accepts both the documented
`{"data":[{"attributes":{...}}]}` shape and a flat list, but **that shape has not
been verified against the live API**. Treat a live import as the first task of
the next session, not as already proven.

The policy classifier is also advisory by design. It returns `allowed`,
`unknown` or `forbidden` with the sentences that decided it, and a human must
confirm the verdict per program (PRD §11.1). A silent policy yields `unknown`,
which denies active verbs.

---

## 3. Deliberate deviations and decisions

| Decision | Why | Risk |
|---|---|---|
| Python target `>=3.11` while the PRD job machine is 3.12 | Local environment is 3.11; code uses no 3.12-only syntax | Low; CI should pin 3.12 |
| Money columns are `budget_micro_usd` / `spend_micro_usd` | Floating-point USD is not acceptable for budgets | Column names differ from PRD §10 |
| Added `source_code` asset type | Architecture v2 / real scopes include it; it must be recorded but never targeted | None; render excludes it |
| Accounts default **allowed** when automation is allowed (PRD D7) | PRD precedence over Architecture v2's "forbidden by default"; D8 still makes them ineffective when automation is `unknown` or `forbidden`; blocklist vetoes | Recorded in `accounts_allowed`; a live program policy still needs review |
| Private/reserved IP deny on by default | PRD §9.3; `--allow-private` is lab-only | A legitimate private-range scope needs the explicit flag |
| `scope explain` exits `2` on deny | Makes it usable as a gate | Documented; not a POSIX convention |
| No `run`/`proof`/`pack` commands | A command that cannot reach a target is the Horizon failure mode | None for Phase 0/1 |
| `signature` is carried, not verified | Ed25519 key management is Phase 2 | **Scope integrity is tamper-evident, not authenticated** |
| `scope import` defaults to the packaged blocklist | PRD §12.5 wants a seeded blocklist | The file is empty until real handles are added |

---

## 4. What this build does not claim

- No live target was contacted. No request left this machine.
- No HackerOne token exists in the tree or the database. There is no submit path.
- No proxy, `dnsgate`, WireGuard, InstaBox machine, recon verb, LLM call, grant,
  lease, proof battery, dashboard or evidence encryption exists yet.
- Phase 2's containment gate, Phase 3's lab recon gate and Phase 4's public-program
  gate are untouched.
- The PRD §18 Phase 0 clause "a reviewer attempts to break `host_match`" has an
  executable attempt but not an independent human reviewer.

---

## 5. Next work, in PRD order

1. **Finish Phase 1 live import.** Obtain a token and one redacted real export;
   diff the assumed fields against it; add the missing mapping; record the policy
   verdict with a human signature. Only then claim the Phase 1 gate.
2. **Add Ed25519 scope signing/verification** before any job machine exists
   (Phase 2 prerequisite). The verify key belongs on the worker; the signing key
   never leaves the owner's machine.
3. **Phase 2 containment.** Scope proxy, `dnsgate`, selfcheck, `curl 1.1.1.1`
   `ENETUNREACH`, mTLS, grants, leases, the chaos matrix. None of this can be
   meaningfully built in this sandbox.
4. **Then** recon, proof bundles and the human handoff.

## 6. Open questions inherited from PRD §21

These do not block Phase 0/1 code, but they block the next gates:

- InstaBox acceptable use for automated scanning (before Phase 2).
- Tailscale enrolment and node-key expiry (before Phase 2).
- First public program and its automation/AI policy (before Phase 3/4).
- HackerOne structured-scope field set (before the Phase 1 gate closes).
- Search API keys and email aliases (Phase 3/6).
- Severity model: CVSS v3.1, v4.0 or HackerOne's scale (proof/pack phase).
- Browser disk reserve measurement (if headless crawl is ever enabled).
- Where the Mac parses hostile evidence/policy HTML (Phase 7).
