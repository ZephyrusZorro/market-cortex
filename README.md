# MARKET CORTEX

Private, local-first market research software. **Phase 1 market-data foundation is in progress; this is not a V1 workstation.** The [Phase 0 blueprint](docs/architecture/PHASE_0_BASELINE_2026-09-26.md) and [ADRs](docs/DECISION_LOG.md) remain the architecture baseline. The owner authorized implementation before live source credentials arrived; the [current evidence and gates](docs/planning/PHASE_1_STATUS.md) distinguish implemented code from validated data.

## What runs now

- Versioned JSON Schema registry and typed daily-bar contracts, venue-scoped valid-time identity, calendar sessions, quality rules, quarantine, provenance and strict as-of selection.
- PostgreSQL migrations for identity, jobs, outbox, observations and atomic dataset manifest publication. Immutable daily bars are content-addressed Parquet. DuckDB reads pinned manifest artifacts.
- Read-only Binance, Upstox and Alpaca daily adapters. Binance public bootstrap works without credentials. Upstox requires an instrument key; Alpaca records its selected feed class. Missing credentials return `NOT_CONFIGURED`.
- Local FastAPI read surface, CLI, redacted Phase 0.6 probes, hardware profile, encrypted backup and isolated restore utilities.
- Synthetic fixture suite. No live PostgreSQL or credentialed-provider integration was possible in this workspace.

There are **no order endpoints or automated trade execution paths**. Advanced feeds, strategies, CORTEX AI, ML and the workstation are subsequent work.

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

The server binds to `127.0.0.1:8765`. `GET /api/v1/health` is available even before PostgreSQL is configured and reports `not_configured`. Provider probes are separate: `python scripts\probe_sources.py --run --output data\probes\phase_0_6_local.json`.

## Layout

`src/market_cortex` contains the Python modular monolith; `apps/api` is the ASGI entrypoint, `apps/web` is reserved, `packages/contracts` is the authoritative JSON Schema registry, `infra/migrations` is the PostgreSQL catalog, `data/lake` contains ignored immutable Parquet artifacts, `docs` holds the ADRs and runbooks, and `tests` holds synthetic cases. The code lives under `src` rather than several importable `packages/*` directories so the installed Python package has one stable namespace while domain boundaries remain separate modules.

Git is initialized locally without a remote. Do not commit owner configuration, provider tokens, journal contents, database dumps or downloaded data. [Owner actions](OWNER_ACTION_REQUIRED.md) list the local validation needed before declaring Phase 1 complete.
