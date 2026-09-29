# Phase 1 — Market Data Foundation: ordered implementation plan

**Implementation update:** The owner authorized Phase 1 engineering on 2026-09-30. The table below is the original ordered plan; [current status](PHASE_1_STATUS.md) records code, tests and open live gates.

**Original planning snapshot:** At the time, no Phase 1 code had begun and the plan awaited [readiness](READINESS.md) and owner approval. The owner later authorized implementation; [current status](PHASE_1_STATUS.md) records the actual code and open validation gates. Each step includes objective; modules; dependencies; tests; output; completion rule; principal risk.

| Step | Objective / modules | Depends on | Tests / expected output | Completion / risk |
| --- | --- | --- | --- | --- |
| 1 | Local setup, DB migration framework and secret injection: `infra/`, `apps/api/`, `config/`, `scripts/` | Approved host/budget | Clean install and no-secret scan; repeatable local environment | Fresh-machine bootstrap; risk Windows/Postgres friction. |
| 2 | Materialize registry as typed Python contracts and versioning/migrations: `packages/contracts/`, `apps/api/` | 1 | JSON fixture validation, compatibility checks | One canonical contract representation, documented breaking migration; risk schema drift. |
| 3 | Instrument master, valid-time mappings and calendar registry: `packages/market_data/identity`, `/calendar`, DB migrations | 2, provider probe | P01–P06, P21 | Exact pilot IDs and sessions resolve without guessing; risk token reuse/exception sessions. |
| 4 | Source capability and rights registry, adapter protocol, one India/US/crypto daily adapter each: `packages/market_data/providers` | 2–3, verified credentials | Auth/429/partial/outage contract tests, symbol/earliest/latest probes | Documented supported subset; risk quota/price/coverage. |
| 5 | Raw batch boundary, validation, quarantine and dedup: `packages/market_data/ingest`, DB migrations | 3–4 | P07–P08, P11, P13, P18, P22 | Invalid/restricted data isolated and explainable; risk source semantics. |
| 6 | Immutable normalized daily bars, actions and manifest publication: `packages/market_data/storage`, `data/manifests`, migrations | 5 | P09–P10, P15, P19, checksums and crash injection | Committed snapshot readable, corrections append-only; risk DB/file atomicity. |
| 7 | As-of query and health/read API: `packages/market_data/query`, `apps/api` | 6 | P12, P14–P15, API pagination/error tests | Pinned/as-of view with provenance and honest freshness; risk unknown availability. |
| 8 | Durable jobs/outbox and controlled refresh/backfill: `packages/market_data/jobs`, `apps/api`, `scripts/` | 5–7 | P07, P18–P20, restart test | Idempotent replays, bounded retry and dead letter; risk duplicate/reordered events. |
| 9 | Backup, restore and runbook: `scripts/`, `infra/`, `docs/data/` | 6–8 | P16–P17 on isolated target | Successful encrypted snapshot restore and as-of equivalence; risk missing Parquet/artifacts/key recovery. |
| 10 | Pilot coverage and handoff report: `docs/data/`, `tests/` | 1–9 | Full hermetic suite plus credentialed probes, measured disk/query budgets | Each supported symbol has verified history, rights, freshness, adjustment and calendar; exceptions named; risk persistent provider gaps. |

Defer dashboards, CORTEX, indicators/strategies, options, ML and Phase 2. A small CLI/API health/read surface is part of the data foundation, not a workstation.
