CREATE TABLE quant_artifacts (
    artifact_id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('source','run','sensitivity','walk_forward','robustness','monte_carlo','comparison')),
    content_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    UNIQUE(kind,content_hash)
);
CREATE INDEX quant_recent ON quant_artifacts(kind,created_at DESC);
CREATE TABLE quant_edge_evidence (
    edge_id uuid NOT NULL REFERENCES edge_library(edge_id),
    revision integer NOT NULL CHECK(revision>0),
    recorded_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY(edge_id,revision)
);
