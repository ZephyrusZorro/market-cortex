# Phase 1 exit evidence — 2026-10-03

**Decision: Phase 1 market-data foundation COMPLETE, with live Upstox and Alpaca validation `DEFERRED_NOT_CONFIGURED`.** The owner explicitly accepted Binance public market data as the live end-to-end provider for this phase. Completion means the core architecture and frozen P01–P22 acceptance behaviors have executable evidence; it does not assert India/US coverage, provider entitlements, source usage rights, or production readiness. No order or broker write path was added.

## Executed local evidence

- PostgreSQL 17.11 ran in an isolated localhost cluster on port 55432. The owner's existing databases were not modified. The integration test ran repeatedly in per-run schemas; no test schemas remained afterward.
- The final suite passed with two dedicated test databases and PostgreSQL client tools available: **39 passed, 13 subtests passed, one Starlette/TestClient deprecation warning**. This includes repeated PostgreSQL integration, encrypted isolated restore, provider contract tests, and calendar validation.
- A read-only Binance public probe returned valid instrument and daily-kline samples for BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, and XRPUSDT. [Redacted local report](../../data/probes/phase_1_2026-10-03.json) is ignored by Git. Public reachability does not establish full historical coverage or caching rights.
- Five venue-scoped identities were bootstrapped in an **isolated pilot database**, then seven completed UTC daily bars per pair were ingested for 2026-09-20 through 2026-09-26. Repeating BTCUSDT after the final adapter changes stored zero new bars and reported seven duplicates. The final pinned manifest `bbc98286-3136-4ff4-9602-e6d8065570c5` had 35 physical rows in five referenced Parquet files, with zero missing, corrupt, staged, or unreferenced files.
- An as-of cutoff before the observed 2026-10-03 local ingest returned zero visible bars for that backfilled window; a cutoff after ingest returned seven per pair. The coverage route returned seven expected and seven observed BTCUSDT sessions, with no gaps. This is correct observed-arrival behavior and makes no claim about what was historically knowable before local ingestion.
- The five-pair pilot was encrypted, restored to a separate empty test database and directory, and compared. Manifest head, identity mappings, five pinned seven-row query hashes, and all artifact checksums matched. The disposable test passphrase is not an owner backup key.
- Sample local read measurement: 20 FastAPI TestClient bar reads for one seven-day pair had p95 **192 ms** and max **393 ms**; five Parquet files used **44,218 bytes**. This small local sample is not a sustained or production performance benchmark.
- Upstox and Alpaca adapter tests assert fixed HTTPS GET endpoints, environment-only credential loading, no network call when credentials are missing, identity and validity-window checks, explicit calendar requirements, and read-only API behavior. Mock credentials and responses are synthetic; neither provider was called live.

## Frozen acceptance cases

| Case | Evidence reached | Remaining limit |
| --- | --- | --- |
| P01–P03 | Synthetic venue ambiguity, rename, and shared ISIN separation | Pilot India/US IDs need account evidence. |
| P04–P06 | Synthetic DST, holiday, early-close, and distinct UTC/session anchors | Versioned official calendars are not imported for the full equity pilot. |
| P07 | Isolated DB duplicate/outbox test; live BTCUSDT repeat stored 0, duplicated 7 | Long-running provider retries unobserved. |
| P08 | Read-only coverage route names `NO_VISIBLE_OBSERVATION_AT_CUTOFF`; synthetic missing date and live crypto 7/7 | India/US gap classification needs calendars and bars. |
| P09 | Isolated DB immutable correction and as-of test | Real provider correction unobserved. |
| P10 | Synthetic raw/split separation with named adjustment vintage and knowledge time | Corporate-action source and live adjusted feed unverified. |
| P11 | Synthetic disagreement retention | No overlapping live providers for one listing. |
| P12 | Synthetic stale/closed/outage/publication-grace states | Per-provider live SLA and outage signal not calibrated. |
| P13 | Isolated DB quarantine and read exclusion for invalid OHLC | Real bad-source event unobserved. |
| P14 | Strict unknown/late availability exclusion on daily observations | Macro series is a later source domain. |
| P15 | Pinned correction replay in DB; real pilot pinned reads match after restore | Broad replay corpus absent. |
| P16–P17 | Synthetic encrypted DB/Parquet drill and separate real-pilot restore | Owner's main DB and separate backup target not drilled. |
| P18 | Mocked bounded provider retry plus DB ready/retry/dead job states | No live 429/outage incident observed. |
| P19 | Injected failure after durable Parquet write left an orphan; retry published it without missing files | Process-kill drill not run. |
| P20 | DB handler failure rolled back receipt; retry consumed once and checked committed manifest | Multi-consumer production scheduling unobserved. |
| P21 | Synthetic reused token resolves to separate expired/current contracts | Live derivative IDs deferred. |
| P22 | Hash-only source metadata survived encrypted restore; no raw payload files returned | Actual provider retention terms remain unverified. |

## Deferred validation and operating limits

1. **`DEFERRED_NOT_CONFIGURED`: Upstox and Alpaca live validation.** When owner-held credentials are available, verify account entitlements, exact native keys, venue, feed class, history depth, timestamps, adjustments, quotas, and retention terms. Their adapters remain present and read-only. The five public Binance pairs alone are the supported live pilot.
2. **`DEFERRED_NOT_CONFIGURED`: India/US mappings and calendars.** Import source-backed, versioned NSE and US sessions including holidays and early closes before accepting equity bars. Bounded sync, gap/freshness checks, pinned replay, and corrections for those listings follow live source validation. No equity candidate is marked supported today.
3. **Owner deployment drill.** The isolated PostgreSQL 17 database, workspace Parquet directory, and encrypted restore proved the pipeline. Applying the same workflow to the owner's main database, primary data root, and a separate backup destination remains an operational rollout task. Existing main/test databases on port 5432 were untouched because their credentials were not exposed to this task.
4. **Sustained ingestion rights.** The public Binance probe establishes technical reachability, not provider permission for arbitrary local retention. Verify current terms before expanding history or scheduling continuous refresh.
