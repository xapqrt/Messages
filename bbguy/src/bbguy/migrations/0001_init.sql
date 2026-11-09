-- bbguy schema v1. Money is stored as integer micro-USD, never floating point.
-- Timestamps are ISO-8601 UTC text. Lease clocks are integer nanoseconds from
-- CLOCK_MONOTONIC plus a boot id; they are not wall-clock timestamps.

CREATE TABLE program (
    id                  TEXT PRIMARY KEY,
    handle              TEXT NOT NULL UNIQUE,
    platform            TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    automation_verdict  TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (automation_verdict IN ('allowed','unknown','forbidden')),
    accounts_allowed    INTEGER NOT NULL DEFAULT 0 CHECK (accounts_allowed IN (0,1))
);

CREATE TABLE scope_revision (
    id              TEXT PRIMARY KEY,
    program_id      TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    revision_hash   TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    yaml_blob       TEXT NOT NULL,
    signature       TEXT,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    UNIQUE (program_id, revision_hash)
);

CREATE TABLE scope_asset (
    id                  TEXT PRIMARY KEY,
    scope_revision_id   TEXT NOT NULL REFERENCES scope_revision(id) ON DELETE CASCADE,
    asset               TEXT NOT NULL,
    type                TEXT NOT NULL,
    eligible_for_submission INTEGER NOT NULL CHECK (eligible_for_submission IN (0,1)),
    eligible_for_bounty     INTEGER NOT NULL DEFAULT 0 CHECK (eligible_for_bounty IN (0,1)),
    instruction         TEXT,
    is_deny             INTEGER NOT NULL CHECK (is_deny IN (0,1)),
    UNIQUE (scope_revision_id, asset, type, is_deny)
);

CREATE TABLE run (
    id                  TEXT PRIMARY KEY,
    program_id          TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    scope_revision_id   TEXT REFERENCES scope_revision(id),
    profile             TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    state               TEXT NOT NULL,
    budget_micro_usd    INTEGER NOT NULL DEFAULT 0 CHECK (budget_micro_usd >= 0),
    spend_micro_usd     INTEGER NOT NULL DEFAULT 0 CHECK (spend_micro_usd >= 0)
);

CREATE TABLE run_grant (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    canonical_json  TEXT NOT NULL,
    signature       TEXT NOT NULL,
    issued_at       TEXT NOT NULL,
    not_after       TEXT NOT NULL,
    revoked_at      TEXT
);

CREATE TABLE control_epoch (
    counter         INTEGER PRIMARY KEY,
    incarnation_id  TEXT NOT NULL,
    issued_at       TEXT NOT NULL,
    verified_at     TEXT
);

CREATE TABLE job (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    kind                TEXT NOT NULL,
    target              TEXT,
    objective           TEXT,
    state               TEXT NOT NULL
                        CHECK (state IN ('queued','leased','running','suspect','orphaned',
                                         'delivered','superseded','failed','truncated')),
    lease_id            TEXT,
    lease_seq           INTEGER NOT NULL DEFAULT 0,
    lease_until         TEXT,
    attempts            INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_requests        INTEGER NOT NULL DEFAULT 0 CHECK (max_requests >= 0),
    requests_used       INTEGER NOT NULL DEFAULT 0 CHECK (requests_used >= 0),
    idempotency_class_json TEXT NOT NULL DEFAULT '{}',
    error               TEXT,
    started_at          TEXT,
    finished_at         TEXT,
    last_heartbeat_mono INTEGER,
    boot_id             TEXT
);

CREATE TABLE job_step (
    job_id              TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    attempt             INTEGER NOT NULL,
    step_index          INTEGER NOT NULL,
    verb                TEXT NOT NULL,
    args_hash           TEXT NOT NULL,
    idempotency_class   TEXT NOT NULL,
    state               TEXT NOT NULL,
    result_ref          TEXT,
    attempted_at        TEXT NOT NULL,
    PRIMARY KEY (job_id, attempt, step_index)
);

CREATE TABLE asset (
    id              TEXT PRIMARY KEY,
    program_id      TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,
    canonical       TEXT NOT NULL,
    first_seen_run  TEXT REFERENCES run(id),
    last_seen_run   TEXT REFERENCES run(id),
    state           TEXT NOT NULL DEFAULT 'active',
    attributes_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (program_id, kind, canonical)
);

CREATE TABLE asset_change (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    run_id      TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    change      TEXT NOT NULL
                CHECK (change IN ('new','disappeared','tech_changed','status_changed','cert_changed')),
    prev_json   TEXT,
    new_json    TEXT,
    detected_at TEXT NOT NULL
);

CREATE TABLE service (
    id              TEXT PRIMARY KEY,
    asset_id        TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    port            INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    scheme          TEXT,
    status_code     INTEGER,
    title           TEXT,
    tech_json       TEXT NOT NULL DEFAULT '[]',
    tls_json        TEXT NOT NULL DEFAULT '{}',
    favicon_hash    TEXT,
    waf             TEXT,
    cdn             TEXT,
    screenshot_blob TEXT REFERENCES evidence_blob(sha256),
    last_seen_run   TEXT REFERENCES run(id),
    UNIQUE (asset_id, port, scheme)
);

CREATE TABLE endpoint (
    id              TEXT PRIMARY KEY,
    service_id      TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    params_json     TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL,
    first_seen_run  TEXT REFERENCES run(id),
    UNIQUE (service_id, method, path)
);

CREATE TABLE fixture (
    id          TEXT PRIMARY KEY,
    program_id  TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    identity    TEXT NOT NULL,
    session_ref TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT
);

CREATE TABLE oracle (
    id          TEXT PRIMARY KEY,
    endpoint_id TEXT NOT NULL REFERENCES endpoint(id) ON DELETE CASCADE,
    identity    TEXT NOT NULL,
    object_id   TEXT,
    status      INTEGER,
    length      INTEGER,
    shape_hash  TEXT,
    captured_at TEXT NOT NULL,
    UNIQUE (endpoint_id, identity, object_id)
);

CREATE TABLE hypothesis (
    id                      TEXT PRIMARY KEY,
    program_id              TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    run_id                  TEXT REFERENCES run(id) ON DELETE SET NULL,
    endpoint_id             TEXT REFERENCES endpoint(id) ON DELETE SET NULL,
    vuln_class              TEXT NOT NULL,
    claim                   TEXT NOT NULL,
    state                   TEXT NOT NULL DEFAULT 'open'
                            CHECK (state IN ('open','testing','supported','refuted','inconclusive')),
    kill_condition_json     TEXT NOT NULL DEFAULT '{}',
    predicted_probability   REAL CHECK (predicted_probability IS NULL
                                        OR (predicted_probability >= 0 AND predicted_probability <= 1)),
    cost_requests           INTEGER NOT NULL DEFAULT 0 CHECK (cost_requests >= 0),
    created_at              TEXT NOT NULL
);

CREATE TABLE hypothesis_evidence (
    hypothesis_id   TEXT NOT NULL REFERENCES hypothesis(id) ON DELETE CASCADE,
    stance          TEXT NOT NULL CHECK (stance IN ('for','against')),
    evidence_ref    TEXT NOT NULL,
    note            TEXT,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (hypothesis_id, stance, evidence_ref)
);

CREATE TABLE hypothesis_verdict (
    hypothesis_id   TEXT NOT NULL REFERENCES hypothesis(id) ON DELETE CASCADE,
    battery_id      TEXT NOT NULL,
    passed          INTEGER NOT NULL CHECK (passed IN (0,1)),
    detail_json     TEXT NOT NULL DEFAULT '{}',
    evaluated_at    TEXT NOT NULL,
    PRIMARY KEY (hypothesis_id, battery_id)
);

CREATE TABLE finding (
    id          TEXT PRIMARY KEY,
    program_id  TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    asset_id    TEXT REFERENCES asset(id) ON DELETE SET NULL,
    endpoint_id TEXT REFERENCES endpoint(id) ON DELETE SET NULL,
    vuln_class  TEXT NOT NULL,
    cwe         TEXT,
    severity    TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low','info')),
    title       TEXT NOT NULL,
    confidence  TEXT NOT NULL,
    state       TEXT NOT NULL
                CHECK (state IN ('candidate','reproduced','drafted','submitted','closed')),
    scope_asset_id TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE finding_evidence (
    finding_id  TEXT NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    blob_sha256 TEXT NOT NULL CHECK (length(blob_sha256) = 64),
    kind        TEXT NOT NULL,
    caption     TEXT,
    PRIMARY KEY (finding_id, blob_sha256)
);

CREATE TABLE finding_reproduction (
    finding_id  TEXT PRIMARY KEY REFERENCES finding(id) ON DELETE CASCADE,
    recipe_json TEXT NOT NULL
);

CREATE TABLE evidence_blob (
    sha256      TEXT PRIMARY KEY CHECK (length(sha256) = 64),
    size        INTEGER NOT NULL CHECK (size >= 0),
    kind        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    program_id  TEXT REFERENCES program(id) ON DELETE SET NULL,
    job_id      TEXT,
    expires_at  TEXT
);

CREATE TABLE manifest_head (
    program_id      TEXT NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    job_id          TEXT NOT NULL,
    head_sha256     TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    anchored_at     TEXT NOT NULL,
    PRIMARY KEY (program_id, job_id)
);

CREATE TABLE approval_request (
    id          TEXT PRIMARY KEY,
    finding_id  TEXT NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    report_hash TEXT NOT NULL,
    state       TEXT NOT NULL CHECK (state IN ('pending','approved','rejected')),
    created_at  TEXT NOT NULL,
    decided_at  TEXT
);

CREATE INDEX idx_scope_revision_program ON scope_revision(program_id, active);
CREATE INDEX idx_scope_asset_revision ON scope_asset(scope_revision_id);
CREATE INDEX idx_run_program ON run(program_id, started_at);
CREATE INDEX idx_job_state ON job(state, lease_until);
CREATE INDEX idx_job_run ON job(run_id);
CREATE INDEX idx_asset_program ON asset(program_id, state);
CREATE INDEX idx_asset_change_run ON asset_change(run_id);
CREATE INDEX idx_service_asset ON service(asset_id);
CREATE INDEX idx_endpoint_service ON endpoint(service_id);
CREATE INDEX idx_oracle_endpoint ON oracle(endpoint_id);
CREATE INDEX idx_hypothesis_program ON hypothesis(program_id, state);
CREATE INDEX idx_finding_program ON finding(program_id, state);
CREATE INDEX idx_finding_severity ON finding(severity, state);
CREATE INDEX idx_evidence_expiry ON evidence_blob(expires_at);
CREATE INDEX idx_approval_state ON approval_request(state, created_at);
