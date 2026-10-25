# Proposed owner Binance daily refresh — disabled

Prepared 2026-10-11. **No scheduled task is registered and no owner refresh writes have been executed in this work.** Approval must cover the exact schedule, symbols, correction window and recovery behavior below. Current owner backup verification should pass first.

## Proposed scope

| Setting | Proposal |
|---|---|
| Destination | Existing OWNER_MAIN `market_cortex`, loopback 5432; `C:\MarketCortexData` |
| Pairs | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT; existing identities only |
| Frequency | Daily 07:00 Asia/Kolkata = 01:30 UTC, 90 minutes after UTC day close |
| Data | Binance public spot, raw P1D; no orders, brokers, paid sources or FX conversion |
| Range | UTC midnight latest accepted session minus two days, through today's UTC midnight exclusive |
| Normal run | Three prior sessions checked for corrections plus one newly closed session per pair; about 20 returned candles total |
| Recovery | Fetch missed sessions since latest persisted day with the same overlap; stop if range exceeds 366 days |
| Retry | At most 3 durable attempts/job, each transport call at most 3 tries; bounded backoff, 600-second lease |
| Windows | Current user, interactive logon, limited privilege; daily and logon triggers; repeat every 10 minutes; StartWhenAvailable; IgnoreNew overlaps |
| Process bounds | Up to 50 ready work items / 20 minutes per invocation; scheduler timeout 30 minutes |

The proposed profile is `config/operations-owner-refresh.proposed.json`. Existing historical bootstrap is not used. Missing owner history stops planning. A missed schedule creates only the most recent due slot, not a separate historical-redownload job for every missed day. Repetition normally sees completed jobs and performs no provider redownload.

Authorized scheduling would permit writes only to the established refresh jobs, source-batch/provenance records, observations/revisions, dataset files/manifests/members/head, outbox and quarantine diagnostics, plus new immutable market Parquets and local receipts. Existing five identities are read, not bootstrapped again. Research, portfolios, journals, preferences, predictions, theses and migration history are outside this proposal. Duplicate-only source fetches can still record source-batch/job evidence even though they publish no new market manifest.

## Deterministic guarantees and limitations

The established queue stores an idempotency key per environment/database/data-root/slot/symbol; duplicate scheduling returns the same job. Accepted duplicate candles do not publish another manifest. Changed source observations create immutable revisions/Parquets; earlier pinned/as-of reads remain reproducible. Every source batch retains provider/fetch time/response hashes and lineage. The Windows `r+b` fsync fix remains intact.

Empty responses or absence of the latest closed session cannot mark a job DONE. Quarantined input leaves diagnostic evidence and marks the job dead. Permanent access/input failures stop after one attempt. Retryable errors stop at three; an expired third lease is dead rather than reclaimed forever. Interrupted ingestion can commit immutable evidence before job completion; retry uses existing fingerprints and preserves that evidence. No rollback/reset is attempted.

Corrections older than the three-day overlap are not automatically detected. Large gaps, earlier historical repair, new pairs and provider changes require a separately reviewed scope. Freshness is a latest-session check, not proof that all historical sessions are present; coverage diagnostics remain separate. The local process clock must be correct. A sleeping/offline machine cannot guarantee a 07:00 refresh; StartWhenAvailable/logon catches up. Interactive tasks run only while the owner is logged in. No wake/unattended service/autologin is installed.

## Private Windows connection and approval gate

The original terminal-only owner URL cannot be inherited reliably by Task Scheduler. Do not place a password in task arguments, scripts, logs, profile JSON or machine/user environment. Prepared `Save-OwnerRefreshConnection.ps1` first verifies actual owner identity read-only and then creates a **new** current-user Windows DPAPI encrypted file under `%LOCALAPPDATA%\MarketCortex\Secrets`; never the repository/OneDrive. Only that user/machine context can decrypt it. The runner loads the file for its child processes and restores the previous process environment on exit.

**After explicit approval**, the owner would run in Terminal 1:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
$taskConnectionFile = & .\scripts\Save-OwnerRefreshConnection.ps1
& .\scripts\Register-MarketCortexRefresh.ps1 `
    -Profile .\config\operations-owner-refresh.proposed.json `
    -ConnectionFile $taskConnectionFile -Enable -ConfirmOwnerWrites
```

This block is a proposal, not authorization. It is not executed. Registration refuses an existing task; no replacement/deletion is automatic. It requires the Windows India timezone. Registration's confirmation displays the concrete task. First execution and logon/retry recovery must then be validated in the actual owner environment before calling the schedule reliable in production.

## Freshness and failure inspection — read-only

Available now in the configured owner terminal:

```powershell
.\.venv\Scripts\python.exe -m market_cortex.operations plan --profile config/operations-owner-refresh.proposed.json
.\.venv\Scripts\python.exe -m market_cortex.operations status --profile config/operations-owner-refresh.proposed.json
```

Reports show all five symbols, including IDENTITY_UNAVAILABLE / DATA_UNAVAILABLE rather than silently dropping missing instruments; STALE/FRESH and expected prior UTC session; durable attempts/error codes/results. Each executed runner writes a unique `runtime\refresh-<uuid>.json` receipt and returns failure for incomplete freshness, failed jobs or work limits. Inspect dead/ready jobs and receipt before intervention. Same-slot dead jobs are not silently resurrected. A following day's new slot is a new bounded attempt; manual requeue/repair requires owner review.

To stop future scheduled writes after enablement, the owner may disable the exact task in Task Scheduler; keep its receipts and committed market history. No automatic deletion of the encrypted connection or data is implemented.

## Acceptance remaining

Disposable regressions cover UTC overlap/ranges, due-slot deduplication, interrupted ingestion, permanent/transient failure, missing scope, empty responses and expired-lease caps. Prepared PowerShell scripts parse successfully. Actual task registration, DPAPI loading by Task Scheduler, owner refresh and Windows logon recovery remain **NOT_ENABLED_PENDING_EXPLICIT_AUTHORIZATION**. No current-state owner acceptance baseline is silently edited to accommodate future writes.
