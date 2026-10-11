# MARKET CORTEX v1 — Operational readiness

## Final owner operational acceptance — 2026-10-11

**OWNER_READY for the supported Binance spot daily research scope.** The actual OWNER_MAIN production application passed startup, all sixteen browser navigation panes plus advanced laboratory reads, APIs, controlled stop/restart, exact post-restart owner inventory and persisted genuine research replay. Current owner application state: runtime/application-a9c83bf65f414697b8cda568c8b868a3.json; workstation http://127.0.0.1:3000, API http://127.0.0.1:8765. The pilot remains running separately. The complete UTC migration-row hash, schema fingerprint and all table counts are unchanged except the separately approved one CORTEX row; all 65 Parquets and six research evidence hashes match. No ingestion or migration retry occurred.

| Area | Final status |
|---|---|
| Architecture | VALIDATED_EXISTING_TWELVE_PHASES |
| Production runtime | VALIDATED_OWNER_AND_PILOT_START_STOP_RESTART |
| Pilot environment | VALIDATED_ISOLATED |
| Owner database | VALIDATED_51_TABLES_13_UNCHANGED_MIGRATIONS |
| Owner market data | VALIDATED_1825_RAW_BARS_65_PARQUETS_FIVE_PAIRS |
| Daily refresh | VALIDATED_FIVE_COMPLETED_OWNER_JOBS; SCHEDULER_DISABLED |
| Local AI | VALIDATED_DETERMINISTIC_FALLBACK; OPTIONAL_LLM_NOT_CONFIGURED |
| India/US coverage | DEFERRED_NOT_CONFIGURED; MAPPINGS_CALENDARS_ENTITLEMENTS_REQUIRED |
| Full operational readiness | OWNER_READY_SUPPORTED_BINANCE_DAILY_RESEARCH |

Full backend regression: 361 tests + 13 subtests; subsequent onboarding/helper updates have nine and three focused passing tests. Frontend 54-test recheck, typecheck and production build passed. No claim of one combined 373-test full run. Original failed receipts and all earlier phase evidence remain intact. The retained owner backups/recovery copies are pre-schema and pre-ingestion baselines, **not a current populated-owner backup**. No supported profitable edge, execution, application login or broad market coverage is claimed. Scheduler registration and further agent-driven owner record writes remain unapproved. The earlier automatic execution-review rejection remains an agent-launch restriction; every production launch/restart was owner-executed through the existing scripts.

Authoritative current evidence: [Owner operational acceptance](../operations/OWNER_OPERATIONAL_ACCEPTANCE_2026-10-11.md), OWNER_OPERATIONAL_ACCEPTANCE_RESULTS.json, OWNER_PRODUCTION_RESTART_RESULTS.json and OWNER_PRODUCTION_RESTART_BROWSER_QA.json. All sections below are dated historical checkpoints superseded by this final acceptance. Local release identity: annotated v1.0.1-operational tag after committing this verified snapshot; no push.

## Owner acceptance invocation correction — 2026-10-11

The owner production inventory failed at import before any verifier query or application stop/restart. Direct file execution selected scripts/market_cortex.py instead of the package. The corrected invocation is `.\.venv\Scripts\python.exe -m scripts.verify_owner_production` from the repository root. The old direct-file invocation now fails early with an explicit instruction. Three focused import/read-only/count regression tests pass (1.59 s); actual module execution with credentials removed reached DATABASE_NOT_CONFIGURED as expected, without package shadowing or database access. That negative configuration check is not a live owner inventory result. The single approved owner research row is already saved/replayed; no additional research submission is authorized. OWNER_READY remains pending actual successful inventory and owner restart. See OWNER_PRODUCTION_IMPORT_CORRECTION_RESULTS.json and OWNER_PRODUCTION_RESTART_ACCEPTANCE.md.

## Production validation update — 2026-10-11

The owner launched the existing combined production script in the authorized pilot terminal. Actual process identity, production state, current BUILD_ID, direct FastAPI health, proxied health and the selected database were checked. The previous agent execution-policy rejection remains an agent-launch restriction; it no longer means the owner-started production application is unvalidated. **OWNER_READY remains pending saved owner research and controlled owner restart acceptance.** The owner launched application-6898cdce55e34ef1ac077e05bdd55b35.json in production on 8765/3000. Direct/proxied health, actual owner identity, all five frozen bar hashes and coverage, request boundaries, all sixteen navigation panes and the advanced laboratory read view passed. No browser errors/warnings. The single genuine research record is now explicitly authorized; its persistence/restart check is in progress. Controlled pilot shutdown/restart and artifact recovery passed. The authorized owner onboarding subsequently committed 1,825 real Binance bars, 65 Parquets and completed five refresh jobs. A timezone-dependent final hash guard was corrected; the owner-executed read-only recovery verified unchanged schema, full migration rows and pinned data. No migration rerun, recovery record write, scheduler registration, release commit, tag or push occurred.

| Area | Current status | Evidence and remaining scope |
|---|---|---|
| Architecture | VALIDATED | Existing twelve-phase implementation; no new phase. |
| Production runtime | VALIDATED_PILOT_START_STOP_RESTART | Owner state application-6c0ac9a5fe5244a991628cc5553d2b32.json; production next start confirmed; both health endpoints ready; BUILD_ID K4ApJcYNA_48DSptxRH31. Controlled stop released both ports; new state application-84cd888863fc48a18410415605e441da.json has new owned PIDs and confirms production next start. |
| Production browser | VALIDATED_PILOT_READ_WORKFLOWS | All sixteen navigation panes plus Advanced Research Laboratory; 23 captured observations; candles/zoom, indicators/state, scanner, existing synthetic risk/journal/predictions, CORTEX/mission/Quant saved evidence and explicit source limits; no console errors/warnings. |
| Pilot environment | VALIDATED | Actual market_cortex_pilot_test at 127.0.0.1:55432; PILOT_TEST; 5,070 real daily bars, 1,014 sessions per pair through October 10. Existing loopback trust authentication does not validate a password. |
| Manifest/as-of | VALIDATED | Current head 5fda5a53-4bcd-4788-84a6-e84cf799a3da; earlier 8c66134e-2ad4-4359-bc2c-aa51c7c3e140 remains through October 9. Before-discovery cutoff clears later correlation values and reports unavailable evidence. |
| Owner database | VALIDATED_OWNER_READ_ONLY_RECEIPT | 51 tables / 13 matching migrations; UTC full-row hash and schema fingerprint unchanged; zero pending/changed migrations. Owner-executed recovery receipt inspected; no agent direct owner connection claimed. Both retained encrypted baselines and isolated recoveries preserved. |
| Owner market data | VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY | Five identities, 1,825 observations, five manifests and 65 immutable Parquets; zero quarantine or storage defects. All five frozen/as-of bar hashes match. Timestamp-format hash defect fixed without weakening migration checks; nine safety/tamper tests pass. No additional owner writes authorized. |
| Daily refresh | VALIDATED_PILOT_AND_OWNER | Pilot: one new bar and three duplicates per pair. Owner: five completed jobs, zero new bars and three duplicates each; all five owner pairs fresh through October 10 at verification time. Scheduler remains disabled. |
| Saved replay | VALIDATED_AFTER_PRODUCTION_RESTART | CORTEX hashes, mission replay VERIFIED, Quant result MATCH; completed ridge dataset/result MATCH through production API. Language is not re-generated. Same CORTEX, mission checkpoint 27, Quant and experimental IDs reopened after restart; hashes/dataset replay matched, and all 51 table counts remained unchanged. |
| Storage | VALIDATED | Selected spot manifest ancestry: 200 files / 5,070 rows. Whole catalog including contextual artifacts: 203 referenced files; no missing/corrupt/unreferenced/staged files. All 51 table counts unchanged since launch. |
| Security | VALIDATED_DECLARED_BOUNDARIES | Foreign Host reads and foreign-Origin POSTs rejected with 403 by API/proxy; proxy GET grants no CORS. Single-user loopback boundary; no application-login claim. |
| Regression | PASS | Full final backend: 361 tests + 13 subtests, no skips, one existing TestClient deprecation warning, 1,047.97 s. Ran against isolated clone/copy; disposable resources cleaned. Frontend recheck: 54 tests; typecheck pass. Initial two async wait failures did not reproduce; no assertion/timeout changes. |
| Local AI | DETERMINISTIC_FALLBACK_VALIDATED | Saved deterministic answers and citations work; local LLM remains not configured, optional. |
| India/US | DEFERRED_NOT_CONFIGURED | Upstox/Alpaca adapters retained; credentials and verified mappings/calendars/entitlements still required. |
| Full operational readiness | PENDING_OWNER_SAVED_RESEARCH_AND_RESTART | Owner market data, actual production startup and API/browser read views passed. Exactly one genuine CORTEX record is separately authorized; save/reopen/replay and owner restart acceptance remain. |

Research conclusions remain unchanged: no supported profitable edge; prior momentum temporal OOS −7.82%, N=82. Synthetic pilot records remain separate; genuine owner history is insufficient.

Current owner completion evidence: docs/operations/OWNER_MARKET_DATA_COMPLETION_2026-10-11.md and OWNER_MARKET_DATA_COMPLETION_RESULTS.json; original failure and successful read-only receipts preserved. Current pilot receipts: docs/operations/PRODUCTION_PILOT_VALIDATION_RESULTS.json, PRODUCTION_BROWSER_QA.json, PRODUCTION_API_CHECK_RESULTS.json, PRODUCTION_EXPERIMENT_REPLAY_RESULTS.json, PRODUCTION_PILOT_POST_BROWSER_PREFLIGHT.json, PRODUCTION_FULL_BACKEND_RESULTS.json and PRODUCTION_FRONTEND_CHECK_RESULTS.json. The owner executed the exact existing Stop/Start scripts without migrations or ingestion. PRODUCTION_RESTART_RESULTS.json and PRODUCTION_RESTART_BROWSER_QA.json record recovery. The current pilot application remains running at the owner’s request.

## Earlier deployment snapshot — 2026-10-11

Baseline: local commit `9de5113`. This earlier snapshot is superseded by the production validation update above; its evidence is retained as history. No Phase 13 or unrelated feature was added. **OWNER_READY remains BLOCKED**. No commit, release tag or push is made while the requested owner-readiness gates remain unresolved.

### Independent acceptance gates

| Gate | Status | Current evidence / remaining requirement |
|---|---|---|
| A. Production runtime launches | BLOCKED_EXECUTION_POLICY | Direct `next.cmd start --hostname 127.0.0.1 --port 3002` rejected before process creation: `blocked by policy`. No Next.js runtime output. Session approval policy is `never`; no escalation mechanism or alternate-launch attempt. |
| B. Production browser workflow | BLOCKED_BY_A | No production browser pass claimed. Prior development browser checks remain historical only. |
| C. Pilot end-to-end operation | VALIDATED_WITH_LIMITATIONS | Real PostgreSQL + Parquet + running FastAPI: chart/11 indicators/state/scan/CORTEX save/reopen/replay/risk/Quant/Intelligence/Journal/Research Lab. Frontend production runtime excluded. |
| D. Secure owner connection | VALIDATED_OWNER_TERMINAL_REPORT | Inspected the refreshed owner-executed local report: market_cortex, ::1:5432, PostgreSQL 17.11, UTF8, transaction_read_only=on. Credential remains confined to the owner terminal. Agent direct connection and application authentication remain unvalidated. |
| E. Owner migrations/data root | VALIDATED_OWNER_EXECUTED_REPORT | Owner committed 0003–0013 on October 11 at 15:08:49 Asia/Kolkata. 51 application tables, 13 matching migration entries, zero pending/changed checksums, 34 new tables empty; all original row hashes preserved. Owner integrity VALIDATED with zero referenced/missing/corrupt/unreferenced/staged artifacts. |
| F. Environment isolation | VALIDATED_WITH_LIMITATIONS | Pilot connected identity is market_cortex_pilot_test, PostgreSQL 17.11 on loopback 55432, UTF8, read-only preflight, checksums current. Owner-terminal identity is separately ::1:5432/market_cortex with the fixed owner root. Profile guard and synthetic/owner-link regressions; owner application startup remains unvalidated. |
| G. Safe refresh | VALIDATED_WITH_LIMITATIONS | 10 new closed daily bars, 15 recognized duplicates, zero quarantine; repeat zero stored/15 duplicates/head unchanged. Same-slot schedule IDs identical. Actual PowerShell refresh returns IDLE; Task Scheduler dry-run only, no registration/logon claim. |
| H. Backup/isolated recovery | VALIDATED_OWNER_AND_PILOT_RECOVERY | Actual pre-upgrade owner bundle retained (41,013 bytes); encrypted-file SHA independently matches. That specific bundle restored/rehearsed before owner commit; retained recovery copy independently read live with matching 51 tables, 13 migrations and original row hashes. Earlier pilot drill additionally verified 198 Parquets and research/model replay. No cutover performed. |
| I. Artifact persistence/replay | VALIDATED_WITH_LIMITATIONS | Saved CORTEX evidence survives graceful API shutdown/restart and replays exactly; accepted negative Quant/mission evidence retained. All restored-artifact replay checks passed. Genuine owner records untested. |
| J. Regression | VALIDATED_WITH_RECORDED_SCOPE | Full backend: 351 passed + 13 subtests, no skips, one existing warning, 595.96 s. Collection began before the final diagnostic fix; all 20 operational tests including both added cases passed against the final implementation (11.88 s). Frontend 54 tests, typecheck and production build pass. |
| K. No trading execution | VALIDATED | Existing provider transport issues GET only to fixed historical/context endpoints; no order adapter was added. Broker endpoint and arbitrary-tool rejection tests retained. |
| L. Limitations documented | VALIDATED | Upstox/Alpaca DEFERRED_NOT_CONFIGURED; verified mappings/calendars/entitlements still required. Local LLM optional; actual unavailable-endpoint deterministic fallback passed. No supported profitable edge or fabricated owner habits. |

### Owner schema migration and retained recovery completed

The authorized procedure completed on October 11 at **15:08:49 Asia/Kolkata**. The original owner-executed report remains unchanged under runtime/owner-migration-99c3aca053254bc1a956496a431e5569/report.json. The agent inspected that report, recomputed preservation and migration-file checksums, independently verified the retained encrypted file's SHA-256, and queried the retained isolated copy read-only. The source post-commit state is verified from the owner's report; no new direct owner connection is claimed.

All eleven migrations committed. Owner now has **51 application tables and 13 matching migration entries**. The original rows were preserved; 34 new tables are empty; the inspected owner data root and storage remain clean. Owner market bootstrap and genuine record creation remain unperformed because they were outside the migration authorization.

The retained pre-upgrade backup is 41,013 bytes; the retained recovery database is the successfully upgraded rehearsal copy. The original requested recovery name exceeded PostgreSQL's 63-byte limit and was truncated; its actual name is documented in the completion report. Its different database/port/root and all recovery checks were verified. Future name generation is shortened and checks actual-name equality; the existing retained copy was not renamed or deleted. After that fix, **35 affected tests passed**, no skips, one existing warning, 49.73 s. Tests cleaned only their disposable fixtures; the genuine retained recovery copy and user-started validation cluster remain available.

Current completion evidence: docs/operations/OWNER_MIGRATION_COMPLETION_2026-10-11.md and OWNER_MIGRATION_COMPLETION_RESULTS.json. The earlier runner-validation receipt remains a historical test record. No migration rerun is needed; no backup key or credential is requested again.

**OWNER_READY is still BLOCKED** by actual production runtime/browser validation and unfinished owner market-data/application onboarding. The production execution-policy rejection remains separate. No broker execution, synthetic owner history, recovery cutover, release commit, operational tag or push was added.

### What was resolved

- Pilot PostgreSQL startup initially omitted its `-p 55432 -h 127.0.0.1` options and attempted the occupied owner port. Correcting the startup configuration launched the dedicated pilot without changing owner services or database configuration.
- Preflight now reports the database's actual name, address, port, server version and read-only transaction state. After the owner supplied a failing report, fixed the skipped integrity check: pending later migrations no longer hide existing Parquet defects. Aggregate table counts are read inside the read-only transaction. Inspection failures retain CONNECTED_READ_ONLY and a safe error type rather than being mislabeled as connection failures. The owner DSN and raw driver exceptions remain excluded from output.
- Restore validation used a hardcoded 1,011-bar count from October 8. It now compares against the selected validated pilot evidence, preserving exact source/restored hashes as history grows. Both validation scripts accept separate output paths so prior evidence is preserved.
- Added bounded 429 recovery/exhaustion transport tests with a synthetic large Retry-After value. These do not create a real provider rate-limit incident or alter accepted financial implementations.

### Actual current observations

Validation date is **October 11 in Asia/Kolkata**. Raw evidence timestamps are UTC (October 10 around 20:23 onward). At that instant, October 9 is the last fully closed UTC daily session; October 10's candle was excluded.

Five-pair pilot: **5,065 bars, 1,013 sessions each**, 2024-01-01 through 2026-10-09. Previous head `a00facd3-9c92-4500-9bef-18f427d937d7` remains immutable; new head `8c66134e-2ad4-4359-bc2c-aa51c7c3e140`. Refresh creates five new manifests and total referenced Parquets become **198**, with no missing/corrupt/unreferenced/staged artifacts. Each pair reports FRESH under the closed-UTC-daily policy. Context derivatives/macro and unsupported sources retain their separate stale/partial/unknown classifications.

Saved real pilot CORTEX run `03f9f5b1-ab58-4898-96e9-765987da5005` reopened and replayed before and after API restart; all four evidence hashes match. Uvicorn printed `Application shutdown complete` on Ctrl+C, its port was released, and a new process passed health/environment checks. The terminal wrapper returns interrupt exit code 1; it is not described as a normal zero-exit termination. The production frontend and combined Windows launcher have not passed this test.

Real API reads additionally verified existing journals, theses, synthetic portfolios, Intelligence context/coverage, canonical momentum run `7017c9e9-ee90-5fc0-9101-2a5e4e660b62`, experimental results, and Research Lab report `800e1535-acd9-474d-9d7c-3a5ba45af4be`. Research remains INCONCLUSIVE / NO SUPPORTED EDGE, with prior momentum temporal OOS **-7.82%, N=82**. Genuine owner history remains N=0 in the pilot. Browser-like foreign/null Origin and untrusted Host POSTs returned 403.

### Exact remaining blockers and owner action

Production rejection originates in Codex's tool process-creation review. The supplied reason is only `blocked by policy`; no rule identifier is available. Because no application process started, this attempt provides no evidence of an OS permission or Next runtime defect. The authorized escalation workflow is unavailable under this session's `never` approval policy. The owner guide gives the original direct launch command for an authorized owner terminal and the exact pilot-only browser/restart checklist. No security controls were changed or disabled.

The owner configured the URL in a separate PowerShell terminal and ran preflight there. Both the initial and corrected reports were inspected directly. Connection succeeded; exit code 1 is caused by **11 unapplied migrations (0003–0013)**. The corrected report confirms 17 application tables with only two migration-ledger rows and one dataset-head row, plus zero market observations/mappings/artifacts and a clean root. This is the inspected application schema, not a claim that unrelated schemas are absent. The agent still cannot inherit that terminal's credential, and no credential was requested through chat. **No further manual preflight rerun is required to review this plan.**

The complete proposal is `docs/operations/OWNER_MIGRATION_PROPOSAL_2026-10-11.md`, with exact SQL checksums/statements in `DEPLOYMENT_OWNER_MIGRATION_PLAN.json`. It adds 34 tables and reviewed indexes/columns/constraints, with no table drops, truncation, record deletes or historical price rewrites. A synthetic two-migration baseline was actually encrypted, restored into a fresh test database, upgraded through all 11 files, and verified: existing rows, bar JSON and manifest preserved; 34 new tables empty; a second migrate run made no changes. This proves the upgrade path with synthetic data, not owner backup acceptance.

The owner explicitly authorized a retained encrypted baseline, isolated recovery/rehearsal of that actual baseline, then the exact schema upgrade and read-only verification on October 11. The owner subsequently executed the approved guarded command; the completed schema/recovery outcome is documented above. The approved command page is now a historical procedure and does not request another execution. The actual owner backup passphrase remains locally supplied/retained; do not substitute an ephemeral test key. The procedure creates the isolated empty restore directory explicitly, including for a zero-Parquet backup. The retained owner backup, isolated rehearsal and schema migration were subsequently completed. Owner bootstrap, record creation and cutover were not performed. Genuine owner-created records and owner production startup remain unfulfilled gates.

The single-user application has loopback and browser-origin controls, not an application login. Owner database authentication is not inferred from a profile label. Existing owner services remain running and owner files remain untouched. Upstox, Alpaca and a local LLM do not block this milestone.

Current evidence: `docs/operations/DEPLOYMENT_REFRESH_RESULTS.json`, `DEPLOYMENT_PILOT_RESULTS.json`, `DEPLOYMENT_API_RESULTS.json`, `DEPLOYMENT_RESTART_RESULTS.json`, `DEPLOYMENT_RESTORE_RESULTS.json`, `DEPLOYMENT_OWNER_PREFLIGHT_RESULTS.json`, `DEPLOYMENT_OWNER_MIGRATION_PLAN.json`, `DEPLOYMENT_UPGRADE_REHEARSAL_RESULTS.json`. Final regression/cleanup evidence is `DEPLOYMENT_ACCEPTANCE_RESULTS.json`. All original `OPERATIONAL_*` reports are retained.

Current encrypted pilot bundle size was **833,996,853 bytes**; backup took **90.185 s**, restore **221.299 s**, and restored ridge recomputation **7.808 s**. These are single local measurements, not a service guarantee. The ephemeral drill key and bundle were not retained as an owner backup. No recovery database named operational_restore_* remains. The full backend suite ran after this drill completed. Its collection preceded the two final diagnostic regression cases; the final 20-test operational suite independently covers those changes. No claim of a single 353-test full run is made. The API was stopped gracefully, its ports and production frontend port are free, all temporary rehearsal databases were cleaned, and the dedicated validation cluster was stopped after confirming zero other clients. Owner PostgreSQL services remained running; owner root still has zero entries. No schedule, commit, tag or push was created.

## Historical operational-hardening evidence — 2026-10-08


Milestone: operational hardening and owner deployment after Phase 12; **not Phase 13**. Date: 2026-10-08. Baseline: `932f4ec` / preserved annotated `phase12-v1.0.0`. Local work only; no push. The original twelve-phase exit evidence is preserved as a historical record.

## Decision and distinct achievements

| Achievement | Evidence-based status | Meaning |
|---|---|---|
| ARCHITECTURE_COMPLETE | VALIDATED | Phases 1–12 remain implemented; accepted Quant, mission, personalization and experiment fingerprints/evidence retained. |
| PILOT_OPERATIONAL | VALIDATED_WITH_LIMITATIONS | Explicit isolated pilot profile; fresh real Binance daily data; Windows development startup/recovery; full research workflow; actual encrypted recovery. Production runtime is excluded from this claim. |
| OWNER_READY | BLOCKED | Production launch remains rejected by automatic approval review. Owner connection/state/migration/deployment approval is absent. No owner deployment claim or completed operational-release tag. |
| FULL_MARKET_COVERAGE_READY | DEFERRED | Validated scope is Binance Pilot 5. India/US live authentication, verified mappings/calendars, broad/delisted coverage and missing advanced sources remain separate gates. |

**No supported profitable edge.** Prior momentum temporal OOS is unchanged: **−7.82%, N=82**. Phase 12 dependent-row model metrics and negative hypotheses remain unchanged. Spot refresh does not turn examined research into pristine prospective validation. Genuine owner history remains **INSUFFICIENT_HISTORY**, N=0 in the pilot.

## Prioritized readiness-gap matrix

| Priority / area | Status | Evidence / remaining gate |
|---|---|---|
| P0 Production launch | BLOCKED | Direct authorized retry of `next start --hostname 127.0.0.1 --port 3002` was rejected by automatic approval review: `blocked by policy`. No alternate production-launch mechanism was used to evade it. Production builds are a distinct gate. |
| P0 Owner environment | DEFERRED | Owner DSN not configured in this process. Main PostgreSQL Windows services run; owner root exists with zero entries. Main catalog contents, encoding/migrations/rights were not inferred from that directory. Owner preflight reports DATABASE_NOT_CONFIGURED and does not fall back. |
| P1 Windows launch/recovery | VALIDATED_WITH_LIMITATIONS | Profile preflight, port conflicts, hidden owned API/frontend processes, environment/health checks, local URL and ownership-checked shutdown. Development launch/shutdown/restart exercised; production branch prepared but blocked. |
| P1 Daily ingestion | VALIDATED | Actual Binance GET refresh: 20 new closed daily bars, 15 duplicates, zero quarantine; five new immutable manifests. Repeat: zero stored/15 duplicates/head unchanged. Scoped durable refresh jobs and recent-correction overlap. |
| P1 PIT/cache correctness | VALIDATED | Accepted pre-refresh manifest remains readable/replayable. Fixed a browser correlation-cache leak when switching to a historical cutoff with zero visible instruments; regression and real browser empty-state checks. All chart/feature/comparison caches clear before empty-context guards. |
| P1 Browser-origin security | VALIDATED | API Host/Origin checks, proxy Host validation, incoming same-origin writes, strict loopback backend URL and UTF8 byte limits. Real local writes work; foreign Origin remains 403; untrusted Host and credential-bearing/malformed backend URL rejected. |
| P1 Backup/recovery | VALIDATED_WITH_LIMITATIONS | Existing output is protected; same-volume atomic publication also rejects a concurrent creator. Real isolated UTF8 restore: all 51 tables, 193 Parquets, frozen research/models/dossier/personal replay, refresh jobs. Ephemeral drill is not a retained owner backup; browser-local notes/watchlists are outside catalog backup. |
| P1 Resilience | VALIDATED_WITH_LIMITATIONS | Real backend loss/restart and browser reload; actual unavailable local-model endpoint fallback; dedicated PG provider failure/retry, interrupted-after-commit ingestion, corruption, permanent dead job and database outage checks. One concurrent heavy-drill replay mismatch is recorded below; final regression runs avoid that contention. |
| P2 Scheduling | VALIDATED_WITH_LIMITATIONS | Visible configurable 07:00 Asia/Kolkata slot, idempotent latest-missed-slot catch-up, due/backoff worker, results/last-success diagnostics; Task Scheduler construction verified with `-WhatIf`. Actual registration/logon execution DEFERRED. No scheduled task or permanent service installed. |
| P2 Workstation | VALIDATED_WITH_LIMITATIONS | Desktop 1920×1200 development-server review across all navigation panes, actual charts/indicators/state/scans/risk/CORTEX/research history/Quant/model reports, source gaps, historical mode and failure states. Production and genuine owner browser use remain unvalidated. |
| P2 Local LLM | DEFERRED | No configured model URL/ID, known Ollama/LM Studio install/CLI or common runtime listener. Hardware inspected: ~32 GiB RAM, RTX 4060 Laptop/8188 MiB VRAM. Optional vendor-documented pathway prepared; no install/download or genuine model benchmark. Deterministic fallback works. |
| P2 India/US | DEFERRED | Upstox/Alpaca remain DEFERRED_NOT_CONFIGURED. Fixed read-only endpoints, env auth, identity/calendar requirements and missing-credential behavior retained/tested. No fabricated authenticated result or substituted scraped feed. |
| P2 Genuine owner records | DEFERRED | Owner mutations require explicit authorization after inspection/backup planning. Pilot portfolio/journal/prediction fixtures are excluded from owner habits. Owner preferences/baseline approval remain gated. |
| P2 Regression/release | VALIDATED_WITH_LIMITATIONS | Backend 349 tests + 13 subtests passed twice; frontend 54 tests/typecheck/build passed twice. Local hardening commit only; no v1.0.1-operational tag while production/owner gates are blocked. |

## Delivered operational changes

- `operations.py`: strict credential-free profiles; loopback/test/owner-root isolation; read-only UTF8/migration/integrity preflight; bounded UTC daily plans, three-session overlap and 1–366-day recent backfill; durable profile-scoped jobs; retry/failure/freshness/status records.
- `operations_runtime.py`: API startup from the selected verified profile. Existing architecture services are reused; no independent market calculations or new execution domain.
- Windows scripts: explicit start/stop and one-shot refresh; optional visible Task Scheduler registration with a dry-run gate, limited current-user principal, missed/logon recovery and ten-minute retry checks. Scheduling stays disabled unless explicitly enabled by the owner.
- System & Lineage: recorded daily refresh status, attempts, result counts and last success, clearly independent of historical research selection.
- Backend/proxy Host and browser Origin validation; incoming Host rather than Next's internally rewritten URL is used for same-origin comparison. The genuine browser regression was fixed and regression-tested.
- Historical UI cache clearing and honest comparison/breadth loading states. Backend-error help no longer assumes the default port when a selected profile uses another one.
- Backup publication refuses overwriting retained backups or a concurrent destination. Existing backup format/encoding/recovery readers remain compatible.
- Phase 4's historical momentum-contradiction assertion is pinned to the accepted Phase 12 manifest instead of requiring a moving live market to stay negative. Its original assertion and remaining current-data scenarios are retained. Phase 10 replay assertions now print mismatch diagnostics; no assertion was weakened or removed.

Accepted financial/source implementation files covered by the Phase 8/10/11/12 fingerprints were preserved. The Windows storage `temp_path.open("r+b")` fix remains intact. No broker order/write endpoint, capital deployment, arbitrary CORTEX SQL/shell/code execution, synthetic owner history or cloud model was introduced.

## Actual market and end-to-end workflow

Environment: `PILOT_TEST`; PostgreSQL 17 loopback 55432 / `market_cortex_pilot_test`; original isolated Binance data root. Owner PostgreSQL 5432 / `C:\MarketCortexData` remained untouched.

Old head `3bf002d2-15f2-4f9d-8c54-cc7eb3fb349c` contains 5035 bars through 2026-10-03. Refreshed head `a00facd3-9c92-4500-9bef-18f427d937d7` contains **5055 bars / 1011 sessions per pair**, 2024-01-01–2026-10-07. Observed arrival is 2026-10-08; no backdated knowledge or in-progress daily candle is implied. Current daily freshness is five/five closed UTC sessions; advanced derivatives/context retain their own stale/unknown flags.

Real workflow: profile/start → health/environment → dataset/cutoff/freshness → 1011-bar BTC chart and 11 deterministic indicators → canonical RSI/state → ephemeral opportunity scan → saved deep CORTEX research → citation/reopen/evidence replay → read-only risk against **SYNTHETIC_TEST_PORTFOLIO** → frozen Quant experiment → owner-eligibility check → isolated encrypted recovery. All API calls succeeded against the identified dataset. The UI also saved/replayed an actual SOL research question and reopened the canonical momentum run `7017c9e9-ee90-5fc0-9101-2a5e4e660b62` with its daily simulated trades/regime cells. No market, portfolio, journal or thesis owner records were seeded.

Controlled public coverage probes for ADAUSDT and DOGEUSDT returned TRADING metadata and two daily samples each. They were **not registered or ingested**. This establishes practical reachability for investigation, not validated new history/universe coverage. Existing bootstrap accepts 1–50 explicit symbols; operational plans remain limited to reviewed existing mappings. Broad/delisted/derivative/option/event/news/on-chain coverage is not established.

## Practical performance

Single local samples; not p95, a sustained benchmark or a production SLA. One workflow ran alongside regression activity; results are descriptive measurements of this machine/data.

| Operation | Observed elapsed |
|---|---:|
| Windows development warm startup + preflight + health | 3.739 s |
| Research context | 0.218 s |
| Full five-member dashboard composition | 7.376 s |
| 1011-bar chart plus 11 indicators | 0.837 s |
| RSI14 series | 0.502 s |
| Canonical market state | 3.379 s |
| Ephemeral BTC opportunity scan | 2.394 s |
| Deep CORTEX research/save | 4.003 s |
| Reopen saved research | 0.031 s |
| Recompute saved research evidence | 4.422 s |
| Synthetic-pilot risk snapshot | 3.584 s |
| Fetch recorded experimental Quant result | 0.088 s |
| Unavailable local endpoint → deterministic fallback | 5.236 s |
| Actual encrypted pilot backup | 74.885 s |
| Actual isolated restore | 169.742 s |
| Frozen ridge recomputation/replay after restore | 2.519 s |
| Genuine LLM inference/resources | DEFERRED; no model evaluation |

The dashboard's full-history composition is visibly slower than a chart read. Resource/time budgets remain cooperative; no hard RSS/GPU cap or heavy concurrent-drill throughput is claimed. Paid API spend remains ₹0.

## Failure and recovery evidence

| Failure | Evidence / response |
|---|---|
| Database unavailable | Real connection to an absent loopback port returns safe failed preflight; no DSN/password in diagnostics. Owner missing-DSN preflight fails before mutation. |
| Provider unavailable / access denied | Dedicated PG tests preserve head, retry transient failure and mark permanent failure dead. Actual Binance refresh/repeat succeeds. No order endpoint is involved. |
| Interrupted ingestion | Test fails after catalog commit before job completion; retry counts the duplicate, preserves head and atomically records success. Lease/attempt records survive process loss. |
| Corrupt referenced file | Isolated corruption yields FAILED integrity preflight with the referenced path; catalog remains evidence, not silently rewritten. |
| Model unavailable | Actual refused local endpoint selects deterministic fallback with LOCAL_MODEL_UNAVAILABLE_OR_INVALID. This is failure testing, not a successful LLM evaluation. |
| Backend unavailable | Owned API stopped while browser/frontend remained live. Refresh cleared active context/analytics and displayed BACKEND_UNAVAILABLE; restart/reload recovered environment and five/five freshness. |
| Failed research job | Existing failed/cancelled/dead/abandoned research-job regressions retained; approved job scope/leases/cancellation/retry boundaries verified by the suite. |
| Historical empty data | Switching from populated comparison to a pre-arrival cutoff clears later matrix/indicator/chart caches and shows unavailable/empty states. |
| Concurrent heavy recovery/replay | One Phase 10 dossier E replay returned unmatched during an overlapping actual recovery drill/regression run. Exact cause is not established. A subsequent isolated replay matched all eight steps; no accepted evidence was rewritten. Final full gates run without a competing heavy drill. This overlap remains a VALIDATED_WITH_LIMITATIONS reliability observation. |
| Backup destination exists/races | Existing retained bytes survive; a concurrent creator between preflight and publication is refused; owned staging is cleaned. Actual atomic bundle restores successfully. |

Run large backup/restore rehearsals while application research/workers are idle. Preserve mismatch diagnostics and investigate if the same failure repeats; do not treat an unavailable calculation as an exact match.

## Recovery coverage and limits

Actual drill: a new random disposable UTF8 `_test` database and empty root, never owner state. Encrypted bundle **828,057,653 bytes** (~789.70 MiB). All **51 table counts matched** the source sample; the verifier's general contract treats pre-dump counts as lower bounds if another process appends during pg_dump. PostgreSQL supplies a consistent dump snapshot.

**193 referenced Parquet artifacts**, zero missing/corrupt/unreferenced; market/context heads match; exact 1011-bar query hashes match; saved CORTEX hash/replay verified; seven accepted experiment definitions/results/datasets and their model JSON verified; ridge recomputation MATCH; experimental dossier/canonical mission replay MATCH; frozen personal snapshot replay matched; ten completed refresh jobs/results survived. Catalog tables include theses, portfolio versions/risk, journal revisions, prediction records/evaluations, research/Quant/context and personalization memory. The disposable database/files and ephemeral passphrase were cleaned; this is **not** a retained owner backup.

Browser-local Research Desk notes/watchlists/view preferences, owner config, source release/runtime binaries and secret backup key need separate handling. The UI explicitly identifies browser-local notes as outside PostgreSQL backup. Use durable Journal records for research requiring catalog recovery. Genuine owner recovery/cutover remains DEFERRED until configuration and authorization are available.

## Local AI, privacy and provider onboarding

The existing ModelGateway allows loopback-only claim-ID selection, schema/known-ID validation and deterministic fallback. Tool selection/calculation/citations remain deterministic and bounded. No genuine model question-understanding, financial explanation, structured-output, latency or RAM/VRAM benchmark is claimed. A permission-dependent optional Windows Ollama/Qwen3:4b evaluation pathway with primary vendor sources is in the owner guide; no paid API, model installation or large download occurred.

The API defaults to loopback; browser proxy routes/URLs/Host/Origin are restricted. Foreign CORS is not enabled. Safe code-only provider/driver diagnostics avoid secret-bearing exception strings. Personal research stays in local services; test/synthetic histories remain excluded from owner habits. Filesystem administrator/malicious same-account processes and OneDrive folder synchronization are outside application enforcement; review actual folder storage deliberately before genuine owner use.

Upstox/Alpaca credential flags are absent for their actual environment-variable names. Their adapters remain present: fixed read-only historical endpoints, environment-only authentication, valid listing/native mapping and verified exchange-session calendars. Upstox output retains `provider_unspecified` adjustment basis until actually verified; Alpaca uses explicit raw/IEX with entitlement/feed limitations. Neither was authenticated live. No unverified free/scraped substitute was introduced.

## Evidence files and final regression gates

- Owner commands/profiles/authorization/recovery: `docs/operations/MARKET_CORTEX_OWNER_DEPLOYMENT.md`.
- Actual API workflow/performance/data references: `docs/operations/OPERATIONAL_PILOT_RESULTS.json`.
- Actual restored tables/artifacts/replays: `docs/operations/OPERATIONAL_RESTORE_RESULTS.json`.
- Browser observations and proof: `docs/operations/OPERATIONAL_BROWSER_QA.json`, `OPERATIONAL_REFRESH_QA.png`. Evidence is **development-server** only.
- Earlier architecture/exit evidence: existing Phase 1–12 reports, especially `PHASE_12_EXIT_MATRIX_2026-10-08.md` and `MARKET_CORTEX_V1_SYSTEM_READINESS.md`.

Final repeated gates: **VALIDATED**.

| Gate | Final result / local ignored evidence |
|---|---|
| Backend acceptance 1 | **349 passed, 13 subtests passed, no skips**, one existing Starlette/TestClient deprecation warning; 543.92 s. `runtime/operational-backend-acceptance-1.log`. |
| Backend acceptance 2 | **349 passed, 13 subtests passed, no skips**, same existing warning; 537.02 s. `runtime/operational-backend-acceptance-2.log`. |
| Frontend final 1 / 2 | **54 passed** each across 13 files; `runtime/operational-frontend-final-1.log` / `-2.log`. |
| Typecheck / production build | Both passed twice; corresponding `operational-typecheck-final-*` / `operational-build-final-*` logs. These do not certify production runtime. |
| Preservation | Accepted experiment, mission and personal implementation hashes match their original reports; storage r+b retained; `phase12-v1.0.0^{commit}` remains 932f4ec25936294f17ee0e242d20e223fb09bc16. |
| Windows cleanup | Owned development API/frontend stopped; no test-created permanent refresh task; owner root still empty. Dedicated validation cluster stopped after checks. |

Earlier runs: the moving-head momentum assertion failed and was correctly frozen; a subsequent 347-test pass preceded two additional backup tests; an overlapping 349-test run had the recorded dossier E mismatch. These are not represented as two final successful runs. No tests were dropped, skipped to improve counts or warning-suppressed. Final full runs include authenticated-provider contract fixtures, isolated migrations, security/isolation/corruption/retry/recovery, every accepted Phase 8/10/11/12 replay, and restore fixtures.

## Owner action required

1. Resolve the production launch authorization through normal controls; verify the real production server/backend communication/browser workflow.
2. Configure the owner DSN locally; perform read-only catalog/encoding/migration/integrity inspection; review a concrete retained-backup/recovery/migration/bootstrap plan and explicitly authorize owner mutations before deployment.
3. Confirm genuine owner onboarding and retained encrypted recovery. Start collecting eligible research without importing synthetic histories. Optional scheduling and local-model downloads need separate deliberate enablement.

India/US credentials and full-market coverage remain deferred independently. An optional LLM is not required to use deterministic CORTEX. Existing architecture is preserved, but **OWNER_READY is not established**. Keep `phase12-v1.0.0`; prepare a clean local hardening commit and withhold `v1.0.1-operational` while critical deployment gates are blocked.
