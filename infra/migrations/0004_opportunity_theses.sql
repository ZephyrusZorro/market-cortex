CREATE TABLE opportunity_candidates (
    candidate_id uuid PRIMARY KEY,
    scan_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    symbol text NOT NULL CHECK (symbol IN ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT')),
    detector_id text NOT NULL,
    detector_version text NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('candidate','rejected','insufficient_data','unsupported')),
    status text NOT NULL,
    evidence_hash text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX opportunity_candidates_recent ON opportunity_candidates(recorded_at DESC);
CREATE INDEX opportunity_candidates_ledger ON opportunity_candidates(outcome, symbol, detector_id, recorded_at DESC);

CREATE TABLE research_theses (
    thesis_id uuid PRIMARY KEY,
    original_candidate_id uuid NOT NULL REFERENCES opportunity_candidates(candidate_id),
    symbol text NOT NULL,
    detector_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    current_version integer NOT NULL CHECK (current_version > 0),
    UNIQUE (original_candidate_id)
);
CREATE INDEX research_theses_recent ON research_theses(created_at DESC);

CREATE TABLE research_thesis_versions (
    thesis_id uuid NOT NULL REFERENCES research_theses(thesis_id),
    version integer NOT NULL CHECK (version > 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL CHECK (status IN ('WATCHING','DEVELOPING','AWAITING_CONFIRMATION','VALID',
                                         'NO_EDGE','EVENT_RISK','AVOID','INVALIDATED')),
    manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    candidate_id uuid NOT NULL REFERENCES opportunity_candidates(candidate_id),
    evidence_hash text NOT NULL,
    actor text NOT NULL CHECK (actor IN ('detector','owner')),
    payload jsonb NOT NULL,
    PRIMARY KEY (thesis_id, version)
);
CREATE INDEX research_thesis_versions_recent ON research_thesis_versions(recorded_at DESC);
