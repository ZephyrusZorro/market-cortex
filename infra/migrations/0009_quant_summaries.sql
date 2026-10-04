-- Derived browsing projection. Full immutable payloads remain the authority.
-- Avoid repeatedly decompressing multi-megabyte decision ledgers for lists.
ALTER TABLE quant_artifacts ADD COLUMN summary jsonb NOT NULL DEFAULT '{}'::jsonb;
UPDATE quant_artifacts
SET summary = jsonb_build_object(
    'strategy_id', payload->'definition'->>'strategy_id',
    'metrics', payload->'metrics',
    'warnings', COALESCE(payload->'warnings', '[]'::jsonb)
)
WHERE kind <> 'source';
