# Current owner backup protection

Prepared 2026-10-11. Operational tag `v1.0.1-operational` and commit `cfe696d` are preserved. These changes are local and unreleased. Neither owner nor pilot application needs to restart for this procedure.

## Completed owner acceptance

**VALIDATED_CURRENT_OWNER_BACKUP_AND_ISOLATED_RESTORE**, owner-executed on 2026-10-11 and independently inspected at 22:12 IST (16:42 UTC).

- Retained bundle: `C:\MarketCortexBackups\owner-current-dab5dbc0b5884373b56868c183cc4131.mcbackup`; 1,198,133 bytes.
- SHA-256: `1cb01c848c4fc7ac94d28e533ff506596df917e31518192bdcc5c5ed9c93641a`.
- Recovery: `mc_protection_dab5dbc0b5884373b56868c183cc4131_test`, isolated port 55432, UTF8; `C:\MarketCortexRestoreDrills\owner-current-dab5dbc0b5884373b56868c183cc4131`.
- Receipt: `runtime\owner-protection-51cf820416c74937aa786795c14c3d43\report.json`; phase COMPLETE, source unchanged, no owner record writes or migrations.
- Independent receipt: same directory, `independent-read-only-verification.json`. Read-only recovery queries matched all 51 table counts/full row hashes, 13 migration rows/checksums and schema/head. All 65 physical Parquets matched catalog hashes and row counts (1,825 total); saved research payload and six replay hashes matched. The owner receipt also proved all five original pinned bar hashes (365 sessions each).
- Both prior owner bundles were independently rehashed and remain unchanged. Owner/pilot applications remain running with distinct manifests.

The command below was executed successfully. **Do not rerun this completed snapshot blindly**: return to a freshly inspected scope for any later state. This retained populated bundle covers the accepted data/research state on 2026-10-11, not future daily refreshes or owner records.

## Audit and scope

The prior retained bundles predate the 1,825 market bars and the saved research run. They remain valid historical baselines, but cannot recover today's populated state. Preserve both bundles and their recovery databases.

The backup now selects **all** dataset/context file references, rather than only current-head ancestry. It uses an exported PostgreSQL snapshot for the dump, full table fingerprints and artifact list. Research writes concurrent with a generic backup cannot create a mismatch between its dump and fingerprints. The owner procedure additionally stops if the inspected state changes before/during recovery.

The new encrypted bundle covers all 51 application tables, 13 full migration rows/checksums, five canonical identities/mappings, source observations/revisions, batches, manifests/head, durable jobs/outbox and the single approved research payload. It includes all 65 referenced immutable Parquets and encrypted configuration metadata: timezone, currencies, preferences/privacy/budgets and release identity. Unknown config keys, environment variables, passwords and passphrases are excluded. Software and dependencies remain in the repository; this is a database/data recovery bundle, not a machine image.

AES-256-GCM authenticates ciphertext; scrypt derives the key from a minimum 16-character passphrase with random salt. Publication is exclusive and atomic. Decryption refuses an existing plaintext destination. PostgreSQL restore uses one transaction, no `--clean`, into a new empty UTF8 database. Loopback aliases of the live database are rejected. The format remains MCBACKUP1 and older retained bundles remain readable; older bundles lack the new complete-row fingerprint verification.

## Owner execution — approved backup scope only

Run in **Terminal 1**, which already holds the private owner connection. Do not copy the URL into the pilot terminal or chat. Avoid submitting research or doing any owner writes during this snapshot/recovery check.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\scripts\Invoke-OwnerProtection.ps1
```

Hidden matching prompts are used unless a backup passphrase is already available in that terminal. Keep the passphrase in a private password manager/offline record outside this repository. The wrapper restores the terminal's original passphrase/PATH variables afterward.

New outputs are unique and retained:

- `C:\MarketCortexBackups\owner-current-<uuid>.mcbackup`
- New database `mc_protection_<uuid>_test` on the existing isolated PostgreSQL 17 cluster, port 55432. The existing admin connection uses local trust; it is not proof of password authentication.
- `C:\MarketCortexRestoreDrills\owner-current-<uuid>`
- `runtime\owner-protection-<uuid>\report.json`

The owner source uses read-only transactions and a temporary advisory lock. No owner row changes, migrations, bootstrap, ingestion, job enqueue, scheduler registration or application startup occur. Creating/restoring the new recovery database is the only database write scope. The pilot database/data remain untouched. The recovery target uses UTF8 even if the cluster's admin database uses SQL_ASCII.

Success requires exact source/restore schema, counts and UTC-normalized row fingerprints for **every table**, unchanged full migration history/head, authenticated bundle/file hashes, storage inventory with no missing/corrupt/unreferenced/staged files, five pinned daily replay hashes, and replay of the existing research ID with six matching evidence hashes. The source must still match the accepted inventory and the bundle hash must remain unchanged.

On any future failure: retain all output and the partial recovery, return the printed report path and stop. Do not rerun blindly, delete evidence, drop any existing database, restore over owner or attempt rollback. A new current-owner backup claim requires its corresponding receipt to pass and be inspected.

## Recovery and retention

This is a restore drill, not a cutover. Any future recovery uses a new empty database/root, the retained matching passphrase, the corresponding code/config and the same fingerprint/replay checks. Review any proposed cutover separately. Do not rerun migrations on a restored database with its preserved ledger. Keep all earlier owner and pilot backups; no rotation/deletion is enabled.

`C:` retention protects against logical corruption, not loss of the entire disk. A separately retained encrypted copy on an owner-chosen second device is still needed for disk-loss recovery; no external destination has been selected or copied to.

## Evidence

Disposable populated-catalog regressions verify Unicode research rows, non-head artifacts, a concurrent research insert excluded from the exported snapshot, GCM tamper rejection before restore, refusal to overwrite plaintext, failed-restore retention and unchanged source records. Live owner-terminal and independent read-only recovery evidence are recorded separately above. See `POST_RELEASE_VALIDATION_RESULTS.json` for regression and live acceptance results.
