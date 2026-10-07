CREATE TABLE personal_records (
    record_id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('MEMORY','PROPOSAL','FEEDBACK','ATTESTATION')),
    audience text NOT NULL CHECK (audience IN ('OWNER_RESEARCH','SYNTHETIC_VALIDATION')),
    dedup_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    current_version integer NOT NULL CHECK (current_version > 0),
    UNIQUE(kind,audience,dedup_key)
);
CREATE TABLE personal_record_versions (
    record_id uuid NOT NULL REFERENCES personal_records(record_id),
    version integer NOT NULL CHECK (version > 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    content_hash text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY(record_id,version)
);
CREATE INDEX personal_record_history ON personal_record_versions(recorded_at);
CREATE TABLE personalization_snapshots (
    snapshot_id uuid PRIMARY KEY,
    audience text NOT NULL,
    as_of timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    content_hash text NOT NULL,
    payload jsonb NOT NULL
);
