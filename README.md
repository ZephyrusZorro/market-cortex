# MARKET CORTEX

Private, local-first market research software. **Phases 1–9 are implemented for the five-pair Binance pilot.** The [Phase 0 blueprint](docs/architecture/PHASE_0_BASELINE_2026-09-26.md), [Phase 1 evidence](docs/planning/PHASE_1_EXIT_MATRIX_2026-10-03.md), [Phase 2 rules](docs/analytics/PHASE_2_ANALYTICS.md), [workstation guide](docs/workstation/PHASE_3_WORKSTATION.md), [CORTEX v1 guide](docs/cortex/PHASE_4_CORTEX_V1.md), [opportunity guide](docs/opportunity/PHASE_5_OPPORTUNITY_AND_THESIS.md), [risk guide](docs/risk/PHASE_6_RISK_AND_PORTFOLIO.md), [learning guide](docs/learning/PHASE_7_JOURNAL_PREDICTION_LEARNING.md), and [Phase 8 exit matrix](docs/planning/PHASE_8_EXIT_MATRIX_2026-10-05.md) describe the validated scope.

## What runs now

- Versioned JSON Schema registry and typed daily-bar contracts, venue-scoped valid-time identity, calendar sessions, quality rules, quarantine, provenance and strict as-of selection.
- PostgreSQL migrations for identity, jobs, outbox, observations and atomic dataset manifest publication. Immutable daily bars are content-addressed Parquet. DuckDB reads pinned manifest artifacts.
- Read-only Binance, Upstox and Alpaca daily adapters. Binance public bootstrap works without credentials. Upstox requires an instrument key; Alpaca records its selected feed class. Missing credentials return `NOT_CONFIGURED`.
- Local FastAPI read surface, CLI, redacted source probes, hardware profile, encrypted backup and isolated restore utilities.
- Synthetic acceptance suite plus isolated PostgreSQL 17 integration tests. Five public Binance pairs completed bootstrap, ingestion, as-of API reads, manifest checks, encrypted backup and separate restore. Upstox and Alpaca live checks are `DEFERRED_NOT_CONFIGURED` until owner credentials and verified equity mappings/calendars exist.
- Versioned feature registry with deterministic returns, trend, momentum, volatility, volume, drawdown and cross-series analytics. A five-pair Binance state snapshot reports separate dimensions, breadth, quality, freshness, evidence and a transparent regime. Calculations read pinned Phase 1 manifests; no derived value changes raw history.
- A local Next.js research workstation with manifest/as-of selection, candlesticks and backend indicators, Feature Explorer, explainable state, correlation, breadth, coverage, lineage, local watchlists and notes. Run it with the Python API; see the [Phase 3 guide](docs/workstation/PHASE_3_WORKSTATION.md).
- CORTEX v1 research uses allowlisted deterministic tools, manifest-pinned evidence, typed claims, a skeptic/limitations pass, inspectable citations, saved research runs and evidence replay. A local model can curate existing claims; a deterministic fallback works without one. See the [Phase 4 guide](docs/cortex/PHASE_4_CORTEX_V1.md).
- Phase 5 adds eight versioned daily-bar opportunity detectors, recorded candidate and rejection events, structured versioned theses, deterministic monitoring, CORTEX candidate review and an integrated workstation scanner/board. See the [Phase 5 guide](docs/opportunity/PHASE_5_OPPORTUNITY_AND_THESIS.md).
- Phase 6 adds local versioned research portfolios, pinned position risk/R/heat/exposure/correlation, explicit what-if scenarios, hypothetical thesis overlays, grounded CORTEX risk tools and a Portfolio & Risk workspace. Native-currency and stale-data limits remain explicit. See the [Phase 6 guide](docs/risk/PHASE_6_RISK_AND_PORTFOLIO.md).
- Phase 7 adds an append-only private journal, frozen prediction definitions, deterministic session-aware outcomes, separate pre-registered/retrospective cohorts, detector/rejection statistics with sample limits, explicit lessons, hypothesis-only Edge Library, CORTEX evidence tools and Journal & Learning workstation. See the [Phase 7 guide](docs/learning/PHASE_7_JOURNAL_PREDICTION_LEARNING.md) and [exit matrix](docs/planning/PHASE_7_EXIT_MATRIX_2026-10-04.md).
- Phase 8 adds Quant Lab: registered canonical detector strategies, strict historical replay, labelled reconstruction, daily execution/costs, reconciled portfolio paths, metrics/drawdowns, bounded parameter grids, train-only walk-forward selection, robustness, seeded Monte Carlo, immutable research artifacts and grounded CORTEX quant tools. See the [Quant Lab guide](docs/quant/PHASE_8_QUANT_LAB.md) and [pilot results](docs/quant/PHASE_8_PILOT_RESULTS.json). Backtests do not establish a proven edge.
- Phase 9 adds Advanced Market Intelligence: immutable contextual facts/revisions, strict availability, partial ContextSnapshot, actual public Binance funding/OI/mark data and Treasury macro data, deterministic event risk, approved CORTEX tools, thesis/risk supplements, frozen Quant context, options/on-chain foundations, and the Intelligence workspace. See the [Phase 9 guide](docs/intelligence/PHASE_9_ADVANCED_MARKET_INTELLIGENCE.md) and [exit matrix](docs/planning/PHASE_9_EXIT_MATRIX_2026-10-05.md).

There are **no order endpoints or automated trade execution paths**. Live India/US, event calendars, licensed news, option chains and on-chain feeds remain deferred. No supported edge has been established; Phase 8 momentum temporal OOS remains **−7.82%, N=82**.

## Windows quick start

Use PowerShell in the extracted `market-cortex` directory. Python 3.12 is tested here; newer Python versions need compatible wheels.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
Copy-Item config\owner.example.yaml config\owner.yaml
.\.venv\Scripts\python.exe scripts\market_cortex.py doctor
```

Install local PostgreSQL and create a **dedicated empty database** with a dedicated owner role. Put the connection string in the current PowerShell process's `MARKET_CORTEX_DATABASE_URL` environment variable. Keep its password out of Git and shell transcripts. See [the Windows runbook](docs/operations/LOCAL_RUNBOOK.md) for migration, public crypto bootstrap, daily sync, API, backup and restore commands.

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py migrate
.\.venv\Scripts\python.exe scripts\market_cortex.py bootstrap-crypto
.\.venv\Scripts\python.exe scripts\market_cortex.py serve
```

The server binds to `127.0.0.1:8765`. `GET /api/v1/health` is available even before PostgreSQL is configured and reports `not_configured`. The `migrate` command applies migrations through `0010_context_intelligence.sql` for local research persistence and efficient summary browsing. Provider probes are separate: `python scripts\probe_sources.py --run --output data\probes\phase_0_6_local.json`.

In a second PowerShell window, start the workstation. Node.js and npm must be installed; `npm ci` is needed only on first setup or after dependency changes.

```powershell
cd apps\workstation
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. Both processes bind to loopback. The frontend server proxies an allowlist of read routes and bounded local CORTEX/opportunity research POSTs to the standard Python port. For a nonstandard backend port, set `MARKET_CORTEX_API_URL` in the frontend server process to a loopback URL before starting it. Set `MARKET_CORTEX_ENVIRONMENT=PILOT_TEST` or `OWNER_MAIN` in the Python process to label the connected catalog visibly. The PostgreSQL DSN stays only in the Python process.

## Layout

`src/market_cortex` contains the Python modular monolith; `apps/api` is the ASGI entrypoint, `apps/workstation` is the Next.js application, `packages/contracts` is the authoritative JSON Schema registry, `infra/migrations` is the PostgreSQL catalog, `data/lake` contains ignored immutable Parquet artifacts, `docs` holds the ADRs and runbooks, and `tests` holds synthetic cases. The code lives under `src` rather than several importable `packages/*` directories so the installed Python package has one stable namespace while domain boundaries remain separate modules.

Git is initialized locally without a remote. Do not commit owner configuration, provider tokens, journal contents, database dumps or downloaded data. [Owner actions](OWNER_ACTION_REQUIRED.md) list the deferred live-source and deployment checks.
