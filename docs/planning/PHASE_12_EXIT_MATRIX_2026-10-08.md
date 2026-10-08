# Phase 12 exit matrix — 2026-10-08

**Status: COMPLETE — acceptance A–X passed.** Annotated local release `phase12-v1.0.0`; `phase12-v1.0.0^{commit}` identifies the accepted implementation. Baseline `phase11-v0.11.0` / `0ed54cbb682da298179c21cb110c5d2906da1477` is preserved. No push.

Canonical repository: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`. Validation uses PostgreSQL 17 on loopback 55432, dedicated `_test` catalogs and disposable schemas/restore roots. Owner main database and `C:\MarketCortexData` are untouched.

## Acceptance A–X

| Gate | Evidence | Status |
|---|---|---|
| A Previous phases | Full suite plus actual Phase 8/10/11 saved-data replay; legacy fingerprint files unchanged | PASS |
| B Experiment framework | Frozen contracts, implementation/dependency/source identity, lifecycle, checksummed Quant artifacts | PASS |
| C Hypothesis registry | Immutable questions, target/reference, numerical falsification thresholds, exploratory/preregistered distinction | PASS |
| D Dataset lineage | Frozen registration source, identity/calendars/raw basis, input hashes, actual/assumed timestamps, context memberships | PASS |
| E Leakage protection | Future target/feature/context/revision/manifest traps; purge/embargo; train-only transforms/selection/tuning; disjoint calibration | PASS |
| F Honest models | Safe CPU mean/momentum/ridge/logistic/fixed ensemble, strict JSON and exact mathematical replay | PASS |
| G Baselines | Per-fold/aggregate training-mean comparisons, canonical bar simulation references, no OOS winner promotion | PASS |
| H Temporal training | Rolling/expanding outer folds, purged inner search and separate calibration, bounded fixed trials | PASS |
| I Ensemble/regime | Fixed-weight ensemble, descriptive proxy regimes/transitions/factors with cell N and noncausal limitations | PASS |
| J Analogues | Past training scaling, feature-only matching, separated historical outcomes, newest reference without future label | PASS |
| K Robustness | Asset/year/regime/fold cells, ablation, missingness, cost proxies, canonical fill/timing/slippage stress and supplied risk shocks | PASS |
| L Search history | Pre-outcome exposure and immutable trial checkpoints; all variants and unavailable significance methods visible | PASS |
| M Holdout reuse | Legacy Quant windows imported; all real studies PREVIOUSLY_EXAMINED; genuinely unseen NOT_ESTABLISHED | PASS |
| N Edge Library | Checksummed stance/result/cost/search/exposure links; no Edge status mutation; Learning and Laboratory views | PASS |
| O CORTEX | Approved experimental tool registry, deterministic recorded-value explanation, bounded authorized wrapper, linked canonical mission/dossier replay | PASS |
| P No deployment | Strict registry; no automatic model/strategy activation; explicit OWNER_MAIN research-baseline approval gate | PASS |
| Q Workstation | Eleven laboratory sections, actual metrics/charts/lineage, hypotheses, jobs, comparisons, analogues, governance | PASS |
| R Resource controls | One concurrent experiment, row/grid/fold/iteration/timeout/artifact bounds; cancellation and cleared job references | PASS |
| S Recovery/replay | Real encrypted pilot restore and repeatable synthetic new-artifact restore, UTF8 preflight | PASS |
| T Negative OOS | Phase 8 −7.82%, N=82 unchanged; all studied historical windows marked examined | PASS |
| U Repeated suites | Backend and frontend/typecheck/build final passes | PASS |
| V Browser | Recorded-model comparison, dataset/labels, newest analogues, unavailable calibration, governance and Edge evidence | PASS |
| W Research only | No broker/trade/order endpoints, arbitrary execution, secret-bearing prompts or unrestricted resource loops | PASS |
| X Scientific honesty | Forecast error separated from simulated trade returns; no supported profitable edge or unseen-validation claim | PASS |

## Implementation and science

New experimental contracts, hypothesis/model registries, registered CPU algorithms and storage/job/API/CLI integration are documented in `docs/quant/PHASE_12_EXPERIMENTAL_ADVANCED_QUANT.md`. The architecture map connects Phases 1–12. New models/artifacts use restricted JSON; no pickle/joblib execution or large model download exists.

Purge/embargo applies to forward label overlap and label knowledge. Feature ranking/scaling/model selection fit only past training rows. Calibration fits a separate past window; sample insufficiency returns PROBABILITY_UNAVAILABLE. Analogues use no future/outcome-based selection and allow a feature-only newest reference. Factors and block-rotation importance are noncausal diagnostics. Moving daily block uncertainty is conditional on the search/block/stationarity assumptions. FDR/DSR/PBO are unavailable when their inputs/assumptions are absent; meta-labeling requires representative PIT candidate/rejected coverage and remains insufficient.

## Real stored Binance results

Source: 5035 stored raw daily observations, five selected surviving USDT pairs, 2024-01-01–2026-10-03. Source cutoff 2026-10-08. Four purged temporal test folds, 90 test sessions each, five assets. N=1800 counts dependent target rows, not independent trades. These are previously examined retrospective windows and not pristine or prospective OOS.

| Study | Target | Error skill against training mean | Sample | Finding |
|---|---|---:|---:|---|
| Training mean | 5-session return | 0.0000 | 1800 | No improvement; registered threshold failed |
| Momentum baseline | 5-session return | −0.33818 | 1800 | Hypothesis falsified |
| Ridge + causal state features | 5-session return | −0.03980 | 1800 | Hypothesis falsified |
| Fixed ridge/mean ensemble | 5-session return | −0.01495 | 1800 | Hypothesis falsified |
| Relative strength | 10-session BTC excess return | −0.03275 | 1800 | Hypothesis falsified |
| Volatility/volume direction | 5-session positive return | −0.10806 Brier skill | 1800 | Hypothesis falsified |
| Funding / OI | 5-session return | Unavailable | 0 | Inconclusive; no historically aligned complete cases |

Negative skill is worse forecast error than the baseline. It is not a percentage investment return. The return and direction targets have different units/metrics and are not interchangeable comparisons. Every result, source/dataset/model reference, fold boundary/score, trial, calibration, warning and replay hash is in `PHASE_12_PILOT_RESULTS.json`.

The modest canonical momentum simulation is a separate two-month in-sample study with 13 simulated trades and declared costs. Its small positive simulated return does not override negative forecast studies or the prior Phase 8 temporal OOS −7.82%, N=82. The cross-phase workflow separately tests the canonical breakout detector/robustness and supplied hypothetical risk shock. These cannot establish profitable trading evidence.

## Validation totals and performance

Backend passed twice: **333 tests + 13 subtests, no skips**; 540.03 s and 533.46 s. All Phase 1–11 regressions, accepted old-source/mission/personal replay, new golden/science/PIT/catalog/security and synthetic new-artifact restore gates ran. Runtime evidence: `runtime/phase12-backend-final-1.log` and `runtime/phase12-backend-final-2.log` (local ignored logs).

Frontend passed twice: **43 tests**; TypeScript check and production build passed twice. Runtime evidence: `runtime/phase12-frontend-final-1.log`, `runtime/phase12-frontend-final-2.log` and corresponding typecheck/build logs.

One nonfunctional Starlette TestClient/httpx deprecation warning remains. No new warning suppression was added. Actual per-study run+replay times, total time, dataset/row counts and artifact references are recorded in the pilot report. Resource bounds are cooperative and row/artifact based, not a hard OS RSS/preemption guarantee. Paid API cost is ₹0; all experiments are NumPy CPU and deterministic CORTEX fallback.

Browser proof: `docs/workstation/PHASE_12_ADVANCED_QUANT_QA.png`. Browser validation used the local development server at 127.0.0.1:3002 against the final loopback pilot API: actual ridge N=1800 and negative skill chart; all derived rows/labels/provenance with 25 feature-only newest references; latest-state analogue search returned five recorded matches; regression PROBABILITY_UNAVAILABLE; owner baseline approval disabled in PILOT; a new alpha-2 ensemble proposal recorded READY before evaluation. Production server launch was rejected twice by automatic approval review with "blocked by policy"; production builds were verified separately. No production runtime/browser validation claim is made. Validation is desktop; mobile/production-owner rollout is not claimed.

## Security and recovery

Strict request/model/feature/tool schemas reject arbitrary code, paths and nonfinite artifacts. Local proxy route allowlists and loopback restrictions remain enforced. Questions/notes are untrusted prose, not instructions for tools or a model. Jobs are scoped to experimental research; cancellation cannot alter existing Quant jobs. Accepted cancellation clears job refs; completed calculation artifacts can remain immutable historical evidence. Explicit owner baseline approval is rejected in test catalogs even if a caller labels the environment OWNER_MAIN. No private personal evidence is sent to an external model.

A recovery drill caught a fresh Windows database defaulting to WIN1252, which could not restore rupee-containing research records. Disposable restore databases now use UTF8 and the backup includes an additive encoding field checked before table data restore. The real pilot encrypted recovery drill restores definitions, model JSON, dataset/result artifacts, manifests, dossiers and Edge links into a fresh disposable catalog/root; exact replay is checked there. The repeatable synthetic restore fixture also passes. Owner data is never a restore target.

## Scope of evidence

| Classification | Delivered evidence |
|---|---|
| Implemented | Experimental registry, temporal dataset/model pipeline, diagnostics, tools, jobs, UI, governance, recovery integration |
| Tested with fixtures | Golden linear/noise/shift/analogue/leakage/missingness/security/cancellation/isolation and new artifact restore |
| Real stored data | Seven Binance studies, historical analogues, canonical simulation/robustness, CORTEX/dossier/Edge links and real encrypted restore |
| Genuinely unseen | NOT_ESTABLISHED; no pristine future validation or supported profitable edge |
| Deferred | Upstox/Alpaca authenticated live validation: DEFERRED_NOT_CONFIGURED; verified equity mappings/calendars; genuine owner history/LLM deployment |
| Unsupported/insufficient | Broad delisted universes, advanced missing sources, justified FDR/DSR/PBO, representative meta-labeling, validated live probabilities |

## Final project state

Original roadmap completion is architectural and evidence-backed within the validated daily pilot scope. Owner deployment and ongoing fresh data operations remain separate. Genuine owner sample is zero / INSUFFICIENT_HISTORY; synthetic/pilot records are not owner habits. New research links do not change canonical strategies, portfolio capital, predictions or Edge status. The release is local, retains previous tags and is not pushed.

**No supported edge exists based on the available evidence.**

## Final recorded recovery and performance

Final real encrypted restore: 7 completed/inconclusive study artifacts and definitions, every referenced model/dataset checksum, 188 Parquet artifacts, canonical mission/dossier replay MATCH, and 1 frozen unevaluated proposal(s) with child-definition links verified. The disposable restore database/files were cleaned. The encrypted drill bundle was approximately 785.87 MiB; it is a recovery rehearsal, not a retained owner backup.

Final stored portfolio elapsed 372.21 s; per-study run + exact recomputation replay ranged 49.2–50.2 s. Each run and replay was individually bounded by the registered 180-second default. No hard RSS cap was claimed.
