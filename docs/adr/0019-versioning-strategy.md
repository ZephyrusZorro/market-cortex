# ADR 0019: Versioning Strategy

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Long-lived system evolves data, API, research and AI behavior.

## Decision
Semantic API/schema versions, DB migrations, immutable dataset manifests, versioned transformations/features/prompts/models, Git tags and ADRs.

## Alternatives
Unversioned mutable records.

## Consequences
Migration discipline; reliable rollback and comparisons.

## Reconsideration triggers
Contract evolution policy proves excessive against measured change rate.
