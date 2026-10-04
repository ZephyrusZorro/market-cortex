# Phase 6 exit matrix — 2026-10-03

Final verification date: 2026-10-04.

**Status:** Complete for the Binance Pilot 5 research scope. **Release:** `phase6-v0.6.0` (the tag resolves to the clean Phase 6 commit). **Baseline preserved:** `phase5-v0.5.0` at `013aeec`. Nothing was pushed. Development and synthetic data used only the isolated `PILOT_TEST` PostgreSQL database ending `_test`; the owner main database was not changed.

## Acceptance

| Gate | Result | Evidence |
| --- | --- | --- |
| A, Q — Phase 1–5 regressions and repeatable full suite | Pass | Final complete backend suite passed twice on 2026-10-04: 94 tests and 13 subtests each, with all PostgreSQL/restore/Pilot 3–6 integrations enabled and no skips. Frontend passed 15 tests twice; typecheck and production build passed. One known Starlette/TestClient deprecation warning. |
| B — Versioned, auditable portfolio | Pass | `0005_portfolio_risk.sql`; immutable full `portfolio_versions` payloads; add, correction and close tests; historical v4 replays after v6 close. |
| C–E — Position risk, R, research sizing | Pass | Decimal golden entry 100/invalidation 95/quantity 10 ⇒ 1R 50; fixed amount and fraction sizing; missing target stays unavailable; invalid long levels rejected. |
| F–H — Heat, exposure, concentration, correlation | Pass | Position and portfolio heat with unknown propagation; native-currency instrument, asset-class, currency, thesis/strategy and provider buckets; 35% concentration and 0.80/50% cluster rules; Phase 2 60-return aligned Pearson. |
| I, J — Scenarios and unknown risk | Pass | Explicit symbol shocks, position contribution reconciliation, zero shock, missing price/FX/invalidation and breached invalidation remain visible or null. |
| K — Freshness | Pass | Source/feature/state freshness, coverage, session, quality and stale warnings in risk snapshot and workstation. Market-state freshness preserves Phase 2's stale classification independently of regime availability. Current status is cutoff dependent. |
| L — Incremental thesis risk | Pass | Linked thesis overlay calculates before/after exposure, heat, concentration, BTC proxy and the same scenario without changing portfolio version. Historical thesis versions remain usable after a future head; invalid long levels return HTTP 422. |
| M, N — Grounded CORTEX and privacy | Pass | Allowlisted read-only `risk.portfolio`/`risk.scenario`/`risk.overlay` tools, evidence IDs, replay validation and cloud gateway blocking test. Multiple portfolios require an explicit ID; incremental thesis questions require quantity and entry assumptions. |
| O — Workstation | Pass | Portfolio screen renders the live test catalog; manually verified valuation, 0.95% heat, risk/unknown panels, a −10% what-if and linked thesis overlay through the loopback API. Frontend tests, typecheck and production build pass. |
| P — No execution | Pass | Risk routes and CLI write only local portfolio/research records. No order placement, broker write route, sizing-to-order path or autonomous deployment. |

## Calculation contracts

- `Portfolio` (`portfolio_v1`) is a local full-version record; `PositionInput` is long-only with positive quantity/cost, canonical instrument, native currency, timestamps, optional thesis/invalidation/target and provenance. `RiskSnapshot` (`risk_snapshot_v1`, `portfolio_risk_daily_v1`) pins portfolio version, manifest, UTC as-of, calculation source hash, data IDs, feature IDs, freshness, quality and warnings. Saved snapshots are immutable and idempotent.
- Entry `1R = quantity × (entry − explicit invalidation)`; current R and optional target R use the same denominator. Current-price-to-invalidation risk is unknown after breach. Research sizing divides fixed monetary or fractional capital risk by the explicit price distance. It is never an order quantity.
- Portfolio heat is sum of open long positions' current stored-price-to-invalidation risk divided by declared capital. One unknown position or missing FX makes total heat unavailable. Priced-position value and unrealized P/L exclude unrecorded cash. Portfolio drawdown remains unavailable without a real equity series.
- Same-session daily log returns feed the existing Phase 2 60-return Pearson correlation. A pair is flagged when correlation ≥ 0.80 and combined gross weight ≥ 50%; single-instrument concentration threshold is 35%. BTC sensitivity is a correlation-weighted exposure proxy divided by capital, not statistical beta.
- A what-if scenario multiplies stored market value by an explicit fractional shock per symbol and reconciles position to portfolio P/L only with complete base-currency coverage. It is not a forecast. No uncontrolled FX rate enters canonical calculations.

## Public Binance refresh and stored pilot measurement

The public read-only Binance endpoint returned HTTP 200 on 2026-10-03. Existing ingestion appended one **completed 2026-10-02 daily bar** for each of BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT and XRPUSDT, each as a new immutable manifest with `stored=1`, `quarantined=0`. The old head `8b5bbfd6-699d-4c40-8f9f-3377604a61ea` remains in the parent chain; the new head is `0624ecba-b711-4fbe-86ca-7fc666ec6f41`. The head manifest inspection found 397 physical rows per symbol. Storage scan: 80 referenced artifacts, zero unreferenced, missing or corrupt files, no staged files. Historical parent-manifest replay remained green.

`scripts/validate_phase6_pilot.py` created and removed a disposable `SYNTHETIC_TEST_PORTFOLIO` holding 0.1 BTC, 2 ETH and 10 SOL with declared 100,000 USDT capital. The final measurement used manifest `0624ecba-b711-4fbe-86ca-7fc666ec6f41` at `2026-10-03T17:20:00Z`. This is **not owner holdings**.

| Metric | Measured result |
| --- | ---: |
| Open-position value / gross exposure | 14,975.48100000 USDT |
| Unrealized P/L | 748.77405000 USDT |
| Current portfolio heat | 1,497.54810000 USDT, 1.497548% of capital |
| BTC/ETH Pearson | 0.877684, 60 returns |
| BTC/SOL Pearson | 0.823161, 60 returns |
| ETH/SOL Pearson | 0.806299, 60 returns |
| Concentration flags | BTC, ETH; BTC+ETH and BTC+SOL cluster pairs |
| Explicit broad Pilot 5 −10% what-if P/L | −1,497.54810000 USDT (−1.497548% of capital) |
| Linked BTC thesis overlay, +0.02 BTC | +1,690.36020000 USDT exposure; +169.03602000 USDT heat |
| Same −10% scenario before / after overlay | −1,497.54810000 / −1,666.58412000 USDT |
| Snapshot save and run time | Persisted; 7.892 seconds for fixture setup, risk, scenario and overlay |

At that cutoff, price and market-state freshness were `current`, with 2026-10-02 as the latest completed session. The result becomes stale if daily ingestion is not repeated. Warnings included `CORRELATED_CLUSTER_CONCENTRATION` and `PORTFOLIO_EQUITY_SERIES_UNAVAILABLE:DRAWDOWN_UNKNOWN`. The live workstation's separate one-BTC synthetic fixture showed 8,451.8 USDT priced value, 0.95% heat, a −845.18 USDT explicit shock result and a linked thesis before/after result. The test-only fixture is labeled `SYNTHETIC_TEST_PORTFOLIO` in the UI.

## Validation and limits

- Backend final full suite: **94 passed + 13 subtests, twice**, in 176.96 and 180.84 seconds. Both runs enabled dedicated PostgreSQL, encrypted restore and all Pilot 3–6 integrations; neither skipped a test. The one warning is the existing Starlette/TestClient `httpx` deprecation. Final targeted golden risk suite: 11 passed. Frontend: **15 tests across 5 files, twice**, followed by successful typecheck and optimized build. A live local browser checked the Portfolio & Risk page against the refreshed `_test` catalog and loopback API. Final logs are retained locally under ignored `runtime/phase6-backend-accepted-{1,2}.log` and `runtime/phase6-frontend-final-{1,2}.log`.
- Final review verified parameterized database writes, strict local input contracts, bounded loopback proxy routes and private-context cloud blocking. No environment, credential, generated build or owner-holdings files are in the release. The Windows Parquet `r+b`/`fsync` fix remains intact.
- Upstox and Alpaca authenticated live validation remains `DEFERRED_NOT_CONFIGURED`; their read-only Phase 1 abstractions are retained. No India/US live portfolio analytics are claimed.
- Missing governed FX, unrecorded cash, portfolio equity history, short positions, derivatives, liquidity, tax lots, margin, transaction costs and VaR remain explicit limitations. Risk is based on daily stored observations and owner-entered research context, never a broker account balance.
- Readiness for Phase 7: append-only portfolio and immutable risk histories can feed a journal and learning loop while preserving synthetic classification, manifests and as-of evidence. Phase 7 was not started.
