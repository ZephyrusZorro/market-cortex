# ADR 0007: Duckdb Polars

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Local analysis needs efficient columnar scans without a dedicated server.

## Decision
Use DuckDB for SQL on pinned Parquet snapshots and Polars for transformations when needed.

## Alternatives
Pandas-only, warehouse, time-series service.

## Consequences
Fast research with two optional query tools; avoid divergent transformation definitions.

## Reconsideration triggers
Workload benchmarking or operational complexity favors one replacement.
