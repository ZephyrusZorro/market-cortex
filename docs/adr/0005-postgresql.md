# ADR 0005: Postgresql

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Identity, jobs, outbox and owner records require constraints and transactions.

## Decision
PostgreSQL transactional authority with migrations.

## Alternatives
SQLite, document DB.

## Consequences
Operational install cost but strong integrity and concurrent workers.

## Reconsideration triggers
Local setup burden outweighs benefit or measured access pattern changes.
