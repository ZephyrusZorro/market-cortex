# ADR 0010: Modelgateway

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
AI vendors, privacy, budgets and model quality vary.

## Decision
ModelGateway routes versioned tasks to replaceable providers; no AI code in Phase 1.

## Alternatives
Direct model calls in domain, single mandatory local model.

## Consequences
Extra boundary and evaluation upkeep; model switch possible.

## Reconsideration triggers
Evaluation shows stable single provider or routing overhead material.
