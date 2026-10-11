# Initial owner Binance data proposal — 2026-10-11

**Historical approved scope, executed on 2026-10-11. Owner market data is validated; do not rerun this initial procedure.** All 1,825 bars and five refresh jobs completed. A timezone-dependent final hash guard falsely failed, then the corrected read-only verifier confirmed unchanged migrations, schema and pinned data. See [Verified owner data completion](OWNER_MARKET_DATA_COMPLETION_2026-10-11.md). Actual OWNER_MAIN application acceptance remains pending; further owner record writes require fresh explicit authorization. The original approved scope and source probes below are retained as history.

## Proposed scope for explicit owner approval

| Item | Proposed value |
|---|---|
| Owner destination | Existing OWNER_MAIN / market_cortex on loopback 5432; exactly `C:\MarketCortexData`. |
| Instruments | **BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT**; Binance spot pair identities and provider-native mappings. |
| Source | Binance public HTTPS GET market data through the existing bounded read-only adapter; no credentials or paid service required. |
| Daily calendar | Verified BINANCE_SPOT venue; UTC 24×7 sessions, P1D bars; exclude unfinished UTC day. |
| Coverage | **2025-10-11 00:00 UTC inclusive through 2026-10-11 00:00 UTC exclusive**: 365 closed sessions per pair, last session October 10. |
| Prices and volume | Provider **raw** OHLCV, quoted in **USDT**; owner INR configuration does not imply an FX conversion. |
| Target coverage | Up to **1,825 valid bars**. Missing/rejected data must be reported rather than filled or invented. |
| Persistence | One crypto venue, five canonical instruments, five provider mappings; actual source batches, observations/revisions, manifests/membership, outbox publication records, and content-addressed Parquets. |
| Files | Expected **65 monthly Parquet partitions** (13 months × 5 pairs) if all requested bars are accepted; actual hashes/counts will be recorded. No overwritten historical file. |
| Refresh | Explicit incremental daily refresh, default three-session correction overlap, **07:00 Asia/Kolkata** latest-due-slot policy. |
| Scheduler | Optional existing Task Scheduler functionality; registration requires separate explicit enablement. No persistent service or task installed by this proposal. |
| Personal domains | No portfolio, prediction, journal, thesis, personalization or research fixtures created/imported. Genuine owner research remains user-authored. |

Current read-only public probes confirmed all five symbols are TRADING, quote USDT, and have an earliest sampled daily bar before the proposed start. Exact probe timestamps and provider-response hashes are in `OWNER_BINANCE_ONBOARDING_PROPOSAL.json`. The first sampled bar establishes available sampled history; it is not a claim of exhaustive exchange/delisted coverage.

## Backup, guards and recovery

The new recovery copy will use the existing isolated PostgreSQL 17 cluster on loopback 55432, a unique database name no longer than 63 bytes ending in _test, UTF8 encoding, and a unique subdirectory under C:\MarketCortexRestoreDrills. The pre-schema recovery database and the live pilot are retained untouched. Creation is limited to this new empty recovery target; no existing database is dropped, reset, migrated or overwritten. Compare recovered schema, migration checksums, record counts, row hashes and head against the fully migrated owner source before ingestion. Keep the new backup and recovery copy even if a later source fetch fails.

Before writing, verify the selected profile's **actual** database identity, thirteen unchanged migration checksums, current root/storage and record state. The last verified owner catalog contains only migration/head metadata; stop if unexpected market identities, observations, references or personal data appeared. Preserve the pre-schema encrypted backup and its retained recovery database.

Create a **new retained encrypted pre-ingestion backup of the fully migrated owner catalog**, with a locally supplied retained passphrase, unique output filename, and isolated recovery verification. This new baseline differs from the already-retained pre-schema backup. Keep both; do not overwrite or delete either. Use the existing backup/restore tooling and different empty UTF8 database/root. Stop if recovery, schema/count/hash checks or storage fail; do not attempt automatic overwrite/cutover.

Bootstrap checks live exchange metadata and the earliest sample again, generates owner-specific canonical IDs, and reuses existing reviewed mappings on a retry. It must not copy pilot IDs, data roots, journal records or portfolios. If a bootstrap/provider step fails, preserve registered identities/evidence and resume only the missing supported steps after reviewing the failure; never reset the catalog.

Fetch only the approved date range and five symbols. Ingestion validates identity, venue/calendar, OHLCV, adjustment basis and batch lineage. Identical observations are duplicates; changed historical evidence creates revisions/manifests instead of replacement. A completed-data repeat must store zero unchanged bars and preserve the head, except when an actual provider correction is recorded transparently.

No historical knowledge is backdated: mapping availability and fetched bar availability are recorded at their observed arrival. A cutoff before owner ingestion may correctly yield no visible owner history even when event dates are older. Frozen manifest/as-of reads must replay the same evidence, and later refresh must not change those pinned results.

## Approved guarded execution

Run [the approved command procedure](OWNER_BINANCE_ONBOARDING_APPROVED_COMMANDS.md) in Terminal 1, which already contains the private owner connection. The implemented wrapper prompts for the retained backup passphrase through hidden input and runs the guarded onboarding module. It performs no migration or application launch.

The runner uses the existing bootstrap, Binance adapter, catalog ingestion, backup/restore, point-in-time reader and refresh functions. It resolves canonical instrument IDs from bootstrap; the existing sync-daily CLI requires --instrument-id, not --symbol. The earlier illustrative per-symbol command block has been replaced.

Six safety/recovery tests passed against disposable catalogs. This is implementation validation, not a claim that the actual owner backup or data ingestion has already happened. The owner execution report is the next required evidence.

## Post-ingestion acceptance

Verify exact owner identity/root and environment; expected session coverage, explicit missing/quarantine counts, finality and freshness; source hashes/native mappings; raw basis and USDT units; manifest parent chain; clean inventory; duplicate repeat and incremental refresh; pinned/as-of replay; and API/production workstation visibility. Save actual result IDs and timestamps. OWNER_MAIN must not select the pilot database/root. Keep optional source domains stale/unknown/deferred where their independent evidence is absent.

After owner runtime is genuinely validated, the owner can create a real research question through the UI and verify save/reopen/replay. Artificial habits, capital/positions, personal predictions or journal history are not generated to satisfy acceptance. This proposal authorizes no such records until the owner approves or initiates their actual content.

Explicit authorization requested after production pilot validation: the new pre-ingestion backup/recovery, these five verified identities and frozen 365-session histories, the stated immutable catalog/storage writes, and a bounded duplicate/incremental verification. Optional scheduler registration is a separate action. The production execution-policy blocker, India/US credential gaps and optional local model are documented independently.
