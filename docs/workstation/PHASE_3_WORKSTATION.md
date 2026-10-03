# Phase 3 research workstation

## Scope and architecture

The workstation is a private, local, research-only application for the exact **Binance Pilot 5** universe: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT and XRPUSDT. It reads Phase 1 PostgreSQL manifests and immutable Parquet observations through FastAPI, then displays Phase 2 deterministic features, alignment results, breadth and `MarketStateSnapshot`. There is no broker write path, order control, AI chat or frontend financial calculation.

`apps/workstation` is a Next.js/React/TypeScript application. Its server-side `/api/v1/*` route proxies a fixed list of GET requests to loopback FastAPI. Browser code receives only read-model JSON. Python credentials, provider configuration and the database URL stay in the Python server process. FastAPI supplies five workstation read models under `/api/v1/workstation/`: `context`, `overview`, `instrument/{id}`, `comparison`, and `manifest/{id}`. The first four resolve a published manifest and UTC availability cutoff; the instrument and comparison routes call existing Phase 2 engines. The manifest route exposes ancestry and integrity inventory. See [API contracts](../API_CONTRACTS.md).

Charts use Apache-licensed ECharts for raw daily candlesticks, volume, zoom/crosshair, overlays and feature panels. The chart component maps backend values onto axes; it does not recompute SMA, EMA, Bollinger Bands, RSI, MACD or ATR. Requests use `no-store`, and the frontend pins every analytical request to the context response's resolved manifest ID and as-of timestamp. This prevents one page load from mixing a moving catalog head with another cutoff.

## Windows setup and startup

Use the canonical repository and Python 3.12 virtual environment. The machine used for Phase 3 validation had Node.js 24.20.0 and npm 11.12.0. PostgreSQL must contain migrated market data and `MARKET_CORTEX_DATABASE_URL` must be set **in the backend process environment**. The source data root must contain the Parquet files referenced by that database's manifests. The normal project operations [runbook](../operations/LOCAL_RUNBOOK.md) covers database setup and Binance ingestion. Never point an automated test at the owner's main database.

PowerShell window 1, from the repository root:

```powershell
$env:MARKET_CORTEX_DATABASE_URL = '<your local database URL>'
$env:MARKET_CORTEX_DATA_ROOT = 'C:\MarketCortexData'
.\.venv\Scripts\python.exe scripts\market_cortex.py serve
```

This starts the existing read-only API at `http://127.0.0.1:8765`. Check `http://127.0.0.1:8765/api/v1/health`; `ready` means a catalog is configured, while `database_unavailable` means PostgreSQL could not be reached. A ready health response does not claim that data is current.

PowerShell window 2, from the same repository:

```powershell
cd apps\workstation
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. `npm ci` is needed only for first setup or dependency changes. For a production-mode local run, use `npm run build` followed by `npm run start`. Both scripts bind to `127.0.0.1`. If FastAPI uses a different port, set `MARKET_CORTEX_API_URL` in **window 2** to its loopback origin before starting Next.js, for example `http://127.0.0.1:8001`. The proxy refuses a non-loopback target.

An empty catalog shows an explicit empty/error state. The five-pair UI becomes populated only after the Binance pilot has been bootstrapped and ingested in the connected catalog. Current Binance data is stored daily history, not a live tick or quote stream. The workstation performs no ingestion by itself.

## Pages

| Page | What it shows |
| --- | --- |
| Overview | Five pilot instruments with last stored close, Phase 2 returns/indicators, quality/freshness, and a scoped market-state summary. |
| Instruments | Raw P1D candlestick and volume history; backend SMA20/50, EMA20, Bollinger bands, RSI14, MACD histogram, ATR14, volatility, relative volume and drawdown. Zoom, range and custom dates change display only. |
| Feature Explorer | Live Phase 2 registry definitions with search/category filter, approved period input, units, version, min history, current value, null reason and backend time series. |
| Market State | The exact Phase 2 vector, metrics, coverage, evidence references, freshness, unknown reason, transparent regime rules and snapshot ID. |
| Compare & Breadth | Backend cumulative returns, same-session Pearson correlation matrix with window/count/coverage/missingness/stability/version, and breadth for **Binance Pilot 5** only. |
| Data & Coverage | Visible session coverage and provider truth: Binance public validated, Upstox/Alpaca `DEFERRED_NOT_CONFIGURED`, native price currency and research limits. |
| Research Desk | Context-bound instrument chart, browser-local notes and watchlists keyed by canonical instrument IDs. Watchlists can be created, renamed, deleted and edited. |
| System & Lineage | Manifest/head/parent and schema, content hashes, file rows, source batches, storage inventory and execution boundary. |

The sidebar and Ctrl+K command search navigate real pages, features and instruments. No placeholder order or AI action exists. Daily bar sessions use the Binance UTC calendar; presentation timestamps are shown in Asia/Kolkata. Owner preference says INR primary and USD secondary, but all market observations retain their native `USDT` quote currency. No FX conversion is performed without a governed FX series.

## Manifest and as-of workflow

The context strip always shows mode, resolved manifest, UTC availability cutoff rendered in IST, and source freshness. **Latest** resolves the current catalog head. **Pinned** selects one of the recent published manifests and holds that dataset fixed. **Historical** selects a manifest (or current head) plus an IST local cutoff; the UI converts it to an offset-aware UTC timestamp before the API request. Each page then sends the resolved `manifest_id` and `as_of` so older research cannot see later observations. Historical and pinned modes have an emphasized strip. A pinned manifest alone still uses the time it was opened as the availability cutoff; choose historical mode when the availability cutoff must also be reproducible.

If a selected manifest, mapping or observation did not exist at the requested cutoff, the backend returns a missing/unknown/insufficient state. Feature points retain their null reason. Stale daily data is visibly stale. The UI never substitutes zero for unavailable results. The context picker lists the latest 30 manifests; older published IDs are still valid through the API but are not currently searchable in the picker. The current view appears in the URL, while manifest selection is held in the open browser session and must be selected again after reload.

## Validation and development

From the repository root, run `\.venv\Scripts\python.exe -m pytest -q`. Set `MARKET_CORTEX_TEST_DATABASE_URL` to a dedicated `*_test` database to include the existing PostgreSQL integration gates. The opt-in Phase 3 real-pilot read test also requires `MARKET_CORTEX_PHASE3_PILOT_DSN` (dedicated `*_test` pilot DB) and `MARKET_CORTEX_PHASE3_PILOT_DATA_ROOT` (its matching immutable Parquet root). It only reads the pilot.

From `apps/workstation`, run `npm test`, `npm run typecheck`, and `npm run build`. Frontend tests cover API errors, loading, universe, market state, context modes and IST conversion, Feature Explorer and deferred provider states. All endpoint and UI changes should preserve manifest/as-of semantics. Review ECharts tooltip and chart interactions in a browser when altering visual rendering; unit DOM tests do not render the chart canvas.

## Known limits

- Phase 3 supports stored raw daily bars only. No intraday/tick/quote/options feeds, order execution, AI synthesis, or predictive regime claims are present.
- Upstox and Alpaca adapters exist, but their live data and verified equity mappings/calendars await credentials: `DEFERRED_NOT_CONFIGURED`. Their markets are not displayed as covered.
- Five-pair breadth is a pilot sample, never the global crypto market. The comparison screen requires two to five supported members and a common UTC daily session.
- The chart does not perform arbitrary universe scans. The instrument and correlation read models are deliberately bounded to the pilot and to validated time windows.
- Watchlists and notes stay in the local browser profile; the PostgreSQL backup does not include them. Clearing browser storage or changing profile removes them. No browser-local secret is stored.
- Direct browser access to the Next.js URL is designed for this single-user loopback machine. It is not an authenticated multi-user service or internet deployment.
