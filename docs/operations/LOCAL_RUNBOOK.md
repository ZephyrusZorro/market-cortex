# Local Windows operation — Phase 1 development

Run these commands in PowerShell from the extracted repository root. This is a **research-only** API; it has no order routes. Use Python 3.12 if your Python 3.14 environment lacks compatible dependency wheels.

## Install and verify

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
Copy-Item config\owner.example.yaml config\owner.yaml
$env:MARKET_CORTEX_DATA_ROOT = 'C:\MarketCortexData'
.\.venv\Scripts\python.exe scripts\market_cortex.py doctor
```

Edit the ignored `config\owner.yaml` for local preferences. Provider keys and database passwords go **only** in environment variables; they are never written to owner YAML or JSON reports.

## PostgreSQL

Install local PostgreSQL with its client tools (`pg_dump`, `pg_restore`). Create a dedicated database and owner role through the local PostgreSQL installer or administration UI. Enter the connection URL without echoing it in your terminal history:

```powershell
$db = Read-Host 'Local PostgreSQL URL' -AsSecureString
$env:MARKET_CORTEX_DATABASE_URL = [System.Net.NetworkCredential]::new('', $db).Password
Remove-Variable db
.\.venv\Scripts\python.exe scripts\market_cortex.py migrate
```

The migration is checksum-locked. If a committed SQL migration changes after it has run, the command stops; create a new numbered migration instead.

## Public crypto pilot

Bootstrap only currently trading native Binance pairs and sample their first daily kline. This registers local UUID identities; sampled first dates are lower bounds for observed history, not proof of complete historical coverage.

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py bootstrap-crypto
```

Copy one returned `instrument_id`, then request a bounded past window. Use UTC offsets and an end-exclusive interval. This call writes only to the **local** database and Parquet directory. Network calls are HTTPS GET market-data requests.

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py sync-daily --provider binance --instrument-id 'PASTE-UUID-HERE' --start '2025-01-01T00:00:00+00:00' --end '2025-02-01T00:00:00+00:00'
.\.venv\Scripts\python.exe scripts\market_cortex.py scan-storage
.\.venv\Scripts\python.exe scripts\market_cortex.py serve
```

Open `http://127.0.0.1:8765/docs` or `http://127.0.0.1:8765/api/v1/health`. The bar route needs `instrument_id`, `from`, `to`, and optionally `as_of`, `manifest_id`, `provider_id` and `adjustment_basis`. Save the manifest ID returned by sync when reproducing a result. `inspect-manifest --manifest-id <UUID>` checks hashes and summarizes physical rows with DuckDB; correction revisions count as separate physical rows.

The Upstox and Alpaca adapters cannot sync until venue-scoped native mappings and versioned exchange calendars are registered. The Phase 0.6 probe supplies evidence for those mappings. The project does not invent US/India holidays or guess a ticker's canonical identity.

## Phase 2 deterministic analytics

Use a manifest ID returned by a completed sync. The date window supplies the warm-up history; SMA200 needs at least 200 complete sessions in it. `as_of` is an availability cutoff. Omit it for a current local view, or specify it for reproducible research. A missing or stale source remains explicit in the result.

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py compute-feature --name sma --instrument-id 'PASTE-LOCAL-UUID' --from 2025-09-01 --to 2026-10-01 --provider-id binance --parameters '{"period":200}' --manifest-id 'PASTE-PINNED-MANIFEST'
.\.venv\Scripts\python.exe scripts\market_cortex.py compute-market-state --history-from 2025-09-01 --evaluation-date 2026-10-01 --manifest-id 'PASTE-PINNED-MANIFEST'
```

The local API adds `GET /api/v1/features`, `/api/v1/features/compute`, `/api/v1/features/series`, `/api/v1/comparisons`, `/api/v1/market-state`, and `/api/v1/regime`. See [exact indicator and state rules](../analytics/PHASE_2_ANALYTICS.md). An optional read-only validation utility, `scripts\validate_phase2_pilot.py`, checks the five-pair snapshot, pinned feature warm-up, API responses, storage inventory and local timings against an already ingested catalog. It writes a redacted report to the requested path and makes no provider request.

## Read-only source probes

```powershell
.\.venv\Scripts\python.exe scripts\probe_sources.py --run --output data\probes\phase_0_6_local.json
```

Upstox uses `UPSTOX_ACCESS_TOKEN`; Alpaca uses `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. Set them in this PowerShell process when available. Missing values produce `SKIPPED_NOT_CONFIGURED`, while Binance public requests still run. Inspect the redacted report before sharing it. Do not share keys or a database URL.

## Encrypted backup and isolated restore

Stop workers and keep a separate backup volume. The backup command obtains an ingestion lock, makes a PostgreSQL custom dump, includes every referenced Parquet file, records SHA-256 hashes, and encrypts the archive with AES-256-GCM. The passphrase is entered into the process environment without terminal echo. A temporary plaintext staging directory is used during the operation and removed afterward; use an encrypted disk for the temporary directory if local disk confidentiality is required.

```powershell
$pw = Read-Host 'Backup passphrase (16+ characters)' -AsSecureString
$env:MARKET_CORTEX_BACKUP_PASSPHRASE = [System.Net.NetworkCredential]::new('', $pw).Password
Remove-Variable pw
.\.venv\Scripts\python.exe scripts\market_cortex.py backup --output 'E:\MarketCortexBackups\pilot.mcbackup'
```

Create a **new empty PostgreSQL database** for the restore drill, set `MARKET_CORTEX_RESTORE_DATABASE_URL` to its URL in the process environment, and choose an empty folder on a separate path. Restore refuses the live database and nonempty data folder. The database and files are checked against the backup manifest, but the drill is not complete until a pinned as-of query matches the original system.

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py restore --input 'E:\MarketCortexBackups\pilot.mcbackup' --data-root 'E:\MarketCortexRestoreData'
```

If a database operation fails, the CLI emits a code/type, not the driver error text, to avoid exposing the connection URL. Record the failing command and nonsecret status when requesting help.
