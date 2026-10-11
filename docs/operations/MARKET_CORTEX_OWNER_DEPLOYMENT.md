# MARKET CORTEX — Windows owner deployment

## Current owner acceptance — 2026-10-11

**OWNER_READY for the validated five-pair Binance raw daily research scope.** Current owner application: http://127.0.0.1:3000, API 8765, production state runtime/application-a9c83bf65f414697b8cda568c8b868a3.json. Actual startup, browser/API reads, safe stop/restart, full owner inventory and the single approved saved CORTEX record's six evidence hashes/payload passed. Read-only post-restart verification reports exactly the approved one research-row increase; schema, all 13 migration rows, head and 65 Parquets are unchanged. The pilot remains separately running at 3002/8001.

See [Final owner acceptance and current controls](OWNER_OPERATIONAL_ACCEPTANCE_2026-10-11.md) and OWNER_OPERATIONAL_ACCEPTANCE_RESULTS.json for current status, exact safe shutdown path, retained baseline backup scope and deferred items. Correct verifier invocation from the repository root: `.\.venv\Scripts\python.exe -m scripts.verify_owner_production`. No additional agent-driven owner writes, scheduler registration or push is authorized. The retained owner recovery baselines predate the newly populated market/research state. Upstox/Alpaca live credentials/mappings/calendars remain deferred; a local LLM is optional. The dated checkpoints and general procedures below are retained as history; do not execute completed onboarding, migration or restart blocks again.

Updated 2026-10-11 (Asia/Kolkata), continuing local commit `9de5113`. This is a deployment guide, not an owner deployment completion claim. The owner-started pilot production runtime and browser reads are **VALIDATED**; controlled production shutdown/restart and saved-artifact recovery are also **VALIDATED**. Codex itself still cannot retry the prior rejected production launch. Owner-terminal read-only connection is **VALIDATED**; owner schema migration is **VALIDATED**. Owner market-data onboarding is now **VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY**: 1,825 observations, 65 Parquets and five completed refresh jobs. The timezone-dependent final guard was corrected; the live read-only receipt confirms unchanged migration history/schema and pinned evidence. Actual OWNER_MAIN startup and read-only API/browser views passed on 8765/3000 using application-6898cdce55e34ef1ac077e05bdd55b35.json. Exactly one genuine CORTEX research record was subsequently approved; its persistence and controlled owner restart checks remain pending. Other owner record writes remain unauthorized. See [Owner market-data completion](OWNER_MARKET_DATA_COMPLETION_2026-10-11.md). The earlier 2026-10-08 evidence remains available separately.

## Exact remaining owner actions

**Completion update:** the owner executed the authorized procedure and supplied its report. All eleven migrations committed; 51 tables and 13 matching migration entries were verified, original record hashes preserved, and owner integrity passed. The retained encrypted backup hash was independently checked and the retained isolated restore was read live without mutation. See [Owner migration completion](OWNER_MIGRATION_COMPLETION_2026-10-11.md). No migration rerun is needed. Production pilot launch/browser reads passed through the authorized owner terminal. Separately approved owner market bootstrap and ingestion also passed the corrected read-only final verification. Actual OWNER_MAIN application acceptance remains pending; genuine personal/research record creation requires separate approval.

### Production authorization and pilot launch

On 2026-10-11 the direct command below was rejected by the tool's process-creation layer: `Rejected(... rejected: blocked by policy)`. It returned no Next.js runtime output. This proves an execution-policy rejection; it does **not** establish an NTFS denial, Windows execution-policy defect, invalid Next.js configuration, or an application crash. The review supplied no rule ID or more specific reason. The active session has approval policy `never`, so an approval escalation cannot be submitted here. No alternative production launcher was used after that rejection.

Run the existing production launcher from the owner's authorized Terminal 2 using [Production pilot launch and health procedure](PRODUCTION_PILOT_LAUNCH_2026-10-11.md). That procedure supplies a hidden pilot-password prompt, read-only database identity and integrity checks, ports 8001/3002, application state capture, and health/restart/shutdown checks. It does not recreate/start PostgreSQL or rerun migrations. The pilot profile uses MARKET_CORTEX_PILOT_DATABASE_URL; keep Terminal 1's owner connection private and unchanged.

The existing pilot database is market_cortex_pilot_test, role cortex_test, at 127.0.0.1:55432. The current cluster uses loopback trust authentication; no password is required or validated. Never substitute the owner URL/password. Production startup and browser reads passed against owner state application-6c0ac9a5fe5244a991628cc5553d2b32.json; shutdown/restart and saved-artifact recovery subsequently passed using current state application-84cd888863fc48a18410415605e441da.json. See [Production pilot validation results](PRODUCTION_PILOT_VALIDATION_RESULTS.json).

### Secure owner connection and read-only inspection

At the initial check, owner connection/backup variables were absent from the Codex process and persistent user/machine environment. The owner subsequently configured the connection in a private PowerShell process and supplied its local safe preflight report. That report confirms `market_cortex`, `::1:5432`, PostgreSQL 17.11, UTF8 and a read-only transaction. The pre-migration exit code 1 reflected 11 pending migrations, not authentication failure. That historical inventory contained 17 application tables. The completed authorized migration baseline had 51 tables, 13 matching migration entries and zero owner Parquets. The separately approved onboarding now has 1,825 observations and 65 verified owner Parquets with unchanged schema/migration rows. See the completion report for the post-migration evidence; do not rerun the migration procedure.

For future configuration or a fresh deployment session, use hidden input and save only the safe preflight result (the current owner has already completed this step):

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$env:MARKET_CORTEX_DATABASE_URL = [Net.NetworkCredential]::new('', (Read-Host 'Owner PostgreSQL DSN for market_cortex on loopback 5432' -AsSecureString)).Password
.\.venv\Scripts\python.exe -m market_cortex.operations preflight --profile config/operations-owner.example.json --integrity | Set-Content -LiteralPath runtime/owner-preflight-current.json -Encoding utf8
Get-Content -LiteralPath runtime/owner-preflight-current.json
```

Do not paste the DSN into chat. A variable set in a separate terminal does not update an already-running Codex process. The safe report file can be inspected here; for subsequent authenticated work, launch the authorized process with the local environment available. The report whitelists diagnostics and now records the **connected** database name, address, port, server version and `transaction_read_only=on`. Driver exception messages and credentials are excluded.

The [Owner migration proposal](OWNER_MIGRATION_PROPOSAL_2026-10-11.md) is historical and has been executed under explicit authorization. The retained encrypted backup, isolated recovery, eleven migrations and preservation checks passed; see [Owner migration completion](OWNER_MIGRATION_COMPLETION_2026-10-11.md). Keep the backup and recovery copy. The owner subsequently approved and executed [initial owner Binance onboarding](OWNER_BINANCE_ONBOARDING_PROPOSAL.md). The [approved initial commands](OWNER_BINANCE_ONBOARDING_APPROVED_COMMANDS.md) are historical and must not be rerun. [Read-only recovery](OWNER_ONBOARDING_READ_ONLY_RECOVERY.md) completed successfully. No owner journal, portfolio, thesis or synthetic research record was created; further owner record writes require fresh explicit authorization.

The application currently relies on the single Windows user and loopback/Origin boundaries; it does not implement an application login. PostgreSQL authentication must be configured and verified independently. Neither `owner_configured=true` nor an environment label proves authenticated owner deployment.

### Current validation and release condition

The latest October 11 validation refreshed the pilot to 5,070 bars (1,014 per pair) through October 10, the last closed UTC session at observation time. See PRODUCTION_PILOT_DATA_REFRESH_RESULTS.json for the current five successful jobs and manifest. Scheduling deduplicated its due slot; a repeated refresh stored zero bars and preserved the head. The PowerShell refresh wrapper returned IDLE after finding those completed jobs. Task Scheduler construction passed `-WhatIf`; no task was registered or logon run claimed. A separate local terminal's process environment is not automatically inherited by Task Scheduler.

See `MARKET_CORTEX_V1_OPERATIONAL_READINESS.md` and the new `DEPLOYMENT_*_RESULTS.json` files for current recovery, API, security and regression results. Preserve the original `OPERATIONAL_*` evidence. Per this milestone's release condition, leave this continuation uncommitted and create no operational tag while mandatory owner/production gates are blocked. Nothing is pushed.

## Prerequisites and profiles

- Windows; Python 3.12 and the existing `.venv`; Node.js and installed workstation dependencies; PostgreSQL 17 client tools and an available UTF8 database.
- Canonical checkout: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`.
- PostgreSQL application credentials belong only in environment variables. Never put them in profile JSON, Git, task arguments, screenshots or chat.
- Owner data: `C:\MarketCortexData`; the owner-executed read-only report confirms `market_cortex` on loopback 5432, 51 application tables, 13 unchanged migration entries, preserved baseline metadata, 1,825 observations and 65 verified referenced Parquets. See the owner market-data completion report.
- Profiles are explicit: `config/operations-owner.example.json`, `operations-pilot.example.json`, `operations-development.example.json`. They contain environment labels, an environment-variable name, data directory and refresh settings, **no DSN**.
- Pilot and development require a database name ending `_test` and a data directory outside the owner root and its ancestors/descendants. Owner requires a non-test database and exactly `C:\MarketCortexData`. The deployment profile accepts loopback connections only and rejects service/search-path overrides. There is no owner-to-pilot fallback.
- The workstation shows the backend environment. The System & Lineage refresh panel shows **latest catalog operations**, independently of pinned historical research.

Start in PowerShell:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$env:PATH = 'C:\Program Files\PostgreSQL\17\bin;' + $env:PATH
```

## Owner preflight and authorization

Set the owner DSN locally using hidden input, then perform read-only inspection:

```powershell
$env:MARKET_CORTEX_DATABASE_URL = [Net.NetworkCredential]::new('', (Read-Host 'Owner PostgreSQL DSN' -AsSecureString)).Password
.\.venv\Scripts\python.exe -m market_cortex.operations preflight --profile config/operations-owner.example.json --integrity
```

Preflight performs a read-only transaction, reports the actual connected identity, verifies UTF8 and migration checksums/pending migrations, and with --integrity reports application table counts plus referenced Parquet integrity even when later migrations are pending. It does not create the database, apply migrations, reset a schema, delete files or seed histories. Missing configuration/connectivity produces a failed preflight and startup stops.

Before owner writes: review the actual database/catalog and missing/mismatched files; obtain explicit owner authorization; make a retained encrypted backup if there is existing application state; verify recovery into a separate empty UTF8 catalog/root; review pending migration SQL. Never run test validators against the owner DSN. A new empty database also needs explicit approval before migration/bootstrap.

Owner schema migration and separately approved public market onboarding are complete; do not rerun either procedure. The retained backup/recovery of the migrated pre-ingestion baseline and successful production pilot validation preceded the owner market writes. Further owner record writes require fresh explicit authorization. A schema checksum conflict needs investigation, never editing migration history. No synthetic journals, portfolios, theses or predictions belong in the owner catalog.

## Build, start and shut down

Build from the workstation directory while its dev server is stopped:

```powershell
Push-Location apps/workstation
npm run typecheck
npm run build
Pop-Location
```

Production startup, when launch is authorized by the tool/OS controls:

```powershell
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json
```

The script checks the selected profile/database/migrations/data root and occupied ports, requires `.next/BUILD_ID` in production, launches the existing API and Next.js with **127.0.0.1** binding, verifies backend readiness/environment and the frontend HTTP response, and prints `http://127.0.0.1:3000` plus an exact shutdown command. Defaults are API 8765 and workstation 3000. It creates an owned process-state file and private local logs under ignored `runtime/`. It does not start/stop the owner's PostgreSQL Windows service or install a persistent application service.

**Earlier agent launch limitation:** direct `next start --hostname 127.0.0.1 --port 3002` was rejected again by automatic approval review with `blocked by policy`. Production build success does not establish production runtime success. This script's production branch has not been launched through another mechanism to evade that rejection. The owner subsequently launched the existing production script; actual pilot runtime/browser reads are validated. Approved market onboarding is now validated; owner readiness still requires actual OWNER_MAIN application checks.

Development is an explicit separate mode:

```powershell
# Dedicated pilot connection only; never substitute the owner DSN.
$env:MARKET_CORTEX_PILOT_DATABASE_URL = 'postgresql://cortex_test@127.0.0.1:55432/market_cortex_pilot_test'
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-pilot.example.json -ApiPort 8001 -FrontendPort 3002 -Development
```

The pilot cluster/data named in the example are this machine's existing validation resources. They must already be available. Development does not certify the production branch.

Copy the **exact shutdown command printed by startup**. `Stop-MarketCortex.ps1 -StateFile <printed runtime path>` checks process creation time, repository and command marker before stopping the app and its descendants. It refuses reused/unrelated PIDs, then removes only its process-state file. Windows process stopping is not a guarantee that an in-flight HTTP request finishes; committed evidence remains immutable and refresh jobs recover after lease expiry. Shut down between research runs when practical. PostgreSQL remains running unless its own operator stops it.

## Daily refresh and bounded backfill

First inspect the plan; this does not enqueue or fetch:

```powershell
.\.venv\Scripts\python.exe -m market_cortex.operations plan --profile config/operations-owner.example.json
```

After authorization for owner ingestion:

```powershell
.\.venv\Scripts\python.exe -m market_cortex.operations refresh --profile config/operations-owner.example.json --confirm-owner-writes
& .\scripts\Refresh-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ConfirmOwnerWrites
.\.venv\Scripts\python.exe -m market_cortex.operations status --profile config/operations-owner.example.json
```

`refresh` enqueues an immediate batch. The PowerShell script deduplicates the latest planned daily slot and processes at most 50 due jobs once, spaced 250 ms apart. The worker excludes the unfinished UTC day, loads existing venue-scoped mappings/calendars, fetches public Binance daily bars, and uses the existing immutable catalog/storage ingestion. Default overlap is three sessions to detect recent corrections. Missing identities stop planning; bootstrap must be reviewed first. No claim of exchange-wide or delisted coverage is made.

To backfill a bounded recent interval, use an aware UTC midnight start:

```powershell
.\.venv\Scripts\python.exe -m market_cortex.operations plan --profile config/operations-owner.example.json --start 2026-09-01T00:00:00+00:00
.\.venv\Scripts\python.exe -m market_cortex.operations refresh --profile config/operations-owner.example.json --start 2026-09-01T00:00:00+00:00 --confirm-owner-writes
```

Operational jobs end at today's UTC midnight and accept at most 366 days. Use the existing `sync-daily --provider binance --instrument-id <registered UUID> --start <UTC date> --end <UTC date>` for explicit older bounded windows after selecting the same authorized environment. Long gaps require chunked backfill; no silent truncation. These are calculations/source reads plus local persistence, never exchange writes.

Jobs expose state, attempts, error code, retry time and last completed result. Retryable provider/network failures retry at most three attempts with the existing capped exponential backoff. Permanent access/format failures become dead. Interrupted ingestion can leave an unreferenced durable file; `scan-storage` inventories it without deleting it. Duplicate retry preserves the committed head. Missed scheduling catches up the latest planned slot, not an unbounded job per missed day; a long outage still needs explicit backfill.

Freshness means the newest visible valid/corrected Binance raw P1D session equals yesterday's UTC date. This is closed daily-bar coverage, not a current quote, provider SLA, complete historical-gap verdict or derivative/news freshness promise. Empty, stale or missing evidence remains visible.

## Optional Windows schedule — disabled by default

Review the schedule without registering anything:

```powershell
& .\scripts\Register-MarketCortexRefresh.ps1 -Profile .\config\operations-owner.example.json -Enable -ConfirmOwnerWrites -WhatIf
```

Only after explicit owner approval, remove `-WhatIf` and confirm the registration prompt. The task is visible as `MarketCortex-ExplicitDailyRefresh`; current user/interactive/limited privileges; daily at profile `07:00` Asia/Kolkata, ten-minute retry checks, logon/missed-run recovery, no concurrent instances and a 30-minute process bound. This script requires Windows India Standard Time matching the profile. It refuses to overwrite an existing task. **No task was registered during validation.**

Scheduled processes must receive their profile's named DSN environment variable in that Windows user session; a variable set only in an old PowerShell process is not inherited by Task Scheduler. Configure this deliberately, with no DSN in task arguments or profile files. Test a manual one-shot run first. The task does not keep an API, frontend or model process running continuously.

Inspect or disable the explicit task:

```powershell
Get-ScheduledTask -TaskName 'MarketCortex-ExplicitDailyRefresh'
Get-ScheduledTaskInfo -TaskName 'MarketCortex-ExplicitDailyRefresh'
Disable-ScheduledTask -TaskName 'MarketCortex-ExplicitDailyRefresh'
```

Review the exact task before manually unregistering it. The optional schedule is a prepared pathway; actual registration/logon execution is deferred.

## India and US provider onboarding

Both remain **DEFERRED_NOT_CONFIGURED**. Missing credentials cause no authenticated request. Adapters retain fixed HTTPS GET endpoints, bounded pages/retries, safe code-only errors, typed daily-provider contracts and native-ID validation. Never supply broker order permissions to this research application.

| Provider | Required owner configuration and limits |
|---|---|
| Upstox | `UPSTOX_ACCESS_TOKEN` environment variable; verified `NSE_EQ\|...` native key, listing validity and XNSE calendar in Asia/Kolkata. V3 days/1 adapter, 181-day bounded chunks; actual account entitlement/history/candle interpretation and versioned holidays/early closes need validation. [Official historical V3 API](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/). |
| Alpaca | `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; verified venue/ticker validity and America/New_York regular-session calendar, including DST/holidays. Raw `1Day`; default IEX, SIP only when entitlement is verified. IEX is one exchange, not consolidated volume/coverage. [Official market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq). |

Official exchange/broker downloadable histories can be future ingestion sources only after rights, identifiers, calendar/timestamps and provenance are validated. No scraped substitute, assumed equity calendar or authenticated live result was added here. Binance public market-data-only endpoint and official archive exist; expansion must be controlled and verified per listing. [Binance primary documentation](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md).

## Local model — optional, not evaluated

This machine was inspected: approximately 32 GiB RAM and RTX 4060 Laptop GPU with 8188 MiB VRAM. No Ollama/LM Studio CLI, known installation or listening common runtime port was found; no model URL/ID is configured. **No genuine local-model evaluation occurred.** Deterministic CORTEX is available with ₹0 paid API spend.

An optional candidate pathway is Ollama's native Windows runtime plus a locally downloaded Qwen3:4b quantization. The candidate has documented instruction/tool and multilingual support; its library Q4_K_M download is about 2.5 GB. This suggests a feasible bounded evaluation on this GPU, **not demonstrated financial accuracy, latency or resource fit**. The current gateway only selects existing claim IDs; it does not grant a model tool execution or numerical fact generation.

Ask the owner before any runtime installation or multi-GB download. If approved, follow [Ollama Windows prerequisites](https://docs.ollama.com/windows), [local compatibility documentation](https://docs.ollama.com/api/openai-compatibility) and the [candidate model page](https://ollama.com/library/qwen3:4b). Keep the runtime loopback and avoid cloud model variants/sign-in. After installation and deliberate local download, configure:

```powershell
$env:MARKET_CORTEX_LOCAL_MODEL_URL = 'http://127.0.0.1:11434/v1'
$env:MARKET_CORTEX_LOCAL_MODEL_ID = 'qwen3:4b'
```

Restart the API. Evaluate actual saved research questions, relevant/irrelevant claim selection, contradictory evidence, injection attempts, strict JSON/known IDs, timeout/fallback, warm/cold latency, RAM/VRAM and citations. Reasoning text outside strict JSON is invalid and falls back; do not silently strip generated text into apparently valid evidence. Numeric explanations remain deterministic. The genuine model evaluation/approval remains a separate deferred gate.

## Retained backup and isolated restore

The existing encrypted bundle contains the PostgreSQL catalog (including research, theses, portfolios, journal/predictions, context, experiments/model JSON and personal memory) and all referenced Parquet history. It checks manifest/reference hashes under a consistent backup boundary. Research Desk notes, watchlists and view preferences stay in browser local storage and are **outside this bundle**, as the UI states; use the Journal for durable research that must survive catalog recovery. Owner configuration, source checkout/runtime binaries and a secret passphrase are **not a complete system-image backup**: preserve the Git release/source and non-secret owner configuration separately. No runtime installation is required to inspect stored model JSON; never restore executable pickle/joblib payloads.

For a retained owner backup, set the authorized owner environment, use PostgreSQL 17 tools and enter a passphrase locally. Store it separately from the encrypted bundle; losing it loses recovery. Use a new output filename (existing files are refused):

```powershell
$env:MARKET_CORTEX_BACKUP_PASSPHRASE = [Net.NetworkCredential]::new('', (Read-Host 'Backup passphrase' -AsSecureString)).Password
.\.venv\Scripts\python.exe -m market_cortex.cli backup --output C:\MarketCortexBackups\owner-2026-10-08.mcbackup
```

Before recovery, deliberately create a **different, empty UTF8** database with `TEMPLATE template0`; allocate a different empty data root. Set `MARKET_CORTEX_RESTORE_DATABASE_URL` to that isolated target. The CLI's current database URL stays the source identity for separation checks:

```powershell
.\.venv\Scripts\python.exe -m market_cortex.cli restore --input C:\MarketCortexBackups\owner-2026-10-08.mcbackup --data-root C:\MarketCortexRestoreDrill
Remove-Item Env:MARKET_CORTEX_BACKUP_PASSPHRASE
```

Restore rejects the source/same database, nonempty target schema/root, unsafe archive paths, wrong passphrase/checksums and incompatible database encoding. It does not use destructive `--clean`. A failed restore target may contain partial data: inspect it, use another fresh target, and keep the owner source intact. Verify table/reference counts, market/context heads, artifact hashes and representative frozen research/experiment/personal replay before planning owner cutover. An ephemeral validation drill is not a retained backup schedule.

## Troubleshooting and privacy

| Signal | Action |
|---|---|
| DATABASE_NOT_CONFIGURED / unavailable | Set the correct profile variable locally; verify PostgreSQL service/port/authentication. Never silently use pilot. |
| Pending/changed migrations | Review actual schema, create a retained backup and obtain owner authorization before applying SQL. |
| PORT_IN_USE | Identify the process; choose explicit other loopback ports. Do not kill unrelated services. |
| PRODUCTION_BUILD_REQUIRED | Stop dev, typecheck/build, then retry only if launch is authorized. |
| Approval rejection | Record exact action/reason; resolve authorization through normal controls. Do not evade it using another launcher. |
| Stale/unknown/missing data | Inspect jobs, mappings/calendar, UTC closed sessions and last success; use explicit bounded refresh/backfill. Never substitute zeros/prices. |
| Dead/retryable refresh job | Read its safe code/attempts. Correct access/configuration first; an immediate `refresh` creates a new visible batch. No unbounded automatic retries. |
| Missing/corrupt artifact | Stop affected research; preserve evidence, inspect `scan-storage`, recover from an isolated verified backup. Never rewrite historical manifest references. |
| Model unavailable/invalid | Deterministic fallback; inspect runtime configuration/timeout/strict JSON. No paid API is required. |
| INSUFFICIENT_HISTORY | Enter legitimate owner research through authorized owner UI/API workflows. Pilot/synthetic records remain excluded; no inferred habits are manufactured. |
| Browser/backend restart | Refresh/reopen the stored artifact or context; verify IDs and environment. Some unsaved forms are transient. |

Use same-origin browser proxy and loopback only. API/dispatcher/schema allowlists forbid arbitrary SQL/shell/code and broker writes. Host checks defend local DNS rebinding; foreign/null browser origins are rejected by the backend; proxy write Origin must match the incoming loopback Host. CORS access is not enabled for external origins. Local CLI/server requests without Origin remain allowed. This is protection against browser-origin attacks, not authentication against malicious programs or an administrator on this Windows account.

Keep ignored logs, profile/root permissions, backup keys and genuine personal exports private. A repository under OneDrive can sync non-ignored/local files outside the machine; review Windows folder synchronization/storage deliberately. The application itself does not upload owner history or use a cloud model. Do not assume filesystem/cloud-sync behavior is enforced by the app.

## Owner acceptance checklist

Complete authorized owner connection/inspection → retained backup and isolated recovery where existing state exists → migration/bootstrap → authorized production start → verify OWNER_MAIN, market freshness and a chart → research/citations → risk/Quant → genuine journal/thesis/prediction/mission/portfolio/preference workflow → reopen/replay → shutdown/restart/recovery. Keep personal history **INSUFFICIENT_HISTORY** until eligible records support it.

All architecture phases remain implemented. Supported operational evidence is the five-pair Binance pilot. India/US live onboarding, full-market coverage, prospective profitable edge and genuine model/owner deployment are separate gates. Prior momentum temporal OOS remains **−7.82%, N=82; no supported profitable edge**.
