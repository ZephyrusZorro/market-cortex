# ADR 0017: Ai Tool Permissions

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Untrusted news/journal can inject instructions into AI tool flow.

## Decision
Least-privilege registered typed read tools; explicit owner-approved writes; no shell/SQL/network by model.

## Alternatives
Arbitrary tool access or prompt-only restrictions.

## Consequences
Capability maintenance; smaller abuse surface.

## Reconsideration triggers
New tools pass threat model, schema, audit and evaluation.
