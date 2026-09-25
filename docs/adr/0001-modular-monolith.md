# ADR 0001: Modular Monolith

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
One-owner local system needs coherent domain transactions and low operational burden.

## Decision
One deployable Python backend with typed internal module boundaries; extract services only on measured need.

## Alternatives
Microservices; separate workers/services immediately.

## Consequences
Simple recovery, but module discipline and import rules matter.

## Reconsideration triggers
Sustained independent scaling, isolation or team ownership need.
