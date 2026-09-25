# ADR 0009: Event Abstraction

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Pipelines and later feeds need durable replay without immediate broker.

## Decision
Versioned domain events through PostgreSQL outbox and DB jobs, single worker initially.

## Alternatives
In-memory callbacks, NATS/Temporal immediately.

## Consequences
At-least-once handlers and reconciliation required; future bus replaceable.

## Reconsideration triggers
Throughput or long workflows demonstrably exceed DB worker.
