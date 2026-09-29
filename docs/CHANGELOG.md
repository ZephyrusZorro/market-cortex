# Changelog

## 2026-09-30 — Phase 1 daily-bar foundation in progress

Owner authorized implementation while account validation remains open. Added installable Python modular monolith, typed registry-aligned daily-bar contracts, identity/calendar/quality logic, read-only provider adapters, local CLI and read API, PostgreSQL migrations/job/outbox catalog, SHA-256 Parquet manifests, DuckDB coverage, encrypted backup/isolated restore tooling, and hermetic tests. Added [ADR 0020](adr/0020-daily-bar-window-semantics.md) for provider-specific daily boundaries. See [status](planning/PHASE_1_STATUS.md) for untested PostgreSQL and live-provider gates. No Phase 2 work or V1 release claim.

## 2026-09-26 — Phase 0.5 draft freeze

Archived original Phase 0 blueprint unchanged; recorded 19 ADRs; split living architecture documents; drafted versioned contracts, pilot and provider feasibility matrix, owner and hardware templates, Phase 1 fixture/test and milestone plan. No Phase 1 runtime code. Provider credentials, exact symbol resolution and host budget still require verification. See [readiness](planning/READINESS.md).

## 2026-09-26 — Phase 0.6 feasibility preparation

Narrowed scope to private local use; added owner-machine hardware and GET-only provider probes, per-candidate pilot register, practical source selection/usage, storage estimate, backup/restore plan, contract/intraday review and readiness report. No owner hardware report, account credentials or authenticated provider observations are available here; readiness remains blocked. Phase 1A proposal is conditional and no production implementation was started.

## 2026-09-26 — Phase 0.6 probe tooling hardening

Implemented Windows-safe GET-only provider probe with fixed endpoint allowlist, redacted atomic JSON report, per-symbol error isolation, explicit IEX/SIP historical distinction, Upstox native key lookup, Binance public metadata/klines, timeout and malformed-response handling. Added optional Windows `tzdata` declaration and 11 hermetic tests. No Phase 1A implementation.
