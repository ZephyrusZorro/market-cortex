# Approved owner migration command — 2026-10-11

The owner explicitly authorized the retained encrypted backup, isolated recovery and rehearsal, migrations **0003–0013**, and preservation checks on October 11. **COMPLETED at 15:08:49 Asia/Kolkata on 2026-10-11.** The owner-executed report is `runtime/owner-migration-99c3aca053254bc1a956496a431e5569/report.json`; its outcome and retained backup were verified by Codex. See `OWNER_MIGRATION_COMPLETION_2026-10-11.md` for the final state, exact retained recovery identity and remaining deployment gates.

The following commands document the completed procedure. **Do not rerun them against the upgraded owner catalog**: the baseline guard intentionally refuses the changed migration state.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
& .\scripts\Invoke-OwnerMigration.ps1
```

The wrapper starts only the existing isolated PostgreSQL 17 validation cluster on loopback **55432** if needed, checks the process environment, and runs the approved procedure. It does not launch Next.js or alter owner PostgreSQL services. If no backup passphrase is already present locally, it asks for hidden input twice. Choose at least 16 characters and retain that passphrase securely outside the repository and separately from the encrypted file. Do not paste it or the database URL into chat.

The Python runner verifies the actual isolated cluster's data directory/port, the OWNER_MAIN profile and fixed root, source database identity/version, all 17 inspected table counts, both original migration checksums, the empty dataset-head/reference state, storage integrity, required privileges, and the exact approved SQL hashes. It refuses uninspected tables in another schema, changed owner state or a modified plan. The original plan JSON remains an immutable reviewed artifact; its historical NOT_AUTHORIZED field is superseded by the owner's explicit authorization recorded here.

The guarded sequence is:

1. Reinspect live state read-only; stop on a material difference from the reviewed baseline.
2. Create a uniquely named retained AES-GCM encrypted bundle under `C:\MarketCortexBackups`. Existing filenames are never replaced.
3. Authenticate/decrypt and restore **that exact bundle** into a fresh random `mc_owner_restore_*_test` database (future name format; the actual original retained identity is recorded in the completion report) on the separate 55432 cluster and an empty unique directory under `C:\MarketCortexRestoreDrills`.
4. Verify exact table counts, original record hashes, schema/index/constraint definitions, migration checksums, head and storage against the live baseline. The current authorized baseline has zero Parquet files; the empty target directory is created explicitly.
5. Rehearse exactly the 11 pending migrations on the restored copy. Require 51 application tables, 13 matching migration entries, 34 empty new tables, preserved original record hashes/head, passing integrity, and a no-op second migration invocation.
6. Use the established migration runner on the owner database. Its transaction checks the baseline again under table locks, uses a five-second lock timeout, and compares the resulting schema/counts/checksums and original rows against the successful rehearsal **before commit**. An ordinary SQL or verification failure aborts that transaction through the established transaction manager.
7. Verify the committed owner state read-only, including the same database identity, preserved records, unchanged empty root, clean integrity and unchanged encrypted-backup SHA-256.

Only approved schema changes and their ledger entries are added to owner state. No market bootstrap, pilot/synthetic import, journal/portfolio/thesis/personal record creation, database reset, history edits, automatic rollback/cutover, or backup deletion is provided by this command. The backup format restores data/schema with `--no-owner --no-privileges`; the isolated copy's role/permissions differ from live permissions, which the procedure does not modify. This is database recovery evidence, not a backup of PostgreSQL server roles or secret configuration.

The command prints only safe status, phase, commit flag, encrypted-backup path and report path. The report is saved under:

```text
runtime\owner-migration-<unique-id>\report.json
```

The encrypted bundle, isolated database and restore directory are **retained on success or failure**. The temporary reviewed SQL copies and unencrypted working dump are cleared by the existing scoped temporary-file mechanisms. The wrapper restores its prior PATH/passphrase environment and clears its local passphrase variables; it does not clear the owner's database variable.

If the procedure stops, inspect the safe report and share its path with Codex. Do not reset the owner database, rerun migrations blindly, overwrite it with a restore, or delete the retained bundle. A connection failure near commit can leave the commit outcome unconfirmed; the runner records this uncertainty and performs no attempted rollback. Read-only inspection is required before any next operation.

Successful output must be **VALIDATED_OWNER_SCHEMA_MIGRATION**, with `owner_migration_committed=true`, retained-backup hash, verified recovery/rehearsal, and passing final owner preflight. A test receipt or prepared command is insufficient evidence of actual owner migration. Give Codex only the printed report path so the outcome can be inspected without exposing credentials.

Production startup remains a separate execution-policy blocker. This procedure does not establish OWNER_READY, install scheduling, configure an LLM, or create an operational release tag.
