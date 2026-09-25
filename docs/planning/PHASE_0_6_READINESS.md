# Phase 0.6 Readiness Report — 2026-09-26

**Recommendation: NOT READY FOR PHASE 1A.** This is a private, local, single-owner, non-execution research system. Phase 0.6 verifies practical data and environment feasibility, not enterprise regulatory architecture. No Phase 1 code has started. The Phase 0 archived baseline remains intact; the 0.5 ADRs remain the architectural baseline.

| Requested result / former blocker | Classification | Evidence and shortest action |
| --- | --- | --- |
| 1. Hardware validation | BLOCKED | `config/hardware.local.json` absent; run hardware script on actual Windows PC and inspect RAM, cores, GPU/VRAM and intended data drive. |
| 2. Owner configuration | BLOCKED | `config/owner.yaml` absent; copy example and fill storage/data budgets, separate backup location, time zone, enabled markets, privacy flags. |
| 3. India provider probe | BLOCKED | Upstox documentation and read-only script prepared; no token/account in this runtime. Run six-symbol probe locally. |
| 4. US provider probe | BLOCKED | Alpaca documentation and raw/split test prepared; no account keys. Run five-symbol probe locally and verify feed class. |
| 5. Crypto provider probe | BLOCKED | Binance public GET from remote workspace timed out at proxy; run five-pair probe on owner PC. Coinbase optional fallback. |
| 6. Context asset coverage | PARTIALLY CLEARED | Explicit nine-slot source/proxy/defer map; actual access untested. Probe NIFTY/ETF/Cboe/Treasury/RBI as selected, defer fragile DXY/oil/gold benchmark. |
| 7. Basic corporate-action behavior | PARTIALLY CLEARED | Raw/split separation and AAPL/NVDA sample defined; actual response untested. Confirm selected source semantics; no enterprise action subscription required. |
| 8. Provider usage notes | PARTIALLY CLEARED | Private-use practical notes written; account tier/cache restrictions unknown. Confirm relevant provider terms locally. |
| 9. Final pilot universe | BLOCKED | 25 candidate rows individually specified; canonical/native IDs and history dates intentionally PENDING. Populate from successful probes. |
| 10. Final Phase 1 source choices | BLOCKED | Upstox, Alpaca IEX and Binance are **provisional**, documentation-verified only; no account-tested primary. Select after probes. |
| 11. Storage validation | PARTIALLY CLEARED | Rough daily/intraday/tick sizing and partition plan; host disk and DB round-trip untested. Check local capacity and Phase 1A install. |
| 12. Backup/restore | PARTIALLY CLEARED | Simple paused-write `pg_dump` + referenced manifest/artifact + hash/restore runbook; destination absent and no drill. Choose separate target before Phase 1A; rehearse before persistent ingest. |
| 13. Contract validation | PARTIALLY CLEARED | 19 draft schemas and port review cover requested fields conceptually; no live provider sample or runtime validator. Compare against probe outputs; do not redesign speculatively. |
| 14. Future intraday compatibility | CLEARED (design) | Half-open UTC interval, venue identities, generic observation envelope, kind-specific payloads and manifest-backed partitioners support later feeds; no advanced feed implemented. |
| 15. Phase 1 test readiness | CLEARED (definitions) | 22 frozen synthetic cases and acceptance plan cover requested failures; not executed against production code. |
| 16. Remaining blockers | BLOCKED | Actual machine profile, owner config/backup target, owner-machine source access with symbol/coverage/time/adjustment evidence. |
| 17. Proposed Phase 1A scope | ACCEPTABLE DEFERMENT | [Conditional proposal](PHASE_1A_PROPOSAL.md) defines skeleton only; no implementation until gate and owner approval. |

## Concrete steps to clear the gate

1. Run hardware report on the actual workstation and provide a nonsecret copy; record the primary data drive and separate backup drive.
2. Fill local owner configuration including budgets and privacy settings; keep tokens outside Git.
3. Run `python scripts/probe_sources.py --run` on that machine with credentials in local environment if available; provide its redacted summary. A credential-less Binance test alone cannot validate India/US accounts. Resolve all selected pilot IDs and a bounded oldest/latest history sample, then check needed tier/cache terms and raw/split behavior.
4. Decide whether to defer or label each inaccessible context source; freeze only the subset with observed data. Confirm a backup target and perform a restore drill as part of Phase 1A before persistent ingestion.

**Limits of current evidence:** `DOCUMENTATION-VERIFIED` is not `ACCOUNT-TESTED`; successful sampled candles do not prove complete multi-year history, missing-day policy or production reliability. No provider has been `PRODUCTION-VALIDATED`.
