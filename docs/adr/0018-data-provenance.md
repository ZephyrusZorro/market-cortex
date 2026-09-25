# ADR 0018: Data Provenance

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Conflicting or corrected provider observations require explanation.

## Decision
Raw batch ref/hash/rights, immutable normalized record, supersession, quality and manifest for every claim.

## Alternatives
Overwrite latest row or strip vendor metadata.

## Consequences
More storage and reconciliation; reproducibility and disagreement visibility.

## Reconsideration triggers
Cost forces retention-tier policy with preserved minimal audit metadata.
