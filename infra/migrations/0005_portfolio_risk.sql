CREATE TABLE portfolios (
    portfolio_id uuid PRIMARY KEY,
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    base_currency text NOT NULL CHECK (base_currency ~ '^[A-Z]{3,5}$'),
    capital numeric(24,8) NOT NULL CHECK (capital > 0),
    current_version integer NOT NULL DEFAULT 1 CHECK (current_version > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE portfolio_versions (
    portfolio_id uuid NOT NULL REFERENCES portfolios(portfolio_id),
    version integer NOT NULL CHECK (version > 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    action text NOT NULL CHECK (action IN ('created','position_added','position_updated','position_closed')),
    reason text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (portfolio_id, version)
);

CREATE TABLE portfolio_risk_snapshots (
    snapshot_id uuid PRIMARY KEY,
    portfolio_id uuid NOT NULL REFERENCES portfolios(portfolio_id),
    portfolio_version integer NOT NULL,
    manifest_id uuid NOT NULL REFERENCES dataset_manifests(manifest_id),
    as_of timestamptz NOT NULL,
    calculation_version text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    FOREIGN KEY (portfolio_id, portfolio_version) REFERENCES portfolio_versions(portfolio_id, version)
);
CREATE INDEX portfolio_risk_snapshots_recent ON portfolio_risk_snapshots(portfolio_id, recorded_at DESC);
