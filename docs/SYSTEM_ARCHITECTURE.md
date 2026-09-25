# System Architecture

**Baseline:** [Phase 0 §§4, 6, 13](architecture/PHASE_0_BASELINE_2026-09-26.md). [ADRs](DECISION_LOG.md) govern details.

One modular Python backend exposes FastAPI `/api/v1` to a TypeScript/React workstation. Seven conceptual engines are package boundaries, not services: Data Fabric → Analytics/State → Opportunity → Decision/Risk; CORTEX consumes typed deterministic tools and memory; Learning/Performance owns journal and predictions. `apps/api` is the composition root. `packages/contracts` defines stable IDs, time and provenance. Cross-domain work flows through application interfaces, not a UI SQL query or a provider object imported by analytics.

Phase 1 dependencies: contracts → provider interface/identity/calendar → raw batch/validation → append-only normalized observations/manifest → as-of query/health API. Transactional records and outbox use PostgreSQL; immutable history uses Parquet and artifact hashes; DuckDB/Polars query local partitions. The DB holds a committed manifest pointer; unpublished Parquet files are invisible. A repair job detects orphans and missing content. See [data architecture](DATA_ARCHITECTURE.md).

Later daily-to-intraday evolution adds typed observation kinds, finer time buckets and stream cursors. Neither session date nor provider ticker is the primary key. A later event broker or time-series engine must implement the same domain contracts. Reserved package folders do not imply Phase 1 implementation.

[Port and feed evolution sketch](architecture/PORTS_AND_EVOLUTION.md).
