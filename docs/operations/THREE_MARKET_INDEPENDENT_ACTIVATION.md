# Optional independent broker-browser acceptance activation

Prepared 2026-10-14. This is a minimum owner-executed startup handoff for **independent browser validation**, not an owner integration/import command. Agent server startup was previously rejected by automatic execution review; that rejection is respected.

**Completed:** owner restarted 8677 on the combined capped archive; process/root/catalog identity and the production 3018 broker charts have been verified. See `THREE_MARKET_BROWSER_ACCEPTANCE_2026-10-14.md`. No further restart is needed for this completed cached-browser acceptance; the original command below is retained as procedure history.

The current independent API on 8677 still reads its original archive and has no Alpaca catalog. Both authenticated broker probes live in separate archives. The new byte-exact three-provider review bundle has been tested through the API in-process; the running browser has not yet been switched to it. This must be disclosed before claiming three-market workstation acceptance.

If the owner elects to continue independent browser acceptance, in **Terminal 3 only**, stop its existing independent API with Ctrl+C, then run:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
& .\.venv\Scripts\python.exe -m market_cortex.market_data_cli --root '.\runtime\three-market-capped-review-2026-10-14' serve --port 8677
```

Leave the existing production frontend on 3018 unchanged; it already proxies to 8677. No owner/pilot process, database, migration, credential or schedule is involved. The new archive has all three catalogs and genuine cached BTC/ETH/RELIANCE/AAPL daily observations. Broker credentials are intentionally absent from this command; no fresh broker history or stream can be claimed without a separately scoped secure invocation. Selecting an uncached broker instrument must return NOT_CONFIGURED/UNAVAILABLE rather than substitute data.

The implementation engineer performs the clean-browser tests and source comparisons. The owner need not inspect DevTools, capture messages or diagnose errors. This optional independent startup is not approval A/B/C in `THREE_MARKET_OWNER_INTEGRATION_PROPOSAL.md`; those owner scopes remain disabled.
