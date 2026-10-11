# Owner migration proposal — 2026-10-11

**Status: COMPLETED and verified from the owner-executed report on 2026-10-11 at 15:08:49 Asia/Kolkata.** Continue from local `9de5113`. The owner has granted authorization for the exact backup, isolated rehearsal, 11 schema migrations and preservation verification. See [Migration completion report](OWNER_MIGRATION_COMPLETION_2026-10-11.md). The approved commands are retained as a historical procedure; no rerun is required. This proposal is based on the refreshed local `runtime/owner-preflight-current.json`, executed by the owner in the PowerShell process holding the secret environment variable. Codex inspected the JSON; it did not connect to the owner catalog directly.

## Inspected pre-upgrade baseline

- Connection succeeds: database `market_cortex`, IPv6 loopback `::1`, port **5432**, PostgreSQL **17.11**, **UTF8**, `transaction_read_only=on`.
- Profile is **OWNER_MAIN**, timezone **Asia/Kolkata**, currency **INR**. The database URL exists in the owner's terminal; it remains unavailable in the current Codex process. No credential has been logged or copied into this proposal.
- The first two migrations are recorded with matching checksums. **11 migrations, 0003–0013, are pending.** No applied migration checksum changed.
- `C:\MarketCortexData` exists. Storage inventory: **0 referenced, 0 missing, 0 corrupt, 0 unreferenced, 0 staged artifacts**. No deletion was performed.
- The inventory covers the active application schema. It does not assert that unrelated database schemas are empty; the backup must capture the whole database.
- Exit code 1 is the pending-schema readiness gate. **It is not an authentication failure.** The original diagnostic skipped integrity when migrations were pending; the corrected implementation now reports it independently and passed its regression tests.

| Existing table | Rows |
|---|---:|
| app_locks | 0 |
| calendar_sessions | 0 |
| consumer_receipts | 0 |
| dataset_files | 0 |
| dataset_head | 1 |
| dataset_manifests | 0 |
| identifier_mappings | 0 |
| instruments | 0 |
| jobs | 0 |
| manifest_members | 0 |
| observations | 0 |
| outbox | 0 |
| provider_capabilities | 0 |
| quarantine | 0 |
| schema_migrations | 2 |
| source_batches | 0 |
| venues | 0 |

These are application metadata rows; the inspected schema has no market observations or instrument mappings. No owner journals, portfolios, theses, research runs, predictions or personalization fixtures will be invented to populate the new tables.

## Reviewed schema changes

| Migration | Change |
|---|---|
| 0003_cortex_research.sql | Saved CORTEX research table and indexes. |
| 0004_opportunity_theses.sql | Opportunity candidates, theses and immutable thesis versions. |
| 0005_portfolio_risk.sql | Portfolios, versions and recorded risk snapshots. |
| 0006_journal_learning.sql | Journal/revisions, prediction records/revisions/evaluations and edge library; adds a foreign key between newly created prediction tables. |
| 0007_quant_lab.sql | Quant artifacts and edge evidence. |
| 0008_quant_jobs.sql | Adds nullable `jobs.result_ref` referencing Quant artifacts. |
| 0009_quant_summaries.sql | Adds a derived `quant_artifacts.summary` column and populates summaries from immutable payloads. In the inspected owner schema, that artifact table does not yet exist and will be created empty. |
| 0010_context_intelligence.sql | Context facts, files, manifests, membership, head and snapshots. |
| 0011_research_missions.sql | Research missions and checkpoints. |
| 0012_personalization.sql | Personal records, versions and snapshots. |
| 0013_experimental_research.sql | Experimental research tables/index; replaces the Quant artifact-kind CHECK constraint with a wider allowed-kind set. No artifact payload or historical price is rewritten. |

Total: **34 new tables**, giving **51 application tables** including the 17 already present. There are no new-table name collisions in the inspected schema. The reviewed files contain no `DROP TABLE`, `DROP DATABASE`, `TRUNCATE` or `DELETE FROM`. The constraint replacement in 0013 is explicitly part of the proposed schema change. Exact migration SHA-256 values and statements are recorded in `DEPLOYMENT_OWNER_MIGRATION_PLAN.json`.

The existing migration runner serializes migrations with advisory locks, verifies applied checksums, and applies pending SQL plus ledger entries in a transaction. Failures roll back that transaction. Do not edit old migration files, clear their ledger, suppress SQL errors, or retry with a reset.

## Completed independent rehearsal

`scripts/validate_owner_upgrade.py` created two fresh random `_test` databases on the isolated PostgreSQL 17 validation cluster. It never connected to owner state. It installed only 0001/0002, inserted one explicitly synthetic bar, made an encrypted backup, restored it into the second database, and applied exactly 0003–0013 there.

Results: all old table counts preserved (except 11 added migration-ledger entries), exact bar JSON preserved, manifest unchanged, **34 new tables empty**, second migration run performed no changes, and original synthetic source remained at its old schema. Disposable databases, temporary files and ephemeral key were cleaned. See `DEPLOYMENT_UPGRADE_REHEARSAL_RESULTS.json`. This rehearsal does not replace the required backup and recovery verification of the real owner catalog.

## Proposed backup-first procedure after authorization

1. **Freeze the reviewed scope.** Run from the owner's configured terminal. Verify the source identity still matches `market_cortex` / loopback 5432, confirm no application workers are writing, and check migration checksums against the proposal. Verify the connected role's required schema/table permissions through read-only privilege checks; successful SELECT access alone does not prove ALTER/CREATE rights. Recheck automatically at execution time; no further manual preflight is needed just to review this plan.
2. **Retain an encrypted baseline.** Use a unique new file under `C:\MarketCortexBackups`, with a passphrase supplied through hidden local input and retained separately by the owner. Preserve the entire catalog, including any unrelated schemas. Current application inventory expects zero Parquet artifacts. Existing backup filenames must never be overwritten.
3. **Restore into a new isolated target.** Allocate a fresh random `_test` database on the **55432 validation cluster**, distinct from the owner and pilot databases, using `TEMPLATE template0 ENCODING UTF8`. Allocate a unique empty folder under `C:\MarketCortexRestoreDrills`. Explicitly create that empty folder before restore: a zero-Parquet backup otherwise has no files whose extraction would create it. Reject a nonempty destination. Never restore into `market_cortex`, its current root, or the pilot catalog.
4. **Verify the actual owner backup before upgrading anything.** Match all 17 application table counts, two migration checksums, the head/reference state, storage inventory and dump authentication/checksum. The backup uses pg_dump's consistent database snapshot; application migration/ingestion coordination uses existing advisory locks. No owner sample records are required.
5. **Rehearse the pending upgrade on that actual restored copy.** Apply the same 11 checksum-locked migrations to the isolated restore. Confirm all original rows/head/reference values persist, 51 application tables exist, new application tables remain empty, all 13 migration checksums match, integrity passes, and another migration invocation is a no-op. Stop on any mismatch. Keep the baseline backup and restore target available for diagnosis.
6. **Apply only the approved owner schema upgrade.** With backup/recovery verified and explicit authorization received, execute the existing `migrate` command against the original owner URL in its local terminal. Do not bootstrap market data or create personal records as part of this schema-only approval.
7. **Verify owner state read-only.** Confirm the same connected identity, 13 migrations with no pending/changed entries, preserved original records, empty new domain tables, and a clean root inventory. Run owner preflight with `--integrity`; it should return VALIDATED. Record only safe diagnostics.
8. **Resume the remaining deployment gates separately.** Obtain production launch authorization; validate the production browser against PILOT_TEST first. Then approve a concrete Binance identity/history bootstrap scope and genuine owner-created records before owner onboarding. Keep provider/model limitations and empty-history states visible.

Proposed baseline backup commands (execute only within the approved procedure):

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$env:PATH = 'C:\Program Files\PostgreSQL\17\bin;' + $env:PATH
$env:MARKET_CORTEX_ENVIRONMENT = 'OWNER_MAIN'
$env:MARKET_CORTEX_DATA_ROOT = 'C:\MarketCortexData'
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$taskBackup = Join-Path 'C:\MarketCortexBackups' "owner-before-v1-$taskStamp.mcbackup"
$env:MARKET_CORTEX_BACKUP_PASSPHRASE = [Net.NetworkCredential]::new('', (Read-Host 'Retained backup passphrase (at least 16 characters)' -AsSecureString)).Password
.\.venv\Scripts\python.exe -m market_cortex.cli backup --output $taskBackup
if ($LASTEXITCODE -ne 0) { throw 'STOP: baseline backup failed' }
```

Keep the existing owner database URL in the same local environment; never echo it, place it in arguments, or copy it to a report. The CLI backup function is compatible with the first-two-migration schema, as demonstrated by the isolated rehearsal. It captures a complete database dump and any referenced artifacts without modifying catalog rows.

The restore target's URL must be supplied through `MARKET_CORTEX_RESTORE_DATABASE_URL`; the source URL remains the original owner identity for separation checks. Choose the fresh target only after confirming the separate cluster and empty target/root. Review actual restore results before issuing the later owner migration command:

```powershell
# Only after authorized baseline backup + isolated restore/rehearsal have passed:
.\.venv\Scripts\python.exe -m market_cortex.cli migrate
if ($LASTEXITCODE -ne 0) { throw 'STOP: migration failed; preserve diagnostics and baseline' }
.\.venv\Scripts\python.exe -m market_cortex.operations preflight --profile config/operations-owner.example.json --integrity
```

Clear the process backup-passphrase variable when finished. The owner must retain the passphrase securely outside Git/logs and separately from the bundle; an ephemeral test key is not adequate for retained recovery.

## Recovery and stop conditions

- If backup authentication, restore, migration rehearsal or any preserved count/hash check fails, stop before owner migrations; preserve original state and the baseline.
- If owner migration SQL fails, allow the transaction rollback and inspect safe error classification. Do not run reset, drop, truncate, ledger-clearing, or `pg_restore --clean` commands.
- If post-upgrade application validation fails after commit, stop the application and restore the retained pre-upgrade backup into **another fresh isolated database/root**. Verify it before proposing any cutover. Obtain separate approval for a connection/root cutover; never overwrite the original owner catalog as an automatic rollback.
- Owner profiles currently require the fixed owner root; a future recovery cutover must explicitly account for that constraint rather than relabeling a test root as owner. Preserve original files until the recovery decision is reviewed.

## Remaining approvals and external actions

**Owner authorization granted on 2026-10-11:** retained baseline backup, isolated recovery/rehearsal, then the exact 11 non-destructive owner schema migrations above, followed by read-only verification. Personal records and market bootstrap have their own reviewable scope. The approved procedure subsequently applied the eleven migrations; the original owner-executed report and retained backup are preserved.

**Separate production blocker:** the direct Next.js production launch is rejected by Codex process-creation review (`blocked by policy`), and this session offers no approval escalation. Resolve normal execution authorization or perform the documented direct launch in an authorized owner terminal. No alternate launcher or disabled security control was used. The production browser and OWNER_READY gate remain blocked until actually validated.
