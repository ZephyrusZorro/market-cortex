# Storage Validation — Phase 0.6

PostgreSQL remains the transactional source for identity, mappings, jobs, manifest pointer and outbox. Immutable Parquet plus manifests stores analytical observations; DuckDB reads pinned files and Polars may transform batches. A local artifact directory holds only permitted raw bytes and reports. The design keeps the interface/manifest separate from physical partitions. **Conceptual fit: CLEARED. Owner-machine installation and sizing: BLOCKED.** No PostgreSQL, DuckDB or Polars installation was measured on the owner PC.

Rough order-of-magnitude storage estimates, **not provider quotes or benchmarks**:

| Workload | Assumption | Approximate records / raw payload | Working capacity guidance |
| --- | --- | --- | --- |
| 25 daily symbols × 10 years | 252 equity sessions/year as upper-common basis; crypto differs; 150–300 bytes/row including metadata | ~63k rows, 10–20 MB before index/metadata overhead | Reserve 1–5 GB for DB, manifests, logs and artifacts; data itself is tiny. |
| 10,000 daily instruments × 10 years | 252 days/year × 200 bytes/row | ~25 million rows, ~5 GB before compression/replication | Tens of GB including history versions, indices and backup; benchmark. |
| 1,000 instruments × 1-minute × 1 year | 400 minutes/day × 252 days × 200 bytes/row | ~101 million rows, ~20 GB before versions/overhead | Plan tens to hundreds of GB depending sessions, sparsity, duplicate feeds and retention. |
| Tick data | 100 trades/sec × 6.5h × 252 × 200 bytes | ~1.18 billion rows and ~236 GB **per instrument-year** before overhead | Do not enable broadly without a measured retention/partition and cost plan. |

For the initial daily pilot, avoid tiny Parquet files per symbol/day; batch files by kind, venue, month and bounded instrument group, with manifest membership. Later ticks can use day/hour/shard partitions without changing query contracts. Store historical revisions append-only; compaction creates a new manifest. Separate primary data and backup drives; target at least one complete extra copy plus room for migration/rebuild.
