# ADR 0012: Cortex Orchestration

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Research needs skepticism and bounded tool permissions.

## Decision
One orchestrated loop with optional specialist passes and trace.

## Alternatives
Unbounded agent swarm, hard-coded chat chain.

## Consequences
Simpler audits; some tasks may need tailored workflow later.

## Reconsideration triggers
Evaluation demonstrates measurable benefit from separate agents.
