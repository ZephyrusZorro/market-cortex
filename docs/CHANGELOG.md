# Changelog

## 2026-09-26 — Phase 0.5 draft freeze

Archived original Phase 0 blueprint unchanged; recorded 19 ADRs; split living architecture documents; drafted versioned contracts, pilot and provider feasibility matrix, owner and hardware templates, Phase 1 fixture/test and milestone plan. No Phase 1 runtime code. Provider credentials, exact symbol resolution and host budget still require verification. See [readiness](planning/READINESS.md).

## 2026-09-26 — Phase 0.6 feasibility preparation

Narrowed scope to private local use; added owner-machine hardware and GET-only provider probes, per-candidate pilot register, practical source selection/usage, storage estimate, backup/restore plan, contract/intraday review and readiness report. No owner hardware report, account credentials or authenticated provider observations are available here; readiness remains blocked. Phase 1A proposal is conditional and no production implementation was started.

## 2026-09-26 — Phase 0.6 probe tooling hardening

Implemented Windows-safe GET-only provider probe with fixed endpoint allowlist, redacted atomic JSON report, per-symbol error isolation, explicit IEX/SIP historical distinction, Upstox native key lookup, Binance public metadata/klines, timeout and malformed-response handling. Added optional Windows `tzdata` declaration and 11 hermetic tests. No Phase 1A implementation.
