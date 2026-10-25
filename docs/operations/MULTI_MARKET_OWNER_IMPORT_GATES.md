# Owner import and collection gates — not an authorization

Status (2026-10-14): **CREDENTIALED_PROBES_REVIEWED; CANONICAL_GATES_AND_OWNER_APPROVAL_PENDING**. See `THREE_MARKET_PROBE_REVIEW_2026-10-14.md` and the exact staged `THREE_MARKET_OWNER_INTEGRATION_PROPOSAL.md`. Upstox delivered a stale after-hours snapshot; Alpaca delivered fresh IEX trades/quotes. No owner import or persistent-collection command is approved by this document. No pending migration was introduced into the release migration directory.

## Required evidence before proposing writes

1. Retain the successful Upstox and Alpaca probe receipts, source/catalog hashes, feed authentication/subscription results and actual observations. Closed-market zero-update samples remain partial evidence.
2. Identify exact candidate native IDs and symbols. Reconcile Upstox listed/suspended series, NSE/BSE listing separation, ISIN/corporate-action changes and reused exchange tokens. Confirm Alpaca asset IDs, symbol-history boundaries, equity/ETF classification and feed coverage. Never derive an opaque canonical UUID from a ticker.
3. Obtain verified exchange sessions covering the proposed history. Preserve source/version/knowledge time, holidays, special sessions, early closes and DST. Do not create weekday-only owner calendars.
4. Review the current owner inventory through the established read-only preflight. Stop if it differs from the accepted inventory; do not assume continued owner inactivity from the old receipt.
5. Review provider terms/entitlements for private local retention. Upstox source adjustment policy remains unknown unless separately established. Alpaca raw IEX and any separately entitled SIP source remain distinct datasets. Adjusted vintages require their own lineage.

## The concrete proposal must specify

- Destination: inspected `OWNER_MAIN` / `market_cortex:5432` / `C:\MarketCortexData`; pilot and independent archives remain separate.
- Metadata snapshot IDs and proposed canonical instruments/mappings, each identity validity and knowledge interval, with ambiguity/unavailable exclusions.
- Exact selected-asset history ranges, intervals and feeds; no full-market minute backfill.
- Expected accepted-session counts from verified calendars; maximum request/page/row budgets and disk budget. Record empty/quarantined/missing-session results rather than inventing bars.
- Retained encrypted current-state backup, isolated restore/drill root/database, integrity/row fingerprint/research replay acceptance and abort conditions before writes.
- Idempotent bootstrap/ingestion through the established catalog/manifest system, preserved revision history and as-of evidence; no migration reruns, synthetic owner fixtures or ledger edits.
- Post-write counts, file hashes, pinned/as-of reads, feed/coverage/freshness labels and unchanged prior research replay.
- Separate production integration acceptance and schedule/collector approval. Credential storage and source probes do not authorize any of these writes.

## Measured planning inputs, not universal size promises

Independent validation retained four catalog artifacts (original and indexed snapshots), totaling 6,523,774 compressed bytes for 79,806 snapshot rows. The latest catalogs contain **39,903 distinct provider-native identities**: 3,684 Binance and 36,219 Upstox cash identities. Do not sum historical snapshot rows as unique securities.

The small Binance source sample stored 125 candle revisions in 19,134 compressed bytes, approximately 153 bytes/row. Sixty-three captured feed events across small batches occupied 50,349 bytes, approximately 799 bytes/event. These are source-archive measurements; canonical owner Bar JSON, monthly partitioning, different feeds, correction density and manifest/checkpoint overhead can change sizes materially.

Planning formula: `selected instruments × verified sessions/bars × measured bytes/bar × revision/overhead margin`. For example, 100 crypto pairs × 365 daily bars × 153 bytes is about 5.6 MB for source candles before overhead; it is an estimate, not an approved scope. Minute history and continuous events grow much faster. At one event/second and the small-batch observed ratio, one asset would occupy roughly 69 MB/day before other overhead; do not assume that rate for another market or stream.

The collector is capped at 50 selected Binance/Upstox instruments or 30 Alpaca IEX instruments; each capture stops at 200,000 accepted events. Rate, disk headroom and approved retention must be measured before persistent use. There is no automatic evidence deletion. The proposed schedule/profile remains disabled and selected symbols are empty.

## Safe recovery

Provider failures are code-only; REST retries are bounded, feed reconnection uses bounded exponential backoff and failures never trigger broker writes. Metadata snapshots, candles, corrections, raw response hashes, checkpoints and gap records remain immutable. Manifests are partitioned by kind/provider with ordered hash-named files, so regular event appends do not parse every historical event manifest.

After a collector outage, read its verified checkpoint, record the unavailable tick interval, and recover only provider-available bars within the configured three-day/100-call recovery budget. The interrupted candle is included; an in-progress candle never marks its range complete in the cache. Older outage ranges are explicitly truncated and require a reviewed backfill. OHLCV does not reconstruct missing ticks.

Windows/OneDrive readers can block atomic replacement of an existing checkpoint. Checkpoints now use exclusive immutable publication and hash verification; the earlier partial checkpoint and reports were retained. On an unclean exit, a stale writer/collector lock stops new writers. Verify the recorded process is gone and preserve a diagnostic copy before any operator removes that specific lock; never remove another process's lock or immutable artifacts.

If an approved future owner ingestion partially fails, retain committed evidence and failed-job receipts. Resume only after read-only reconciliation of actual committed state and an idempotent scoped procedure. No reset, unverified rollback or repeat full onboarding.
