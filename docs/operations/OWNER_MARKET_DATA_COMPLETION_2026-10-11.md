# Owner market-data verification — 2026-10-11

**VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY.** OWNER_MAIN production startup and read-only API/browser checks subsequently passed. The owner separately approved one genuine CORTEX record, saved as `f329f8c9-1274-4be5-8f8d-0e695cdd7e7c`; its six evidence hashes replayed successfully. OWNER_READY remains pending the final owner inventory and controlled restart acceptance. The data recovery itself authorized no further record writes. Do not rerun onboarding or migrations.

## Evidence

The original execution report is preserved unchanged at `runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/report.json`. Its SHA-256 remains `2b96abfc17cc7e0b671c03b83d2f4820c13f0023e9b52369a4503cb5785f925e`.

The owner ran the corrected read-only verifier in the existing private Terminal 1. The inspected receipt is `runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/verification-7c13d8d2c4534941a72e39e258d6249d.json`. It reports successful live owner verification and `owner_database_writes=false`. The connection was unavailable to the agent; these live owner results come from the owner-executed receipt. Derived results are in `OWNER_MARKET_DATA_COMPLETION_RESULTS.json`.

## Root cause

The final migration guard hashed PostgreSQL `to_jsonb` migration rows under the session timezone, Asia/Calcutta. The baseline snapshot hashed those same rows under UTC. `applied_at` is a timestamptz: its JSON text uses different offsets for the same instant. The serialized hashes differed even though migration history was unchanged. The phase label EXPLICIT_INCREMENTAL_REFRESH remained from the preceding completed step; this was a final verification failure.

The live receipt confirms all 13 migration IDs and checksums, their UTC-normalized full row hash including applied_at, and the schema fingerprint match the baseline. There are zero pending or changed migrations. The session hash is `639655e40806f863c96fd8132ffe4ff098543a536f330ef45aca9b7b27c67e3c`; the matching baseline/UTC hash is `a10a7e8897bdfcc2830386d1ad8151fe22c6a6b7302468677e4c8893f3fd3093`. Schema fingerprint: `596fdf250422719c6aa31852644b8329cb65137164bfc7e6d16422acd515cafd`.

The minimal code fix sets transaction-local UTC before hashing the complete migration rows. IDs, count, checksums and applied_at checks remain enforced. Nine focused safety/recovery tests passed, including rejection of genuine checksum and applied_at changes. No ledger row was edited and no integrity check was bypassed.

## Actual owner state

| Item | Verified result |
|---|---|
| Database | market_cortex, loopback ::1:5432, PostgreSQL 17.11, UTF8; read-only verification transaction |
| Schema | 51 application tables; 13 unchanged migration entries |
| Identity | Five instruments and provider mappings, one Binance spot venue |
| Raw history | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT; 365 sessions each; 1,825 observations total |
| Date coverage | 2025-10-11 inclusive through 2026-10-11 exclusive; last closed session 2026-10-10 |
| Storage | 65 referenced immutable monthly Parquets; zero missing, corrupt, unreferenced or staged files |
| Manifests | Five manifests, 65 file memberships; head 94368463-0587-46f0-8c3d-7b5dfee1826b |
| Provenance | 15 source batches; five completed jobs and five outbox records |
| Replay | All five frozen bar hashes match; original pinned/as-of evidence preserved; pre-availability reads exclude later-known data |
| Duplicate checks | Full-range repeat: zero new bars / 1,825 duplicates; incremental refresh: five done jobs / zero new bars / 15 duplicates |
| Quality | Zero quarantined records; all five pairs FRESH at the October 11 verification cutoff |
| Personal/research state | No journal, portfolio, prediction, thesis, saved CORTEX, mission, personalization or experimental owner records created |

Prices remain raw USDT quotations. The owner's INR base currency does not imply an FX conversion. No synthetic pilot records were imported. No ingestion retry or owner database repair is needed.

## Retained recovery

The encrypted backup `C:\MarketCortexBackups\owner-before-market-4f483e3fa2424c688c5cf60cebbc49e9.mcbackup` is retained: 112,693 bytes, SHA-256 `12e8734a56ccc5997df1983397fe7c76a65cf6b0157bdf6c02ec18c434b14aec`.

That specific backup was successfully restored and verified before ingestion. The retained isolated database `mc_owner_market_4f483e3fa2424c688c5cf60cebbc49e9_test` on port 55432 and directory `C:\MarketCortexRestoreDrills\owner-market-4f483e3fa2424c688c5cf60cebbc49e9` still match the pre-ingestion 51-table schema, 13 migrations, counts and record hashes. Independent read-only checks and the latest owner receipt confirm integrity. The earlier pre-schema backup/rehearsal are also retained.

This is the fully migrated **pre-ingestion** recovery baseline, with zero market Parquets. It is not a backup of the newly populated owner history. Do not restore it over the current owner database. No recovery cutover, rollback, deletion or restore over existing data was performed.

## Executed owner application launch (historical)

The owner executed the existing production launcher from the already-configured Terminal 1:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ApiPort 8765 -FrontendPort 3000
```

The inspected resulting state is `runtime/application-6898cdce55e34ef1ac077e05bdd55b35.json`, production mode. Direct/proxied health, selected owner identity, all five API bar hashes/coverage, foreign Host/Origin rejection and twenty browser observations including the authorized research record passed. Terminal 2's validated pilot remains separate on 8001/3002. See `OWNER_PRODUCTION_LAUNCH_RESULTS.json`, `OWNER_PRODUCTION_API_RESULTS.json`, `OWNER_PRODUCTION_BROWSER_QA.json` and `OWNER_RESEARCH_PERSISTENCE_RESULTS.json`.

The owner-terminal launch was required because its private connection is not inherited by Codex and the earlier agent production launch was rejected by automatic execution review. This restriction is separate from the corrected data verifier. Final acceptance now uses the read-only `scripts/verify_owner_production.py`, followed by the existing owner Stop/Start commands and reopening/replaying the same saved ID. That verifier requires unchanged schema/full migration rows/storage/head and exactly one additional cortex_research_runs row with the approved payload. No further owner record write is authorized. Scheduler registration remains disabled. Upstox/Alpaca live authenticated validation remains DEFERRED_NOT_CONFIGURED; local LLM configuration is optional.
