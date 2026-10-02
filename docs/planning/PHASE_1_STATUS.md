# Phase 1 implementation status — 2026-10-03

**Phase 1 market-data foundation: COMPLETE under the owner-approved Binance live-provider exit scope.** This is a research-only daily-bar foundation, not the Phase 3 workstation or a production data service. The [exit matrix](PHASE_1_EXIT_MATRIX_2026-10-03.md) records P01–P22 evidence and the precise limits of each test.

| Area | Status | Evidence |
| --- | --- | --- |
| Contracts, identity, calendars | Complete for the foundation | Versioned schema; venue-scoped valid-time mappings; explicit sessions and calendar-version checks; synthetic DST, holiday, and early-close cases. |
| PostgreSQL, jobs, outbox | Complete for the foundation | PostgreSQL 17.11 migration and repeated isolated integration runs; duplicate handling, correction, transaction rollback, retry/dead-letter, and idempotent outbox behavior. |
| Immutable market data | Complete for the foundation | Content-addressed Parquet and atomic manifests; five-pair public Binance pilot, 35 daily bars, zero storage inventory defects, seven duplicate BTC bars on repeat sync. |
| Quality and as-of | Complete for the foundation | Quarantine, coverage gaps, freshness states, strict availability and adjustment-vintage filtering; pinned correction replay and observed-arrival pilot replay. |
| Read API | Complete for the foundation | Loopback, read-only instrument, bar, manifest, health, and coverage routes; 20 pilot bar reads measured. |
| Backup and restore | Complete for the foundation | Encrypted database and Parquet backup restored to a distinct empty database and directory; manifest, identity, hashes, and pinned reads agreed. |
| Upstox and Alpaca adapters | Implemented; live validation `DEFERRED_NOT_CONFIGURED` | Mocked read-only calls, environment credential loading, safe missing-credential behavior, native identity and calendar guards. No authenticated result claimed. |
| India/US pilot mappings and calendars | `DEFERRED_NOT_CONFIGURED` | Official, versioned sessions and verified native IDs are required before those equity feeds can be enabled. No guessed equity coverage. |

The final test run on Python 3.12 and PostgreSQL 17 passed: **39 tests, 13 subtests**, with one nonfunctional Starlette/TestClient deprecation warning. A bounded live Binance probe and five-pair ingest, as-of API read, manifest inspection, encrypted backup, and isolated restore were executed. The pilot used disposable test databases and workspace storage; the owner's main database and `C:\MarketCortexData` were not modified.

Source-specific retention and account terms still need review before sustained ingestion. Phase 2 analytics and Phase 3 workstation remain separate roadmap phases.
