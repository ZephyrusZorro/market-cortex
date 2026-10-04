ALTER TABLE jobs ADD COLUMN result_ref uuid REFERENCES quant_artifacts(artifact_id);
