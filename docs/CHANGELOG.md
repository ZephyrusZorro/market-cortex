# Changelog

## 2026-10-03 — Phase 4 CORTEX v1

Added six allowlisted research tools over Phase 1/2 data, a typed single-orchestrator CORTEX flow, deterministic analyst/skeptic/limitations passes, internal evidence citations, optional loopback OpenAI-compatible claim selection, privacy-gated model use, PostgreSQL research-run manifests, pinned evidence replay, local CLI/API routes, and an integrated workstation pane with an active environment badge. Real Binance pilot research was validated; no local model runtime was configured, so the deterministic fallback was used. See [CORTEX v1](cortex/PHASE_4_CORTEX_V1.md) and the [Phase 4 exit matrix](planning/PHASE_4_EXIT_MATRIX_2026-10-03.md). Live Upstox/Alpaca remain deferred and no order path was added.

## 2026-10-03 — Phase 3 research workstation

Added a loopback-only Next.js research workstation and five read-only FastAPI workstation read models. The interface exposes real Binance pilot bars, Phase 2 features and MarketStateSnapshot, manifest/as-of context, correlation and breadth, coverage, lineage, local watchlists and notes. It does not calculate canonical indicators in the browser or expose execution controls. See the [workstation guide](workstation/PHASE_3_WORKSTATION.md) and [Phase 3 exit matrix](planning/PHASE_3_EXIT_MATRIX_2026-10-03.md).

## 2026-10-03 — Phase 2 deterministic analytics and market state

Added 38 versioned daily feature definitions, manifest-pinned analytical series, explicit same-session and UTC cutoff alignment, relative strength/correlation with sample coverage, five-member breadth, a vector market-state snapshot, transparent regime rules, read-only Phase 2 API/CLI, golden and point-in-time tests, and a bounded live Binance backfill/validation. [Calculation rules](analytics/PHASE_2_ANALYTICS.md) and the [exit report](planning/PHASE_2_EXIT_MATRIX_2026-10-03.md) record exact scope and evidence. Upstox/Alpaca live coverage remains deferred; no execution path was added.

## 2026-10-03 — Phase 1 foundation complete under Binance live-provider scope

Validated five public Binance pairs through isolated PostgreSQL and Parquet ingestion, atomic manifests, pinned/as-of API reads, coverage, encrypted backup, and separate restore. Added provider contract and calendar guards, correction replay fixes, expanded PostgreSQL failure tests, and a 39-test final suite. Upstox/Alpaca live checks and equity mappings/calendars are `DEFERRED_NOT_CONFIGURED`; see the [exit matrix](planning/PHASE_1_EXIT_MATRIX_2026-10-03.md). The owner's main database was not modified. No broker write path exists.

## 2026-09-30 — Phase 1 daily-bar foundation in progress

Owner authorized implementation while account validation remains open. Added installable Python modular monolith, typed registry-aligned daily-bar contracts, identity/calendar/quality logic, read-only provider adapters, local CLI and read API, PostgreSQL migrations/job/outbox catalog, SHA-256 Parquet manifests, DuckDB coverage, encrypted backup/isolated restore tooling, and hermetic tests. Added [ADR 0020](adr/0020-daily-bar-window-semantics.md) for provider-specific daily boundaries. This entry records the initial implementation checkpoint; subsequent validation appears above. No Phase 2 work or V1 release claim.

## 2026-09-26 — Phase 0.5 draft freeze

Archived original Phase 0 blueprint unchanged; recorded 19 ADRs; split living architecture documents; drafted versioned contracts, pilot and provider feasibility matrix, owner and hardware templates, Phase 1 fixture/test and milestone plan. No Phase 1 runtime code. Provider credentials, exact symbol resolution and host budget still require verification. See [readiness](planning/READINESS.md).

## 2026-09-26 — Phase 0.6 feasibility preparation

Narrowed scope to private local use; added owner-machine hardware and GET-only provider probes, per-candidate pilot register, practical source selection/usage, storage estimate, backup/restore plan, contract/intraday review and readiness report. No owner hardware report, account credentials or authenticated provider observations are available here; readiness remains blocked. Phase 1A proposal is conditional and no production implementation was started.

## 2026-09-26 — Phase 0.6 probe tooling hardening

Implemented Windows-safe GET-only provider probe with fixed endpoint allowlist, redacted atomic JSON report, per-symbol error isolation, explicit IEX/SIP historical distinction, Upstox native key lookup, Binance public metadata/klines, timeout and malformed-response handling. Added optional Windows `tzdata` declaration and 11 hermetic tests. No Phase 1A implementation.
