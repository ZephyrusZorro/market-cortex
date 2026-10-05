CREATE TABLE research_missions (
    mission_id uuid PRIMARY KEY,
    request_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    current_revision integer NOT NULL,
    cancelled boolean NOT NULL DEFAULT false,
    lease_token uuid,
    lease_until timestamptz
);
CREATE TABLE research_mission_checkpoints (
    mission_id uuid NOT NULL REFERENCES research_missions(mission_id),
    revision integer NOT NULL,
    recorded_at timestamptz NOT NULL,
    status text NOT NULL,
    content_hash text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY(mission_id,revision)
);
CREATE INDEX research_mission_history ON research_missions(created_at DESC);
