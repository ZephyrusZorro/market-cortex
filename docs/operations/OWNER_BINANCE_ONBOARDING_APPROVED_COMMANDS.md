# Approved owner Binance onboarding — 2026-10-11

**Historical execution procedure: the initial run committed all 1,825 bars and completed refresh, then stopped on a timezone-dependent migration-row hash guard. Do not rerun this initial procedure. Use OWNER_ONBOARDING_READ_ONLY_RECOVERY.md. Further owner record writes require fresh explicit authorization.**

The owner explicitly approved the scope in OWNER_BINANCE_ONBOARDING_PROPOSAL.md. Production pilot startup, browser validation, controlled shutdown/restart and saved-artifact recovery passed. Owner market data remains uninitialized until this procedure actually succeeds. No migration rerun is included.

## Terminal 1: execute the approved procedure

Use the original owner terminal containing MARKET_CORTEX_DATABASE_URL. The configured variable has not reached Codex; this owner-executed step is required. Leave Terminal 2 and its isolated pilot connection unchanged.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\scripts\Invoke-OwnerBinanceOnboarding.ps1
```

The wrapper asks through hidden prompts for a matching backup passphrase of at least 16 characters if none is configured. **Retain that passphrase securely outside the repository**, separately from the encrypted file. It never displays it, passes it on a command line, or saves it in the report. The wrapper restores its prior passphrase/PATH environment after execution.

## Guarded sequence

1. Read-only identity, inspected post-migration state, 51-table empty-market baseline, thirteen checksums, fixed owner root and approved closed-session date checks. Unexpected records/root/schema/identity stop before writes.
2. Retain a unique encrypted fully migrated catalog backup under C:\MarketCortexBackups. The original pre-schema backup is untouched.
3. Create only a fresh UTF8 recovery database named mc_owner_market_<UUID>_test on the existing isolated port 55432 and a unique C:\MarketCortexRestoreDrills\owner-market-<UUID> directory. No existing database is reset, dropped or overwritten. No cluster is created or restarted.
4. Restore that specific backup and compare recovered schema, all counts, record hashes, ledger and head; verify integrity and retained encrypted-file SHA. Recheck the source before any market writes. Both backup and recovery copy are retained on success or failure.
5. Bootstrap the five approved public Binance identities with provider-native provenance. Fetch only 2025-10-11 inclusive–2026-10-11 exclusive using the existing daily adapter and immutable catalog. Require 365 accepted sessions per pair; stop on missing/quarantined evidence and preserve partial state.
6. Prove pre-ingestion as-of returns no backdated knowledge; freeze the new manifest/cutoff and per-pair bar hashes. Repeat the same range to check duplicates/head stability. Unexpected provider revisions are retained and reported, never overwritten or hidden.
7. Run one explicit incremental refresh batch with the existing correction overlap. Verify pinned replay, owner integrity, unchanged migration history and unrelated table counts. No scheduler, synthetic records, personal beliefs, model installation or application launch is performed.

The exact coverage is frozen. If the UTC closed-session date changes before execution, the runner stops rather than silently extending the approved range.

## Result and failure handling

The command prints a safe JSON summary and absolute `runtime\owner-onboarding-<UUID>\report.json` path. Send that report path back for inspection. Successful data status is **VALIDATED_OWNER_MARKET_DATA**, not OWNER_READY; actual OWNER_MAIN production application/research acceptance remains separate.

If it stops, preserve the backup, recovery copy, report and any registered identities/immutable data. Do not rerun blindly, reset the owner, restore over it, or attempt an unverified rollback. The agent will inspect the recorded phase and partial state before proposing recovery.

Runner validation: six tests passed against fresh disposable test catalogs, including successful encrypted recovery and a failed restore retaining the backup with the source unchanged. No actual owner execution is claimed by those tests.
