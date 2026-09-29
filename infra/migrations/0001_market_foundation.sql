-- PostgreSQL is the authoritative catalog. Artifacts are immutable and addressed
-- by SHA-256. Migration runner serializes application and records the checksum.
CREATE TABLE IF NOT EXISTS venues (
  venue_id text PRIMARY KEY, timezone text NOT NULL, session_kind text NOT NULL,
  document jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS instruments (
  instrument_id uuid PRIMARY KEY, primary_venue_id text NOT NULL REFERENCES venues,
  valid_from timestamptz NOT NULL, valid_to timestamptz,
  document jsonb NOT NULL, CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE TABLE IF NOT EXISTS identifier_mappings (
  mapping_id uuid PRIMARY KEY, instrument_id uuid NOT NULL REFERENCES instruments,
  provider_id text NOT NULL, venue_id text NOT NULL REFERENCES venues,
  identifier_type text NOT NULL, identifier_value text NOT NULL,
  valid_from timestamptz NOT NULL, valid_to timestamptz, available_at timestamptz,
  document jsonb NOT NULL, CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS mapping_lookup ON identifier_mappings
  (provider_id, identifier_type, identifier_value, venue_id, valid_from);
CREATE TABLE IF NOT EXISTS calendar_sessions (
  calendar_id text NOT NULL, session_date date NOT NULL, venue_id text NOT NULL REFERENCES venues,
  version text NOT NULL, document jsonb NOT NULL,
  PRIMARY KEY (calendar_id, session_date, version)
);
CREATE TABLE IF NOT EXISTS provider_capabilities (
  provider_id text NOT NULL, capability_id text NOT NULL, document jsonb NOT NULL,
  PRIMARY KEY (provider_id, capability_id)
);
CREATE TABLE IF NOT EXISTS source_batches (
  source_batch_id uuid PRIMARY KEY, provider_id text NOT NULL,
  fetched_at timestamptz NOT NULL, raw_hash text NOT NULL,
  raw_retention_state text NOT NULL, rights_policy_id text NOT NULL,
  status text NOT NULL, CHECK (raw_hash ~ '^[a-f0-9]{64}$')
);
CREATE TABLE IF NOT EXISTS dataset_manifests (
  manifest_id uuid PRIMARY KEY, parent_manifest_id uuid REFERENCES dataset_manifests,
  created_at timestamptz NOT NULL, schema_version text NOT NULL,
  selection_policy_version text NOT NULL, status text NOT NULL CHECK (status = 'committed')
);
CREATE TABLE IF NOT EXISTS dataset_head (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  manifest_id uuid REFERENCES dataset_manifests
);
INSERT INTO dataset_head(singleton, manifest_id) VALUES (true, NULL) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS dataset_files (
  content_hash text PRIMARY KEY CHECK (content_hash ~ '^[a-f0-9]{64}$'),
  relative_path text NOT NULL, row_count integer NOT NULL CHECK (row_count > 0),
  kind text NOT NULL, venue_id text NOT NULL,
  min_event_at timestamptz NOT NULL, max_event_at timestamptz NOT NULL,
  schema_version text NOT NULL, rights_policy_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS manifest_members (
  manifest_id uuid NOT NULL REFERENCES dataset_manifests, content_hash text NOT NULL REFERENCES dataset_files,
  PRIMARY KEY (manifest_id, content_hash)
);
CREATE TABLE IF NOT EXISTS observations (
  observation_id uuid PRIMARY KEY, fingerprint text UNIQUE NOT NULL,
  logical_key text NOT NULL, revision integer NOT NULL CHECK (revision >= 1),
  supersedes_observation_id uuid REFERENCES observations,
  instrument_id uuid NOT NULL REFERENCES instruments,
  venue_id text NOT NULL REFERENCES venues, provider_id text NOT NULL,
  interval text NOT NULL, start_at timestamptz NOT NULL, end_at timestamptz NOT NULL,
  session_date date NOT NULL, adjustment_basis text NOT NULL,
  available_at timestamptz, availability_basis text NOT NULL,
  quality_state text NOT NULL, source_batch_id uuid NOT NULL REFERENCES source_batches,
  content_hash text NOT NULL REFERENCES dataset_files,
  manifest_id uuid NOT NULL REFERENCES dataset_manifests,
  UNIQUE (logical_key, revision), CHECK (start_at < end_at)
);
CREATE INDEX IF NOT EXISTS observation_history ON observations(logical_key, revision DESC);
CREATE INDEX IF NOT EXISTS observation_time ON observations(instrument_id, end_at, available_at);
CREATE TABLE IF NOT EXISTS quarantine (
  quarantine_id uuid PRIMARY KEY, source_batch_id uuid NOT NULL REFERENCES source_batches,
  provider_id text NOT NULL, instrument_id uuid, reason_codes text[] NOT NULL,
  raw_hash text NOT NULL, recorded_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id uuid PRIMARY KEY, kind text NOT NULL, idempotency_key text UNIQUE NOT NULL,
  state text NOT NULL, attempts integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz NOT NULL, lease_until timestamptz,
  payload jsonb NOT NULL, error_code text
);
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(state, next_attempt_at);
CREATE TABLE IF NOT EXISTS outbox (
  event_id uuid PRIMARY KEY, event_type text NOT NULL, schema_version text NOT NULL,
  occurred_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL,
  aggregate_id text NOT NULL, correlation_id uuid NOT NULL,
  idempotency_key text UNIQUE NOT NULL, payload_ref text NOT NULL,
  delivered_at timestamptz
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(recorded_at) WHERE delivered_at IS NULL;
