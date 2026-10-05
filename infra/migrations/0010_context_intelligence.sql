CREATE TABLE context_facts (
    fact_id uuid PRIMARY KEY,
    logical_key text NOT NULL,
    provider text NOT NULL,
    domain text NOT NULL,
    entity_key text NOT NULL,
    revision integer NOT NULL CHECK(revision > 0),
    available_at timestamptz,
    ingested_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    content_hash text NOT NULL,
    semantic_hash text NOT NULL,
    payload jsonb NOT NULL,
    UNIQUE(provider,logical_key,revision)
);
CREATE INDEX context_visibility ON context_facts(domain,available_at,entity_key);
CREATE TABLE context_files (
    content_hash text PRIMARY KEY,
    relative_path text NOT NULL UNIQUE,
    row_count integer NOT NULL,
    min_event_at timestamptz NOT NULL,
    max_event_at timestamptz NOT NULL,
    venue_id text NOT NULL
);
CREATE TABLE context_manifests (
    manifest_id uuid PRIMARY KEY,
    parent_manifest_id uuid REFERENCES context_manifests(manifest_id),
    created_at timestamptz NOT NULL,
    content_hash text NOT NULL UNIQUE,
    payload jsonb NOT NULL
);
CREATE TABLE context_manifest_facts (
    manifest_id uuid REFERENCES context_manifests(manifest_id),
    fact_id uuid REFERENCES context_facts(fact_id),
    PRIMARY KEY(manifest_id,fact_id)
);
CREATE TABLE context_manifest_files (
    manifest_id uuid REFERENCES context_manifests(manifest_id),
    content_hash text REFERENCES context_files(content_hash),
    PRIMARY KEY(manifest_id,content_hash)
);
CREATE TABLE context_head (singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), manifest_id uuid REFERENCES context_manifests(manifest_id));
CREATE TABLE context_snapshots (
    snapshot_id uuid PRIMARY KEY,
    content_hash text NOT NULL,
    recorded_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
