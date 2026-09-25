# ADR 0011: Deterministic Analytics

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Financial calculations require traceability and reproducibility.

## Decision
Typed pure analytics services own numbers; AI only invokes and explains.

## Alternatives
Model-generated arithmetic, hidden chart-library indicators.

## Consequences
Testing/versioning burden, reproducible results.

## Reconsideration triggers
A new computation engine passes equivalent golden and replay tests.
