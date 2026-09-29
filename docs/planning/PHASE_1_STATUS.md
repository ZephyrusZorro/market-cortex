# Phase 1 implementation status — 2026-09-30

The latest owner instruction supersedes the earlier approval pause and 30-day schedule. Phase 0.6 account validation remains open, while reversible Phase 1 engineering proceeds. The Phase 0 baseline has not been rewritten.

| Area | Status | Evidence / limit |
| --- | --- | --- |
| 0.6 probe | Implemented | 11 deterministic tests; existing owner-reported public Binance result is not independently revalidated in this workspace. Upstox/Alpaca keys absent here. |
| 1A contracts/config/identity/calendar | Implemented, synthetic-tested | `src/market_cortex/{contracts,config,identity,calendar}.py`; JSON Schema round-trip checks, DST, holiday/early-close synthetic cases. Real exchange calendars not loaded. |
| 1A PostgreSQL migrations/jobs/outbox | Implemented, database integration untested | SQL migrations parse; no PostgreSQL server in this execution environment. Queue/outbox runtime behavior needs an isolated DB test. |
| 1B daily adapters | Implemented, mocked | Fixed HTTPS GET endpoints, timeouts, bounded retry, Binance public, Alpaca raw/IEX-by-default, Upstox native key. Account entitlements, adjustments, history and venue semantics unverified live. |
| 1C immutable ingest | Implemented, artifact-tested | SHA-256 Parquet, manifest ancestry, head publication transaction, duplicate/correction logic, hash-only raw retention. PostgreSQL transaction and crash drill pending. |
| 1D quality | Partial | OHLC, volume, calendar/session, conflict, quarantine and gap functions. Full freshness SLAs, outlier policy and reconciliation rules pending real source data. |
| 1E as-of | Implemented in pure logic; DB integration pending | Known availability cutoff, unknown exclusion, correction selection, pinned manifests. Live published-vintage proof pending. |
| Backup/restore | Implemented, crypto unit-tested; drill pending | AES-256-GCM encrypted archive, scrypt key derivation, dump + exact referenced artifacts, isolated empty target requirement. No `pg_dump`/`pg_restore` installed here. |
| Read API | Implemented, mocked | Loopback CLI and read routes; source-backed query requires PostgreSQL and catalog data. |
| Phase 2–12 | Not started | Continue after Phase 1 evidence gates, preserving existing roadmap. |

## Executed tests

`python -m pytest -q`: 24 passing hermetic tests and one PostgreSQL integration test skipped without a dedicated test database, on Python 3.12. The 24 include 11 Phase 0.6 probe tests. This is not a claim of 22 fully completed Phase 1 acceptance cases. P01/P02/P04/P05/P06/P09/P11/P13/P14/P15/P18/P22 have partial synthetic coverage; P07/P08/P10/P12/P16/P17/P19/P20/P21 and real provider coverage still require integration evidence. [Frozen definitions](PHASE_1_TEST_PLAN.md) remain the gate.

## Next implementation sequence

1. Run PostgreSQL migrations and transaction tests on an isolated DB, including P07/P09/P15/P19/P20 and restart behavior.
2. Import verified pilot instrument mappings and versioned venue calendars from actual provider/official exchange evidence; reject ambiguity.
3. Run bounded Binance public pilot sync, gap/reconciliation and pinned as-of/backup/restore drills; measure disk use and query latency.
4. When keys are available, validate Upstox and Alpaca account access, native identities, feed class, history depth, adjustment semantics and rights, then ingest small windows.
5. Finish quality/freshness and the Phase 1 exit matrix. Only then build Phase 2 deterministic analytics and the workstation.

**Release decision: Phase 1 IN PROGRESS; V1 NOT READY.**
