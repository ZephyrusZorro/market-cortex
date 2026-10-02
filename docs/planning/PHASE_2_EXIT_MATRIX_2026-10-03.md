# Phase 2 exit evidence — 2026-10-03

**Decision: Phase 2 deterministic analytics and market-state engine COMPLETE for the owner-approved five-pair Binance daily pilot. Phase 3 is ready to begin as a separate task.** Every canonical number is calculated by deterministic code from Phase 1 observations. No order, broker write, or AI calculation path was introduced. Upstox and Alpaca authenticated checks and live India/US coverage remain `DEFERRED_NOT_CONFIGURED`.

## Architecture and code delivered

| Area | Added or extended | Result |
| --- | --- | --- |
| Feature registry and contracts | `src/market_cortex/features.py` | 38 discoverable daily features; typed request, definition, point, series; numerical units, parameter validation, minimum history, lineage, source manifest/as-of, code hash, null reasons and elapsed time. |
| Numerical kernels | `src/market_cortex/indicators.py` | NumPy rolling work and deterministic recursive EMA/RSI/ATR/drawdown; no zero-filled warm-up or future-session interpolation. |
| Comparison and breadth | `src/market_cortex/alignment.py`, `breadth.py` | Explicit same-session or UTC decision-cutoff alignment, sourced optional FX contract, rolling relative strength/Pearson correlation with sample coverage, and exact-universe breadth with denominators. |
| State and regime | `src/market_cortex/market_state.py` | Versioned vector of 11 dimensions and transparent rule IDs, each with evidence and unknown/freshness status; no opaque market score. |
| Read surfaces | `src/market_cortex/api.py`, `cli.py`, `scripts/validate_phase2_pilot.py` | Six Phase 2 GET routes, two local CLI commands, and a read-only pilot validation utility. |
| Packaging and guidance | `pyproject.toml`, `README.md`, `docs/API_CONTRACTS.md`, `docs/operations/LOCAL_RUNBOOK.md`, `docs/analytics/PHASE_2_ANALYTICS.md`, `docs/analytics/VERSION_LOCKS_2026-10-03.json` | NumPy is a core dependency; version 0.2.0; exact formulas, cache/storage policy, version locks, API/CLI and limitations documented. |
| Tests | `tests/test_phase2_indicators.py`, `tests/test_phase2_engine.py`, `tests/test_phase2_postgres_integration.py` | Golden values, invariants, missingness, identity validity, alignment, state rules, API and isolated PostgreSQL correction replay. |

The Phase 1 catalog remains the authority for source history. Analytical results are calculated on demand and not persisted or cached. Every result names the source manifest, availability cutoff, provider, interval, adjustment basis, observation window, feature/rule version and actual code hash. The code hashes are locked by a test; changing a numerical definition requires a new version and retained old code.

## Supported analytical definitions

The 38 registered features cover arithmetic/log/cumulative/rolling/gap returns; SMA and EMA; price-versus-average, moving-average slope/alignment, higher-high/lower-low structure, trend persistence/strength; Wilder RSI, ROC, MACD line/signal/histogram; sample rolling return standard deviation, annualized log-return volatility, true range, Wilder ATR, Bollinger middle/upper/lower/bandwidth, rolling high-low range, volatility midrank percentile; average/relative/change/z-score/signed price-volume metrics; and running peak, drawdown, maximum drawdown, duration and recovery. Periods are configurable within validated bounds. [Full equations, warm-up rules and units](../analytics/PHASE_2_ANALYTICS.md) are the normative definition.

Conventions that materially affect reproduction:

- EMA begins at the first full SMA seed; RSI and ATR use Wilder recurrence after a full seed. RSI14 needs 15 consecutive closes; a flat valid run yields RSI 50.
- MACD defaults to 12/26/9 and its histogram first requires 34 consecutive closes. Bollinger bands use population close standard deviation (`ddof=0`); return volatility uses sample standard deviation (`ddof=1`).
- Annualized log-return volatility uses √365 for 24/7 sessions and √252 for regular exchange sessions unless explicitly overridden. Volatility percentile uses midranks, so tied constant values sit at 50 rather than 100.
- A missing expected session breaks rolling windows. Prelisting dates are ineligible, not counted as missing bars. Zero denominators, missing volume, insufficient history, unavailable observations and degenerate correlation become null with explicit reasons.
- Relative strength uses the ratio of two aligned rolling returns. Correlation uses Pearson on complete aligned log-return pairs and reports its window, pair count, coverage, missingness and consecutive-estimate change.

## Live Binance validation

The isolated PostgreSQL 17.11 pilot catalog from Phase 1 was extended with bounded public HTTPS GET daily-history reads for BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT and XRPUSDT. For each pair, the requested inclusive window **2025-09-01 to 2026-10-01** has **396/396 visible daily sessions** at fixed cutoff **2026-10-02T21:54:30Z**. Each sync stored 389 additional bars, recognized the previous seven as duplicates, and quarantined none. The catalog contains **1,980 observations**, **10 manifests**, and **75 referenced Parquet files**; storage inventory found no missing, corrupt, staged or unreferenced files.

The pinned source manifest was `8b5bbfd6-699d-4c40-8f9f-3377604a61ea`. SMA200, RSI14, MACD histogram, ATR14, annualized volatility20 and relative volume20 were non-null for all five pairs at the evaluation session. The older Phase 1 manifest `bbc98286-3136-4ff4-9602-e6d8065570c5` still showed only seven observed BTC sessions and a null SMA200 at the same cutoff. This directly demonstrates that later backfill does not appear under the old manifest. The [local read-only validation report](../../data/probes/phase2_pilot_2026-10-03.json) contains the five-pair feature IDs, numerical values and API statuses; it is ignored by Git and contains no credential or DSN.

The deterministic snapshot ID at that fixed manifest and cutoff was `79f17004de4b6705ddbc591a8cb8b5b4b962e16dd61071e61caffbb45c6da198`. Five repeated calculations returned the same ID. Its categories were: trend `up`, momentum `mixed`, volatility `middle`, traded-volume proxy `typical`, participation `complete`, five-pair breadth `broad_positive`, alt relative strength `btc_outperforming`, alt/BTC correlation `high`, risk-appetite proxy `mixed`, freshness `current`, and uncertainty `bounded`. The regime was `mixed` because the directional dimensions did not jointly meet an uptrend or downtrend rule. These are rule outputs for **Binance pilot 5**, not claims about the whole crypto market.

## Acceptance validation

| Gate | Evidence | Status |
| --- | --- | --- |
| A. Phase 1 regression | Existing foundation, PostgreSQL and encrypted restore tests remained in both full-suite runs. | PASS |
| B. Deterministic features | Hand-calculated SMA/EMA/returns/RSI/MACD/ATR/Bollinger/volatility/volume/drawdown tests plus all five live pairs. | PASS |
| C. Reproducibility | Same manifest, code version/hash, parameters and as-of produced identical feature/snapshot IDs; version lock test passed. | PASS |
| D. No look-ahead | Synthetic and isolated PostgreSQL correction tests distinguish early as-of, later correction and old pinned manifest; live older manifest stayed at seven bars. | PASS |
| E–F. State and evidence | Real 11-dimension vector, exact five-member breadth, feature/comparison references, rule IDs, coverage/freshness and unknown states. | PASS |
| G. Local API | Feature definitions, compute, correlation, market-state and regime routes returned HTTP 200 against the live pilot; read-only route tests passed. | PASS |
| H. Quality | Missing sessions, prelisting dates, missing volume, zero variance, provider ambiguity, stale evidence and insufficient history are surfaced or rejected. | PASS |
| I. Repeatability | Two consecutive full runs: **56 passed, 13 subtests passed, one Starlette/TestClient deprecation warning** each. Isolated test schemas remaining afterward: zero. | PASS |
| J. Performance | Five complete on-demand state calculations on the owner Windows machine: median **1,762.786 ms**, nearest-rank p95 **1,946.368 ms**. This is a five-sample local check, not a sustained latency guarantee. | PASS |
| K. Security | Only fixed read-only provider GET paths and local GET analytics routes; no new secret output or broker/trading path. | PASS |

## Known limits and deferred work

- The five public Binance pairs are the only live Phase 2 universe. Upstox/Alpaca remain `DEFERRED_NOT_CONFIGURED`; verified native mappings, official exchange calendars, feed entitlements and usage/retention rights are prerequisites to real India/US calculations. Mixed-calendar and FX-aware comparison contracts fail closed without valid source inputs.
- Breadth, correlation and the risk-appetite proxy describe only this five-pair universe. There is no global market breadth, sector breadth, order-book liquidity, macro context, corporate-action feed, fundamental data, derivatives, intraday indicators, ML regime model or prediction claim.
- The current comparison HTTP route has no verified FX feed and therefore rejects currency mismatch. The internal FX conversion contract requires its own sourced rate, manifest and availability. Cross-venue UTC cutoff alignment has synthetic tests but no live equity feed.
- Phase 1 removes quarantined rows from standard reads; Phase 2 reports `NO_VISIBLE_VALID_BAR` for a missing valid observation. That reason can include never fetched, unavailable at cutoff or quarantined; it does not imply an observed zero or identify the exact cause without a separate catalog investigation.
- Results are computed on demand. Materializing frequently requested features or adding a bounded cache awaits measured need; any future cache must key on source manifest, as-of, provider, adjustment, window, parameters and code version/hash.
- Live validation used the existing isolated localhost pilot database and external local Parquet root, not the owner's main `market_cortex` database. The disposable PostgreSQL test cluster is stopped after verification. Broad or scheduled ingestion needs a separate review of current provider retention terms.

**Phase 3 readiness:** the read-only, versioned feature and state contracts are ready to be consumed by a future workstation. Phase 3 was not started here.
