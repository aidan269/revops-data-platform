-- AUTOMATION-DIGITAL-TWIN — canonical, vendor-neutral automation graph.
--
-- SCOPE: local warehouse only. Nothing in this schema creates, modifies, or
-- deletes a record in HubSpot, Apollo, Zapier, or any other external system.
--
-- CONTRACT, enforced by constraint below:
--   Stored evidence NEVER authorizes an external write. Every table that can
--   describe a mutation carries authorizes_external_write BOOLEAN NOT NULL
--   DEFAULT false with a CHECK pinning it to false. The only table permitted to
--   carry a true value is raw.automation_approvals, and only once a human
--   approver and an immutable request hash are both present.
--
-- Collection honesty: a surface that could not be collected is recorded as
-- NOT_COLLECTED with a reason. A zero-row inventory must never be presented as
-- a healthy baseline; see analytics.automation_baseline_coverage.

-- ---------------------------------------------------------------------------
-- Source snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_source_snapshots (
    snapshot_id            TEXT        PRIMARY KEY,
    source_system          TEXT        NOT NULL,   -- hubspot | apollo | zapier | forms | warehouse | ledger
    workspace_identifier   TEXT,                   -- portal / team / account id
    collected_at           TIMESTAMPTZ NOT NULL,
    collector              TEXT        NOT NULL,   -- mcp | browser_report | repository_artifact | warehouse
    source_artifact        TEXT        NOT NULL,
    source_hash            TEXT,
    collection_status      TEXT        NOT NULL,   -- COLLECTED | PARTIAL | NOT_COLLECTED
    baseline_established   BOOLEAN     NOT NULL DEFAULT false,
    not_collected_reason   TEXT,
    imported_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT ads_status_ck CHECK (collection_status IN ('COLLECTED','PARTIAL','NOT_COLLECTED')),
    CONSTRAINT ads_no_write_ck CHECK (authorizes_external_write = false),
    -- an uncollected surface may never claim a baseline
    CONSTRAINT ads_baseline_honesty_ck CHECK (
        NOT (collection_status = 'NOT_COLLECTED' AND baseline_established = true)
    ),
    CONSTRAINT ads_reason_required_ck CHECK (
        collection_status <> 'NOT_COLLECTED' OR not_collected_reason IS NOT NULL
    )
);

-- ---------------------------------------------------------------------------
-- Assets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_assets (
    asset_id               TEXT        PRIMARY KEY,
    snapshot_id            TEXT        NOT NULL REFERENCES raw.automation_source_snapshots(snapshot_id),
    source_system          TEXT        NOT NULL,
    native_id              TEXT,
    name                   TEXT,
    asset_type             TEXT        NOT NULL,   -- workflow | zap | form | list | sequence | import | property | owner | integration
    object_type            TEXT,
    state                  TEXT        NOT NULL,   -- active | off | draft | unknown
    owner_identity         TEXT,
    evidence_state         TEXT        NOT NULL,   -- COLLECTED | PARTIAL | NOT_COLLECTED
    first_observed         TIMESTAMPTZ,
    last_observed          TIMESTAMPTZ,
    raw_definition_ref     TEXT,
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT aa_state_ck CHECK (state IN ('active','off','draft','unknown')),
    CONSTRAINT aa_evidence_ck CHECK (evidence_state IN ('COLLECTED','PARTIAL','NOT_COLLECTED')),
    CONSTRAINT aa_no_write_ck CHECK (authorizes_external_write = false)
);
CREATE INDEX IF NOT EXISTS idx_aa_system ON raw.automation_assets (source_system, asset_type);

-- ---------------------------------------------------------------------------
-- Nodes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_nodes (
    node_id                TEXT        PRIMARY KEY,
    asset_id               TEXT        NOT NULL REFERENCES raw.automation_assets(asset_id),
    node_type              TEXT        NOT NULL,   -- trigger|filter|branch|delay|lookup|transform|create|update|associate|notify|error|approval
    operation              TEXT,
    object_type            TEXT,
    classification         TEXT        NOT NULL,   -- trigger|action|condition|delay|error|approval
    config                 JSONB       NOT NULL DEFAULT '{}'::jsonb,
    basis                  TEXT        NOT NULL,   -- observed | inferred
    write_capability       BOOLEAN     NOT NULL DEFAULT false,
    external_side_effect   TEXT        NOT NULL,   -- none | crm_write | email | slack | unknown
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT an_basis_ck CHECK (basis IN ('observed','inferred')),
    CONSTRAINT an_class_ck CHECK (classification IN ('trigger','action','condition','delay','error','approval')),
    CONSTRAINT an_no_write_ck CHECK (authorizes_external_write = false)
);
CREATE INDEX IF NOT EXISTS idx_an_asset ON raw.automation_nodes (asset_id);

-- ---------------------------------------------------------------------------
-- Edges
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_edges (
    edge_id                TEXT        PRIMARY KEY,
    asset_id               TEXT        NOT NULL REFERENCES raw.automation_assets(asset_id),
    source_node_id         TEXT,
    target_node_id         TEXT,
    source_ref             TEXT,       -- used when an endpoint is not an inventoried node
    target_ref             TEXT,
    branch_condition       TEXT,
    path_type              TEXT        NOT NULL,   -- normal | failure | fallback | timeout
    basis                  TEXT        NOT NULL,   -- observed | inferred
    evidence_reference     TEXT,
    endpoints_resolved     BOOLEAN     NOT NULL DEFAULT false,
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT ae_path_ck CHECK (path_type IN ('normal','failure','fallback','timeout')),
    CONSTRAINT ae_basis_ck CHECK (basis IN ('observed','inferred')),
    CONSTRAINT ae_no_write_ck CHECK (authorizes_external_write = false)
);
CREATE INDEX IF NOT EXISTS idx_ae_asset ON raw.automation_edges (asset_id);

-- ---------------------------------------------------------------------------
-- Field access
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_field_access (
    access_id              TEXT        PRIMARY KEY,
    asset_id               TEXT        NOT NULL REFERENCES raw.automation_assets(asset_id),
    node_id                TEXT        REFERENCES raw.automation_nodes(node_id),
    system                 TEXT        NOT NULL,
    object_type            TEXT        NOT NULL,
    property_name          TEXT        NOT NULL,
    operation              TEXT        NOT NULL,   -- read | write | create | clear | associate
    overwrite_behavior     TEXT,                   -- replace | only_if_empty | never | unknown
    conditional_behavior   TEXT,
    basis                  TEXT        NOT NULL,   -- observed | inferred
    confidence             TEXT        NOT NULL,   -- high | medium | low
    evidence_reference     TEXT,
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT afa_op_ck CHECK (operation IN ('read','write','create','clear','associate')),
    CONSTRAINT afa_basis_ck CHECK (basis IN ('observed','inferred')),
    CONSTRAINT afa_no_write_ck CHECK (authorizes_external_write = false)
);
CREATE INDEX IF NOT EXISTS idx_afa_prop ON raw.automation_field_access (system, object_type, property_name);

-- ---------------------------------------------------------------------------
-- Runs. Simulated and observed executions are never conflated.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_runs (
    run_id                 TEXT        PRIMARY KEY,
    asset_id               TEXT        REFERENCES raw.automation_assets(asset_id),
    run_kind               TEXT        NOT NULL,   -- simulation | observed
    fixture_name           TEXT,
    input_fixture_hash     TEXT,
    result                 TEXT        NOT NULL,   -- completed | stopped_safe | policy_blocked | cannot_evaluate
    traversed_nodes        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    proposed_writes        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    blocked_writes         JSONB       NOT NULL DEFAULT '[]'::jsonb,
    findings               JSONB       NOT NULL DEFAULT '[]'::jsonb,
    ledger_reference       TEXT,
    executed_externally    BOOLEAN     NOT NULL DEFAULT false,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT ar_kind_ck CHECK (run_kind IN ('simulation','observed')),
    CONSTRAINT ar_no_write_ck CHECK (authorizes_external_write = false),
    -- a simulation can never be recorded as having executed externally
    CONSTRAINT ar_sim_never_executed_ck CHECK (
        NOT (run_kind = 'simulation' AND executed_externally = true)
    )
);

-- ---------------------------------------------------------------------------
-- Findings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_findings (
    finding_id             TEXT        PRIMARY KEY,
    policy_id              TEXT        NOT NULL,
    severity               TEXT        NOT NULL,   -- P0 | P1 | P2 | P3
    asset_id               TEXT        REFERENCES raw.automation_assets(asset_id),
    system                 TEXT,
    object_type            TEXT,
    property_name          TEXT,
    observation            TEXT        NOT NULL,
    inference              TEXT,                   -- deliberately separate from observation
    evidence_reference     TEXT,
    recurrence_risk        TEXT,
    reversibility          TEXT,
    proposed_remediation   TEXT,
    approval_required      BOOLEAN     NOT NULL DEFAULT true,
    detected_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    CONSTRAINT af_sev_ck CHECK (severity IN ('P0','P1','P2','P3')),
    CONSTRAINT af_no_write_ck CHECK (authorizes_external_write = false)
);

-- ---------------------------------------------------------------------------
-- Approvals. The ONLY table where authorizes_external_write may become true,
-- and only with a named approver and an immutable request hash.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.automation_approvals (
    proposal_id            TEXT        PRIMARY KEY,
    target_system          TEXT        NOT NULL,
    asset_id               TEXT,
    object_type            TEXT,
    record_ids             JSONB       NOT NULL DEFAULT '[]'::jsonb,
    fields                 JSONB       NOT NULL DEFAULT '[]'::jsonb,
    old_values             JSONB       NOT NULL DEFAULT '{}'::jsonb,
    proposed_values        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    reason                 TEXT        NOT NULL,
    rollback_plan          TEXT        NOT NULL,
    idempotency_key        TEXT        NOT NULL,
    request_hash           TEXT        NOT NULL,
    approver               TEXT,
    approved_at            TIMESTAMPTZ,
    execution_status       TEXT        NOT NULL DEFAULT 'PENDING_APPROVAL',
    authorizes_external_write BOOLEAN  NOT NULL DEFAULT false,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT aap_status_ck CHECK (execution_status IN
        ('PENDING_APPROVAL','APPROVED','REJECTED','EXECUTED','ROLLED_BACK')),
    -- authorization requires a human approver AND a timestamp. Never implicit.
    CONSTRAINT aap_auth_requires_human_ck CHECK (
        authorizes_external_write = false
        OR (approver IS NOT NULL AND approved_at IS NOT NULL AND execution_status = 'APPROVED')
    )
);

COMMENT ON TABLE raw.automation_source_snapshots IS
    'Provenance for every evidence import. NOT_COLLECTED surfaces can never claim baseline_established.';
COMMENT ON TABLE raw.automation_approvals IS
    'Only table permitted to carry authorizes_external_write = true, and only with a named approver.';
COMMENT ON COLUMN raw.automation_findings.inference IS
    'Kept separate from observation by design. Never merge the two columns.';
