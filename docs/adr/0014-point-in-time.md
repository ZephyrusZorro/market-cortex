# ADR 0014: Point In Time

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Backfills, revisions, filings and actions can leak future facts.

## Decision
Use event/publish/available/ingest/effective times, availability basis, immutable manifests and as-of cutoff; unknown excluded in strict replay.

## Alternatives
Latest-only data and retrospective adjustments.

## Consequences
More storage and conservative coverage; honest historical results.

## Reconsideration triggers
Only change with formal equivalent replay proof and migration.
