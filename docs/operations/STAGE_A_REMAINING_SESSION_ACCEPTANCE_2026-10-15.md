# Remaining finite Stage A session acceptance

Execution notes for the implementation engineer; **no routine manual diagnostics are requested from the owner**. Both captures are already explicitly authorized. No scheduled wake-up, continuous collector or automatic retries of failed operations are registered. Continue when an active interaction coincides with the relevant session; do not claim future autonomous execution has been scheduled.

## Current evidence and admission

Candidate 3019/8678 restarted successfully. Nine production historical charts, all seven stored history hashes, request ledger, performance and both isolated restorations passed. Current source: 14,534,128 bytes of 512 MiB. Provider GET admissions remain history/comparison 14, metadata 0, stream authorization 0. Original Binance and IEX finite captures are stopped; current live subscription count is zero.

Fresh Indian observations are required for RELIANCE/INFY on both NSE and BSE. The original approved capture is 120 seconds, maximum 200,000 events, one provider socket at a time, maximum five retries and 64 MiB capacity reserve. Official feed `marketInfo.segmentStatus` must confirm NORMAL_OPEN for both NSE_EQ and BSE_EQ; each native listing must have fresh observations with two or more distinct timestamps. Conservative admission: weekday 09:20–15:25 Asia/Kolkata. Do not infer holiday/session state from weekday alone.

The separately authorized supplemental IEX capture is one 90-second observation for AAPL/SPY/QQQ, at most 200,000 additional events and a 64 MiB reserve within 512 MiB. It permits **zero additional REST/historical/metadata requests**. Conservative admission: weekday 09:35–15:55 America/New_York, with actual fresh event proof required. At the resumed check (October 14 20:03:30 UTC), this window had closed; no supplemental operation was started or admission consumed. Timezone conversion handles daylight saving. An open-clock window does not prove a nonholiday session.

## Finite capture commands — engineer executed during admission only

Run from `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`. Use the current-user DPAPI files below through the secure wrapper only. Never print decrypted values, inspect another process's environment or transfer the private owner database URL. The wrapper clears owner/pilot connections and restores temporary provider environment variables.

Indian capture:

```powershell
& .\scripts\Invoke-StageAAcceptance.ps1 `
  -CandidateReceipt '.\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-candidate.json' `
  -OwnerProtectionReport '.\runtime\owner-protection-2a833c19b082431183e1feb580f6aba7\report.json' `
  -SourceProtectionReport '.\runtime\stage-a-source-protection-95948c2cc4a94bc5803b1b58784954aa.json' `
  -Operation upstox `
  -UpstoxCredentialFile 'C:\Users\faris\AppData\Local\MarketCortex\Secrets\upstox-b08d8c411dde4967b9efb5e9a8c30ef8.dpapi'
```

Supplemental IEX:

```powershell
& .\scripts\Invoke-StageAAcceptance.ps1 `
  -CandidateReceipt '.\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-candidate.json' `
  -OwnerProtectionReport '.\runtime\owner-protection-2a833c19b082431183e1feb580f6aba7\report.json' `
  -SourceProtectionReport '.\runtime\stage-a-source-protection-95948c2cc4a94bc5803b1b58784954aa.json' `
  -Operation alpaca-ui-90 `
  -AlpacaCredentialFile 'C:\Users\faris\AppData\Local\MarketCortex\Secrets\alpaca-44401d783e314bfaaa3e9e9ac2f14940.dpapi'
```

The frozen viewer/build is unchanged; the supplemental operation is a separate reviewed addendum with its code hash recorded in immutable source metadata. Original capture markers and failures remain intact. Do not invoke `history`, `binance` or original `alpaca` again. Any failed capture keeps its admission/partial evidence and requires investigation rather than a blind retry.

## Concurrent browser observation

Immediately after admitting each finite capture, run the real clean browser observer concurrently using the existing isolated Playwright runtime. This starts a disposable browser only, not an application or feed; it permits only local candidate UI requests. Use `--provider upstox` or `--provider alpaca` and a **new unique** `--output runtime/…json`.

```powershell
& 'C:\Users\faris\AppData\Local\Temp\mc-browser-benchmark-7769e087a7a341ee98b73a2397a7e8fa\Scripts\python.exe' `
  -m scripts.observe_stage_a_live_browser --provider upstox --output 'NEW_UNIQUE_INDIAN_BROWSER_RECEIPT'
```

For the US addendum substitute `--provider alpaca`. Observe all four Indian identities (~64 seconds) / three US identities (~48 seconds) while the socket is active. Exact native ID, exchange, timestamp, receipt time, last trade and bid/ask must match the API response that drove the DOM, with state LIVE. A stale snapshot or authentication-only response cannot pass. Inspect actual bounded worker receipt and clean browser result; do not infer exchange streaming from a moving chart alone.

## Close and protect

1. Confirm workers ended, connected=false, no collector locks and durable GET usage within limits. IEX supplemental usage must be unchanged. Retained snapshots must become explicitly STALE after shutdown.
2. Validate immutable manifests/lineage and bounded storage; no historical gap recovery is permitted by these captures. Capture records gaps as unrecoverable tick intervals instead of fabricating observations.
3. Create another **new retained** source backup and isolated restore via `Protect-StageASource.ps1 -CandidateReceipt … -GenerateDpapiRecoveryKey`; retain all earlier bundles/keys/roots. DPAPI source keys are Windows-profile-bound, not portable passphrases. Use the latest receipt in the read-only `scripts.verify_stage_a_recovery` audit.
4. Rerun production-browser/performance only to establish the final populated-cache acceptance. Verify current owner recovery evidence, original tag/build and candidate code hashes, pinned histories, no owner/pilot writes, no collector/schedule and request/storage totals.
5. Produce a final hash-bound combined receipt only if every mandatory gate passed. Present that evidence and the separate cutover/recovery procedure, then request **final owner cutover approval**. Do not execute Stage B/C or new production deployment under conditional Stage A authorization.

Only actual expired/rejected provider credentials or execution-review rejection may require owner involvement. If the existing API/UI has stopped, request the minimum candidate startup action using the prepared receipt; do not bypass the previous server-startup rejection.
