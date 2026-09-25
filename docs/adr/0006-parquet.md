# ADR 0006: Parquet

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Historical observations and reproducible research benefit from portable columnar files.

## Decision
Immutable partitioned Parquet plus manifest and hash catalog.

## Alternatives
Transactional-only DB, custom binary format.

## Consequences
Cheap scans and exports; file/DB publication needs explicit protocol.

## Reconsideration triggers
Concurrency/latency or retention constraints break measured targets.
