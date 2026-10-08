-- Derived artifacts reuse the Quant Lab content-addressed JSON store and backup.
ALTER TABLE quant_artifacts DROP CONSTRAINT quant_artifacts_kind_check;
ALTER TABLE quant_artifacts ADD CONSTRAINT quant_artifacts_kind_check CHECK
 (kind IN ('source','run','sensitivity','walk_forward','robustness','monte_carlo','comparison',
          'experiment_dataset','experiment_model','experiment_result','experiment_analogue','experiment_dossier','experiment_comparison'));
CREATE TABLE research_hypotheses (
 hypothesis_id uuid PRIMARY KEY, content_hash text UNIQUE NOT NULL, recorded_at timestamptz NOT NULL,
 payload jsonb NOT NULL
);
CREATE TABLE experiment_definitions (
 experiment_id uuid PRIMARY KEY, hypothesis_id uuid NOT NULL REFERENCES research_hypotheses,
 content_hash text UNIQUE NOT NULL, recorded_at timestamptz NOT NULL, payload jsonb NOT NULL
);
CREATE TABLE experiment_events (
 experiment_id uuid NOT NULL REFERENCES experiment_definitions, revision integer NOT NULL,
 recorded_at timestamptz NOT NULL, status text NOT NULL CHECK(status IN
 ('PROPOSED','VALIDATED','READY','RUNNING','COMPLETED','INCONCLUSIVE','FAILED','REJECTED','REVIEW_REQUIRED','ARCHIVED')),
 payload jsonb NOT NULL, PRIMARY KEY(experiment_id,revision)
);
CREATE TABLE experiment_exposures (
 exposure_id uuid PRIMARY KEY, experiment_id uuid REFERENCES experiment_definitions,
 recorded_at timestamptz NOT NULL, start_date date NOT NULL, end_date date NOT NULL,
 symbols jsonb NOT NULL, payload jsonb NOT NULL
);
CREATE TABLE experiment_governance (
 experiment_id uuid NOT NULL REFERENCES experiment_definitions, revision integer NOT NULL,
 recorded_at timestamptz NOT NULL, payload jsonb NOT NULL, content_hash text NOT NULL,
 PRIMARY KEY(experiment_id,revision)
);
CREATE TABLE experiment_edge_links (
 link_id uuid PRIMARY KEY, edge_id uuid NOT NULL REFERENCES edge_library,
 experiment_id uuid NOT NULL REFERENCES experiment_definitions, recorded_at timestamptz NOT NULL,
 payload jsonb NOT NULL, content_hash text NOT NULL
);
CREATE TABLE experiment_proposals (
 proposal_id uuid PRIMARY KEY, parent_experiment_id uuid NOT NULL REFERENCES experiment_definitions,
 experiment_id uuid NOT NULL REFERENCES experiment_definitions, recorded_at timestamptz NOT NULL,
 payload jsonb NOT NULL, content_hash text NOT NULL
);
CREATE INDEX experiment_exposures_period ON experiment_exposures(start_date,end_date);
