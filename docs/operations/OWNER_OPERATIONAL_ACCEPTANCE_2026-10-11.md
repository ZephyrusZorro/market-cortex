# MARKET CORTEX — Owner operational acceptance

**OWNER_READY for the supported Binance daily research scope — 2026-10-11.** This conclusion follows actual OWNER_MAIN production startup, API/browser operation, controlled shutdown/restart and persisted owner research replay. The earlier agent launch rejection was respected; the owner executed every production launch/restart through the existing scripts.

## Current application

- Workstation: http://127.0.0.1:3000; API: http://127.0.0.1:8765.
- Owner state: `runtime/application-a9c83bf65f414697b8cda568c8b868a3.json`, production mode, OWNER_MAIN. Keep this exact state path for safe shutdown.
- Owner database: market_cortex on loopback 5432, PostgreSQL 17.11, UTF8; data root `C:\MarketCortexData`.
- Pilot remains separate on 8001/3002 with market_cortex_pilot_test on 55432 and its original distinct data root.

## Acceptance evidence

| Area | Result |
|---|---|
| Architecture | Existing twelve development phases preserved; no new phase or unrelated feature |
| Production runtime | Owner and pilot production starts, controlled stops and restarts validated; Next start uses existing BUILD_ID K4ApJcYNA_48DSptxRH31 |
| Owner database | 51 tables, 13 matching migrations; no pending/changed migration; complete UTC migration-row hash including applied_at and schema fingerprint unchanged |
| Owner history | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT; 365 sessions each, 1,825 raw observations, 2025-10-11 through 2026-10-10 |
| Owner storage | 65 immutable Parquets, five manifests, 65 memberships; zero missing/corrupt/unreferenced/staged files and zero quarantine |
| Replay/as-of | All five frozen bar hashes matched; no availability backdating; selected manifest preserved |
| Incremental refresh | Five completed owner jobs; zero new bars, 15 recognized duplicates, stable head; scheduler remains disabled |
| Browser | All 16 navigation panes and advanced laboratory read view; real candles/indicators/state/coverage/lineage; ephemeral scan; unavailable contextual data and insufficient owner history reported explicitly; no console errors/warnings |
| Owner research | Exactly one separately approved genuine CORTEX row; saved/reopened/cited/replayed before and after production restart; no other personal domains seeded |
| AI | Deterministic fallback demonstrated with no model configured and zero paid API spend |
| Isolation/security | Distinct owner/pilot identities, heads and roots; foreign Host reads and foreign-Origin writes rejected by API/proxy; loopback boundary, no application-login claim |
| Regression | Full backend 361 tests + 13 subtests, no skips, one existing warning. Subsequent helper changes: nine onboarding safety tests and three import/read-only/count tests passed separately. Frontend full recheck 54 tests; typecheck/build passed. No single combined 373-test full-run claim |

The pre-restart owner receipt `runtime/owner-production-verification-1f9cecacc5ba4d48b0d4ad4b4adaf133.json` and post-restart receipt `runtime/owner-production-verification-abfa86482c814d57bef0d97223da4a9f.json` match on all table counts, schema, migration rows, head, research payload and backup hash. Both report `owner_database_writes=false`. Counts differ from the verified post-ingestion baseline only by the separately approved one research row.

Saved research ID: `f329f8c9-1274-4be5-8f8d-0e695cdd7e7c`. Evidence hash: `f6c96904277c739b8c6cf2977c6fe23c08672c30c0cd23d5033d182f1ae6c2e7`. All six tool evidence hashes match after restart; the full saved payload is unchanged. Original cutoff `2026-10-11T12:48:07.699784Z` remains attached to the saved research even when the workstation's current cutoff advances. Language is reopened, not regenerated.

## Corrected defects

The onboarding final guard used session-timezone timestamp JSON against a UTC baseline, falsely reporting MIGRATION_HISTORY_CHANGED. It now normalizes to transaction-local UTC while retaining every migration integrity check. The original failure report remains unchanged; read-only verification proved the actual committed owner state without ingestion retry or database repair.

The owner production verifier's direct file invocation selected `scripts/market_cortex.py` instead of the package. Use only this module invocation from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_owner_production
```

The old direct-file invocation fails before imports/configuration with a clear instruction. Import resolution, absence of configuration/receipt work for --help, read-only query ordering and rejection of an unexpected extra record are regression tested. This acceptance verifier deliberately expects the approved snapshot: after legitimate future owner writes, a mismatch requires reviewing the changed state rather than editing its baseline or bypassing checks.

## Retained backups and scope limits

Both actual owner encrypted baselines and their isolated recovery copies are retained and verified: the pre-schema backup/rehearsal and the fully migrated pre-ingestion backup/recovery. The latter's SHA is unchanged after restart. They predate the newly populated market/research state; the pre-ingestion copy contains zero Parquets. **They are not a current populated-owner backup.** Populated pilot backup/restore/artifact replay was validated separately. No recovery cutover or restore over the owner was performed.

India/US authenticated validation remains **DEFERRED_NOT_CONFIGURED**: Upstox/Alpaca adapters are retained; credentials, verified mappings/calendars and entitlements are required. Local LLM integration is optional. Task Scheduler registration remains disabled and requires separate approval. Prices are raw USDT, with no inferred INR/USD conversion. Binance Pilot 5 is the existing five-pair sample's name, not the database environment; OWNER_MAIN identity and owner-specific instrument IDs were verified.

No supported profitable edge, broker execution or autonomous capital deployment is claimed. The historical Phase 8 momentum result remains negative evidence from the earlier research validation, not a new owner experiment. No synthetic portfolio, journal, prediction, mission or experiment was imported, and no owner habits were fabricated.

## Owner controls

The owner and pilot applications remain running at the owner's request. To stop only the current owner application from the canonical repository:

```powershell
& .\scripts\Stop-MarketCortex.ps1 -StateFile .\runtime\application-a9c83bf65f414697b8cda568c8b868a3.json
```

For a future production start after that stop, use the existing private owner terminal:

```powershell
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ApiPort 8765 -FrontendPort 3000
```

Do not rerun onboarding, migrations, the research submission or historical restart blocks. Additional agent-driven owner record writes remain outside the single-record authorization. No credential or backup key is included in the reports. Original evidence is preserved. Release identity is the local annotated `v1.0.1-operational` tag after committing this validated snapshot; nothing is pushed.

Machine-readable acceptance: `OWNER_OPERATIONAL_ACCEPTANCE_RESULTS.json`. Detailed restart/API/browser evidence: `OWNER_PRODUCTION_RESTART_RESULTS.json` and `OWNER_PRODUCTION_RESTART_BROWSER_QA.json`.
