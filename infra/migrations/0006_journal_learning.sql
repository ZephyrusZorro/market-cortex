CREATE TABLE journal_entries (
    entry_id uuid PRIMARY KEY,
    current_revision integer NOT NULL CHECK (current_revision > 0),
    created_at timestamptz NOT NULL
);
CREATE TABLE journal_revisions (
    entry_id uuid NOT NULL REFERENCES journal_entries(entry_id),
    revision integer NOT NULL CHECK (revision > 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (entry_id, revision)
);
CREATE TABLE prediction_records (
    prediction_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    source_manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    registration text NOT NULL CHECK (registration IN ('PRE_REGISTERED','RETROSPECTIVE_EVALUATION')),
    original_context_hash text NOT NULL,
    payload jsonb NOT NULL,
    current_revision integer NOT NULL CHECK (current_revision > 0)
);
CREATE TABLE prediction_revisions (
    prediction_id uuid NOT NULL REFERENCES prediction_records(prediction_id),
    revision integer NOT NULL CHECK (revision > 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL,
    reason text NOT NULL,
    evaluation_id uuid,
    PRIMARY KEY (prediction_id, revision)
);
CREATE TABLE prediction_evaluations (
    evaluation_id uuid PRIMARY KEY,
    prediction_id uuid NOT NULL REFERENCES prediction_records(prediction_id),
    evaluation_manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    evaluated_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
ALTER TABLE prediction_revisions ADD FOREIGN KEY (evaluation_id) REFERENCES prediction_evaluations(evaluation_id);
CREATE INDEX prediction_due ON prediction_records(created_at);
CREATE INDEX evaluation_prediction ON prediction_evaluations(prediction_id, evaluated_at);
CREATE TABLE edge_library (
    edge_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
