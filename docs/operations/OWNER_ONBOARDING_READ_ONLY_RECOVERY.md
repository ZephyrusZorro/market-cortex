# Owner onboarding verification recovery — 2026-10-11

The initial owner run stopped at MIGRATION_HISTORY_CHANGED after committing five identities, 1,825 daily observations and completing all five incremental jobs. It must not be restarted. Its original report remains unchanged at runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/report.json.

## Findings independently checked

- The owner lake contains 65 Parquets and 1,825 physical rows; every content hash matches its immutable filename.
- The retained encrypted pre-ingestion backup is 112,693 bytes. Its SHA-256 matches the owner receipt. The retained isolated recovery copy still matches the fully migrated pre-ingestion schema, all counts and record hashes: 51 tables, 13 migrations.
- Unchanged migration rows on that retained copy hash as a10a7e8897bdfcc2830386d1ad8151fe22c6a6b7302468677e4c8893f3fd3093 under UTC, matching the owner baseline. Under Asia/Kolkata they hash as 639655e40806f863c96fd8132ffe4ff098543a536f330ef45aca9b7b27c67e3c. Only transaction-local timestamp formatting changed; no rows were modified.
- The baseline snapshot sets UTC, but the former final guard did not. PostgreSQL converts applied_at (timestamptz) to session-timezone text inside to_jsonb. The comparison therefore falsely reported a migration-history change.
- The fix canonicalizes the complete migration-row hash to UTC while preserving migration IDs, count, checksums and original applied_at values in the integrity check. Nine tests pass, including real checksum and applied_at changes remaining rejected.

The owner subsequently executed the read-only diagnostic below. The inspected receipt `runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/verification-7c13d8d2c4534941a72e39e258d6249d.json` reports **VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY**. All 13 migration IDs/checksums, the full UTC row hash and schema fingerprint match; all five pinned bar hashes, 1,825 observations, 65 Parquets and five completed refresh jobs pass. The retained backup hash matches. No owner records were written during recovery. See [Verified owner data completion](OWNER_MARKET_DATA_COMPLETION_2026-10-11.md).

## Executed read-only Terminal 1 command (historical)

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
.\.venv\Scripts\python.exe -m market_cortex.owner_onboarding --verify-existing '.\runtime\owner-onboarding-20473f58dfda42659c60bcf6668b12bb\report.json'
```

This requires only the existing owner connection. It asks for no backup passphrase and issues READ ONLY transactions, SELECTs and transaction-local settings. It does not bootstrap, ingest, enqueue jobs, migrate, restore, reset or edit owner records.

It checks actual owner identity; all migration names/checksums/counts; default-timezone and canonical UTC row hashes; the full schema fingerprint; all table counts; unchanged unrelated records; existing completed refresh jobs; storage checksums; frozen bar hashes and as-of availability. It appends a unique verification-<UUID>.json beside the original report and prints that path. Repeating this verification makes no database changes.

The receipt has been inspected; no rerun is required. No ingestion retry or owner database repair is needed. Further owner database writes require explicit authorization. Successful data verification does not establish OWNER_READY until the actual owner production application is validated. The next exact application command is in the completion report linked above.
