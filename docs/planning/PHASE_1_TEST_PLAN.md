# Phase 1 Acceptance Test Plan (defined before production code)

**Baseline:** [Phase 0 §§5–6, 12, 14](../architecture/PHASE_0_BASELINE_2026-09-26.md). Frozen case IDs and synthetic data in [fixture catalog](../../tests/fixtures/phase1_cases.json). No API/ingestion implementation exists yet. Tests are acceptance definitions, not claims that they pass.

| ID | Failure mode / setup | Required assertion |
| --- | --- | --- |
| P01 | Same ticker across venues and dates | Resolver returns exactly one venue-scoped UUID or explicit ambiguity; never guesses. |
| P02 | Ticker rename with old/new valid intervals | Both mappings resolve to same listing where appropriate; old symbol not used after expiry. |
| P03 | ISIN shared across venues | Separate listing IDs; issuer link allowed. |
| P04 | NY DST and India fixed offset | UTC interval and exchange-local `session_date` agree with calendar. |
| P05 | NSE/NYSE holiday and early close | No false missing bar for closure; early close interval ends correctly. |
| P06 | Crypto UTC daily and NSE daily | Distinct anchors; half-open windows, no midnight assumption for NSE. |
| P07 | Duplicate provider record/retry | Idempotent ingest; one canonical revision and one outbox event. |
| P08 | Missing expected trading-day bar | Gap explicit with reason; no interpolated observed OHLC. |
| P09 | Later corrected close | New immutable observation supersedes old; as-of before correction selects old. |
| P10 | Split/dividend known after decision | Raw history unchanged; adjusted view names action vintage; strict replay excludes unavailable action. |
| P11 | Two sources disagree | Retain both and display conflict/selection policy; no silent average. |
| P12 | Feed stale vs venue closed | Stale/closed/outage distinct, no current label for stale data. |
| P13 | Invalid OHLC or ambiguous ID | Quarantine, trace validation code and exclude from standard read. |
| P14 | Macro publication lag or late backfill | Strict `as_of` excludes unknown or post-cutoff availability. |
| P15 | Rebuild against pinned manifest | Repeat result/hash under same manifest; new correction changes manifest ID. |
| P16 | Backup after commit | Encrypted backup includes DB, referenced manifests/artifacts and policy metadata. |
| P17 | Restore to isolated directory | Checksums, pointers, mappings and P09 as-of result agree. |
| P18 | Provider 429/timeout/outage | Bounded retry; previous cached data stays labeled stale; dead letter is inspectable. |
| P19 | Manifest publication crash | Readers never see partial file; orphan repair safe and idempotent. |
| P20 | Event duplicate/reorder | Consumer idempotency and manifest-reference integrity hold. |
| P21 | Reused provider token, expired derivative | Valid-time resolution; no accidental contract identity merge. |
| P22 | Source rights forbid raw bytes | Store only permitted hash/metadata; restore does not resurrect prohibited raw payload. |

**Execution gates:** contracts validate against registry; synthetic hermetic tests run in CI; credentialed source probes in an explicit separate suite; an isolated restore rehearsal precedes supported coverage. Never mark a source fully covered from a mock fixture. Add measured p95 and disk-cost checks after actual pilot hardware is known.
