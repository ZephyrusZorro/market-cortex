# Three-market evidence review — 2026-10-14

Status: **INDEPENDENT_EVIDENCE_VALIDATED; OWNER_INTEGRATION_NOT_DEPLOYED**.
The operational commit/tag remain `cfe696d51b137566c15eebaf734ff7ee0ca95197` / `v1.0.1-operational`. No owner/pilot database connection, ingestion, migration, schedule, continuous collector, application restart, push or release occurred during this review.

## Evidence actually inspected

- Upstox: `runtime/multi-market-probe-371973ac2bc34a5b8e6e40d8ecac58d9.json` and its sibling immutable archive.
- Alpaca: `runtime/multi-market-probe-a21584d60eca4f0ca0e38e4074d5cf4d.json` and its sibling immutable archive.
- Read-only audit: `runtime/three-market-probe-final-audit-2026-10-14.json`. This verifies manifest chains, Parquet hashes/row counts, receipt counts, candle-source lineage, source identity, OHLCV validity, event hashes and arrival timing.
- Combined evidence: `runtime/three-market-review-2026-10-14/bundle-receipt.json`; all original provider manifests/artifacts are copied byte for byte into a new independent archive. Collector states and credential files are excluded.
- Actual source-backed API checks: `runtime/three-market-bundle-validation-2026-10-14.json`. Provider GETs were prohibited during these checks.
- Final archive with a retained 512 MiB quota: `runtime/three-market-capped-review-2026-10-14/bundle-receipt.json`; final API receipt `runtime/three-market-capped-bundle-validation-2026-10-14.json`. All nine selected-listing checks passed again: search medians 35.80–74.02 ms; history medians 35.71–48.60 ms. Originals and the earlier review bundle were preserved.

The original secure probes performed fresh raw provider comparisons using a separate comparison parser. Eight RELIANCE daily candles and nine AAPL daily candles matched every timestamp/OHLCV value: no missing, extra or changed timestamps. This review verifies the receipts and immutable rows; **raw HTTP bodies and socket payloads were retained as hashes only**, so a second offline raw-body reconstruction is unavailable. No additional credentialed comparison was fabricated or executed.

## Historical and streaming results

| Evidence | Upstox / NSE RELIANCE | Alpaca / AAPL |
|---|---|---|
| Historical source | V3 daily, provider adjustment unspecified | Daily IEX, raw, ticker remapping disabled |
| Accepted observations | 8: October 1, 5–9, 12–13 | 9: October 1–2, 5–9, 12–13 |
| Provider comparison | EXACT_OHLCV_MATCH, 8 rows | EXACT_OHLCV_MATCH, 9 rows |
| Authentication/subscription | Confirmed / confirmed | Confirmed / confirmed |
| Messages/events | 2 / 1 | 211 / 502 |
| Event types | 1 last-trade snapshot | 16 trades, 485 quotes, 1 minute bar |
| Price event age at receipt | 21,030.363432 seconds | 2.623073–2.732786 seconds; median 2.627543 |
| Fresh price events | 0 | 501 |
| Changing fresh prices | Not observed | 10 distinct trade prices, $344.61–$344.675 |
| Reconnects/duplicates/out of order | 0 / 0 / 0 | 0 / 0 / 0 |
| Capture-end connection | Disconnected | Disconnected |
| Confirmed entitlement | V3 LTPC connection and historical sample | IEX connection and historical sample |

Upstox's price ₹1,174.60 has event time `2026-10-14T10:29:37.078Z` (15:59:37 IST) and receipt time `2026-10-14T16:20:07.441432Z` (21:50:07 IST). The socket delivered a genuine old snapshot after the session; `market_updates_observed: true` in the old receipt meant a decoded observation, **not** fresh updates. A market-open capture is still required.

Alpaca's AAPL events span current US daytime trading. The minute bar's timestamp marks its window start; its approximately 62-second age is not quote transport latency. The receipt confirms actual exchange-feed WebSocket observations, not HTTP-generated prices. The workstation uses backend exchange WebSockets and browser HTTP polling every two seconds; it does not currently push prices over a browser WebSocket. No collector was left running by this review. No SIP/delayed-SIP/overnight entitlement was tested in these receipts.

Original Alpaca event records did not retain `x`, `bx` or `ax` venue codes. Their IEX feed lineage is known; individual historical execution venue codes cannot be reconstructed from hashes. The independent decoder now preserves these codes for future captures, separately from the security's listing exchange (e.g. NASDAQ).

## Full searchable discovery, not full chart coverage

| Provider | Present native records | Status/venue breakdown | Instruments with stored historical observations in the review bundle |
|---|---:|---|---:|
| Binance spot | 3,689 | 1,380 TRADING; 2,309 BREAK | 6 |
| Upstox cash segments | 36,255 | NSE 16,669; BSE 19,586 | 1 |
| Alpaca US asset catalog | 33,550 | 14,382 active; 19,168 inactive | 1 |
| Total | **73,494** | Provider-native records, not unique issuers | **8** |

Upstox includes 22,773 listed, 13,481 suspended and one listed/suspended conflict. NSE: 9,802 listed, 6,866 suspended, one conflict; BSE: 12,971 listed, 6,615 suspended. The catalog includes equity, debt and fund securities; it must not be described as 36,255 currently tradable stocks. Suspended/ambiguous records remain searchable with explicit status. Absence from a future catalog does not erase evidence or prove delisting.

Alpaca exchanges: OTC 17,448; NASDAQ 6,952; NYSE 3,744; ARCA 3,220; BATS 1,797; AMEX 389. There are 13,494 active records with `tradable=true`; that broker attribute does **not** prove IEX quote/history coverage. Classification is `equity_or_etf`; no universe-wide stock-versus-ETF classification has been established. SPY and QQQ have issuer documentation identifying them as ETFs, but canonical classifications are not imported.

Binance's public `exchangeInfo` was rechecked at `2026-10-14T16:57:37.277614Z`: 3,729 total records, 3,689 spot-enabled. This agrees with the selected immutable spot catalog. Broader derivative discovery is outside this count.

Nine exact selected-listing searches passed. Cached daily API responses returned 15 BTCUSDT and 15 ETHUSDT rows in the measured September 29–October 14 range, eight NSE RELIANCE and nine AAPL rows. BSE RELIANCE, NSE/BSE INFY, SPY and QQQ correctly returned `UNAVAILABLE` with zero cached candles. Discovery was not misrepresented as ingestion. Broker charts in the actual running browser remain **not validated**: the running independent API still uses its original Binance/public-India archive, not the new combined bundle.

## Performance and storage measurements

Actual copied source evidence, five samples per case, FastAPI TestClient in-process:

- Exact-symbol searches: medians 36.43–74.68 ms.
- Cached historical reads: medians 36.24–48.23 ms, including correct empty results.
- Latest catalog Parquets: Binance 623,614 bytes; Upstox 3,107,250; Alpaca 4,139,523. Combined **7,870,387 bytes / 7.51 MiB**.
- Combined bundle integrity: 362 manifests, 308 unique Parquets, 10,675,777 bytes before the validation receipt. It excludes the unused Upstox snapshots in the original Binance archive; it is not an owner-data count.
- Daily samples: Upstox 3,569 bytes / 8 rows; Alpaca 3,550 bytes / 9 rows. Small-file overhead dominates these ratios; do not treat them as large-dataset compression forecasts.
- Alpaca event Parquets: 32,289 bytes / 502 events over roughly 30 seconds. Linear extrapolation is illustrative only: this AAPL capture would imply about 24 MiB per 6.5-hour session before manifest/checkpoint overhead. Illiquid symbols and busier sessions differ substantially.

Earlier actual Binance production-browser measurements remain in `PRODUCTION_MARKET_VALIDATION_2026-10-14.md`: median chart render approximately 936 ms, instrument switch 380 ms, warm daily HTTP read approximately 80 ms after the read optimization. **Those measurements do not establish broker-browser performance.** The new measurements above are API preparation evidence, not production deployment acceptance.

## Implementation and regression evidence

New preparation:

- `market_observation_audit.py`: offline receipt/lineage/freshness audit; initial snapshots, delayed feeds, clock skew and bar-window timestamps distinguished.
- `market_archive_bundle.py`: new-destination-only, byte-exact three-provider evidence assembly; owner/pilot roots rejected, no collector state copied.
- `scripts/verify_three_market_bundle.py`: real cached rows/searches through the existing API with all provider calls forbidden.
- `market_rate_budget.py` + independent `PacedTransport`: shared provider budgets across transport instances, every network retry charged, quota exhaustion/cooldowns explicit and bounded. Coordination is process-wide, not cross-process/account-wide.
- `market_universe.py` / `market_data_app.py`: unchanged semantic catalogs reuse the pinned snapshot with a small immutable check receipt and separate catalog-check freshness. Changed catalogs create revisions; new knowledge timestamps follow completed provider responses rather than request start.
- `multi_market_probe.py`: new receipts carry explicit observation freshness; legacy flag semantics documented. Original receipts untouched.
- `market_stream.py`: Alpaca execution/quote venue codes retained; future-clock observations cannot display LIVE.
- `market_archive.py`: explicit Windows extended paths for immutable hard-link/staged publication; exclusive reuse/hash verification preserved. `storage.py` still uses `r+b` for Windows fsync.
- Optional archive capacity ceilings persist in new markers and cannot be relaxed by reopening. Failed capacity checks publish no partial append and delete no retained evidence. New bundle copies/checkpoints also enforce the configured ceiling; existing source archives are unchanged.

Full Python regression: **337 passed, 118 skipped, 13 subtests passed**, 37.32 seconds; one existing Starlette/httpx deprecation warning (`runtime/three-market-final-python-regression-2026-10-14.log`). The final quota/checkpoint changes then passed the focused source/probe/security/readiness suite: **74 passed**, including **19 preparation tests**. Skips require dedicated disposable PostgreSQL/restore opt-ins; no owner database was used to satisfy them. A default pytest temp-directory permission failure was avoided using a unique disposable temp root; a separate reproduced deep-path publication failure received the tested Windows fix. No outstanding failure in the final executed checks. No frontend source change was made in this review; its earlier 68-test/typecheck/production-build evidence remains separately dated.

Retained owner backup rehashed unchanged: `owner-current-dab5dbc0b5884373b56868c183cc4131.mcbackup`, SHA-256 `1cb01c848c4fc7ac94d28e533ff506596df917e31518192bdcc5c5ed9c93641a`. Its successful restore evidence is historical, in `POST_RELEASE_OWNER_PROTECTION.md`; no new restore or current owner SQL inventory is claimed. Current owner/pilot application ports are offline; independent 8677/3018 remain running and were not restarted.

See `THREE_MARKET_OWNER_INTEGRATION_PROPOSAL.md` for the exact staged approval scope and remaining gates.
