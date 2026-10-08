# MARKET CORTEX v1 — Operational readiness

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
