# Independent chart/browser acceptance — owner terminal handoff

**Current acceptance:** independent production frontend 3018/API 8677 passed actual browser, provider-value, real-event, replay and performance checks after owner startup on 2026-10-14. See `PRODUCTION_MARKET_VALIDATION_2026-10-14.md`. The commands below are retained for future isolated startup; no further startup is currently required.

Automatic execution review rejected the agent's independent API/development-UI startup. No alternate launcher was attempted. The owner subsequently started the independent API and development UI. Clean-browser BTC/ETH historical and real-price acceptance passed on 2026-10-14; see `AUTONOMOUS_MARKET_VALIDATION_2026-10-14.md`. Production-build runtime measurement requires the separate startup below.

Use two **new** terminals if the independent environment is offline. No private database credentials are required. Preserve OWNER_MAIN (8765/3000) and PILOT_TEST (8001/3002) in their existing state. Their ports were offline after the PC reboot at the latest inspection; this procedure does not start them. The copied frontend uses a separate temporary directory; the owner production `.next` directory is not rebuilt.

## Terminal 3: independent API

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
if (Get-NetTCPConnection -State Listen -LocalPort 8677,3017 -ErrorAction SilentlyContinue) {
    throw 'INDEPENDENT_TEST_PORT_IN_USE; stop and report'
}
Remove-Item Env:MARKET_CORTEX_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:MARKET_CORTEX_PILOT_DATABASE_URL -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe -m market_cortex.market_data_cli --root '.\runtime\multi-market-foundation-0c306424e0eb40148568db23fade99bc' serve --port 8677
```

This removes variables only from the new terminal. It does not change Windows user/machine environment or Terminal 1/2.

## Terminal 4: copied development workstation

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
$taskSandbox = (Get-Content -LiteralPath '.\runtime\multi-market-ui-sandbox-path.txt' -Raw).Trim()
if (-not (Test-Path -LiteralPath (Join-Path $taskSandbox 'app\markets\page.tsx'))) {
    throw 'PREPARED_UI_SANDBOX_MISSING; stop and report'
}
Remove-Item Env:MARKET_CORTEX_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:MARKET_CORTEX_PILOT_DATABASE_URL -ErrorAction SilentlyContinue
$env:MARKET_CORTEX_MARKET_DATA_API_URL = 'http://127.0.0.1:8677'
$env:MARKET_CORTEX_API_URL = 'http://127.0.0.1:8677'
Set-Location -LiteralPath $taskSandbox
node .\node_modules\next\dist\bin\next dev --webpack --hostname 127.0.0.1 --port 3017
```

Both proxy variables point to the independent data API. Original research API routes therefore cannot reach the owner application from this copied workstation. Webpack is used because Turbopack rejects the prepared external node_modules junction; the isolated Webpack build passes.

Open `http://127.0.0.1:3017/markets`. Exact active BTCUSDT is selected initially; ETHUSDT has a shortcut. Active/listed is the default catalog filter, with other statuses available explicitly. The chart renders actual source candles and volume, with accessible zoom/pan controls. All eight BTC timeframes and ETH daily/minute history were browser tested and compared with public Binance responses. UTC history requests wait ten seconds after a close boundary to avoid premature REST mirror observations. Earlier affected independent observations are reconciled through revisions, preserving as-of evidence.

Bounded validation collectors are stopped after their evidence capture. STALE with a retained last quote is correct when no collector is connected. Browser prices poll the local API every two seconds; the backend receives Binance mini-ticker/kline WebSocket events. HMR is development tooling, not the market feed. Alpaca has no local catalog until its credentialed probe succeeds. Upstox metadata is available but authenticated history remains deferred without its token. No manual DevTools diagnostics are required from the owner.

Selecting an instrument may issue bounded public/history GET requests and create source-cache evidence in the independent archive only. It does not write owner or pilot records. No collector or scheduler is started by the page. End these test servers with Ctrl+C in their respective terminals after acceptance; do not stop the owner/pilot terminals.

## Separate production-build runtime validation

The build is prepared in the unique temporary directory named by `runtime/multi-market-production-sandbox-path.txt`. Existing development and owner/pilot build directories are preserved. Only the owner performs server startup because of the execution-review rejection:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
& .\scripts\Start-IndependentProductionValidation.ps1
```

This serves the built UI on 3018 and uses the existing independent API on 8677. Keep it running for agent-controlled browser, HTTP and process measurements. No DB credentials, migration, ingestion job, order endpoint or scheduled task is involved. When read-side code changes, restart only Terminal 3's existing `serve --port 8677` process to load the verified implementation. Do not restart owner or pilot applications.
