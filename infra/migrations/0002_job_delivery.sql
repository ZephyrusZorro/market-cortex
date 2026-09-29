CREATE TABLE IF NOT EXISTS consumer_receipts (
  consumer_id text NOT NULL, event_id uuid NOT NULL REFERENCES outbox,
  processed_at timestamptz NOT NULL, PRIMARY KEY (consumer_id, event_id)
);
CREATE TABLE IF NOT EXISTS app_locks (
  lock_name text PRIMARY KEY, holder uuid, lease_until timestamptz
);
