CREATE TABLE IF NOT EXISTS cortex_research_runs (
    run_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    primary_symbol text,
    evidence_hash text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS cortex_research_runs_recent ON cortex_research_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS cortex_research_runs_symbol_recent ON cortex_research_runs(primary_symbol, created_at DESC);
