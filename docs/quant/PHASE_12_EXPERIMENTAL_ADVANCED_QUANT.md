# Phase 12 — Experimental Advanced Quant

Release: `phase12-v1.0.0`, local only. This finishes the original architecture roadmap. It does not establish a profitable edge, a deployed owner system, or live coverage of Indian and US equities.

## Architecture

The Advanced Research Laboratory extends the existing Quant Lab. It uses the same PostgreSQL catalog, immutable Parquet history, identity/calendar contracts, `ReplayCatalog`, Phase 2 indicator calculations, `QuantService`, `QuantStore`, `JobQueue`, CORTEX missions, personal snapshots and Edge Library. No alternative trade simulator or market-data engine was introduced.

New modules are `experiment_contracts`, `experiment_datasets`, `experiment_models`, `experiment_analysis`, `experiment_store`, `experiments`, `experiment_tools`, `experiment_api` and `experiment_cli`. Migration `0013_experimental_research.sql` adds append-only research records and additional derived JSON artifact kinds to the existing Quant artifact store. Existing engine files participating in Phase 8/10/11 fingerprints were preserved. Historical accepted Phase 10/11 dossiers remain replayable.

```mermaid
flowchart LR
  M[Market and context manifests] --> R[Canonical frozen replay source]
  R --> D[Causal features and separate labels]
  H[Frozen hypothesis] --> E[Versioned experiment definition]
  D --> E
  E --> V[Purged temporal training and inner validation]
  V --> C[Separate calibration slice]
  C --> O[Temporal test predictions]
  O --> A[Baseline, factor, regime, drift and robustness diagnostics]
  A --> Q[CORTEX skeptic and canonical Quant evidence]
  Q --> L[Immutable dossier and Edge evidence link]
  L --> G[Human research governance]
  E --> X[Search and exposure ledger]
  X --> G
```

## Contracts and identity

Frozen Pydantic contracts reject unknown fields, nonfinite values, uploaded paths, executable code and unregistered models/features. Exported schemas are in `packages/contracts/`.

| Contract | Purpose |
|---|---|
| ResearchHypothesis | Question, rationale, relationships, target, universe, benchmark, falsification prose, numerical sample/improvement thresholds, concerns and exploratory/preregistered registration |
| ExperimentDataset | Market manifest, source cutoff, dates, daily horizon, replay policy, raw basis, selected-survivor universe, source classification and publication lag |
| ExperimentDefinition | Frozen hypothesis reference, dataset, protocol, model, configuration, metrics and optional canonical Quant references |
| ValidationProtocol | Rolling/expanding windows, inner validation, separate calibration, purge/embargo, minimum training rows, train-only feature selection |
| ModelDefinition / ModelArtifact | Approved CPU algorithm, bounded regularization grid/iterations; restricted JSON transforms, coefficients, cutoffs and calibration |
| ExperimentManifest / ExperimentRun / ExperimentResult | Definition/hypothesis/source/dataset/code/dependency hashes, exposure, result status, reports, warnings and reproducibility hash |
| RobustnessAssessment / ExperimentComparison | Transparent small-cell classification and comparison assumptions |
| ExperimentProposal / PromotionDecision | Frozen registered revisions and explicit human research decisions |

Experiment identity includes the loaded code fingerprint, Python/NumPy versions, hypothesis hash, immutable source hash and every supplied definition field. The source is frozen at registration, including context manifest membership times. Run/replay retrieves that artifact instead of recapturing current database state. Identical definitions and source/runtime produce the same identity. Creation/audit timestamps are outside numerical result hashes.

Lifecycle events are append-only: PROPOSED → VALIDATED → READY → RUNNING → COMPLETED or INCONCLUSIVE, with FAILED, REJECTED, REVIEW_REQUIRED and ARCHIVED. Execution completion is separate from the scientific conclusion. COMPLETED / HYPOTHESIS_FALSIFIED is a normal outcome. Trial checkpoints remain visible even if later work fails. Earlier development versions are archived with audit records; their saved artifacts remain readable and their absent implementation is reported as VERSION_UNAVAILABLE.

## Dataset, lineage and targets

The supported research universe is the five Binance USDT spot pairs. It is a selected surviving pilot universe, with verified UTC 24x7 calendars, daily sessions and raw bars. This is not historical full-universe or delisting-aware equity research.

Derived rows retain instrument IDs, session, feature cutoff, source observation, input window/hash, actual input knowledge time, context observation IDs and separately nested label provenance. The dataset carries manifest/cutoff, currency, calendar version, feature versions/parameters, source classification, exclusions and missingness. It stores derived evidence and references; raw Parquet history is not copied into a second lake.

Registered experimental features are momentum 5/20, canonical trend persistence, return volatility 20, relative volume, BTC-relative momentum, 60-session drawdown, pilot dispersion, BTC return correlation, funding, OI change and a specifically named Treasury macro series. Fixed experimental price regimes use volatility ≥3.5% and momentum ±2%. They are research proxies; the canonical Phase 2 Market State rules are unchanged. Relative strength and excess-return labels explicitly use BTC; all other labels use own-instrument prices. The hypothesis cross-asset reference is restricted to BTC. Forecast-error comparisons use the training mean; canonical Quant trade studies retain their existing cash/BTC/equal-weight benchmarks.

Targets: N-session close return, BTC excess return, forward return volatility, maximum adverse/favorable excursions bounded by zero, and positive-return direction. Predictor matrices can only consume registered feature keys. Labels are not features. Missing inputs remain null; training/evaluation uses complete cases and reports exclusions. Feature-only reference rows retain the newest state when its future target is unavailable. They are excluded from fitting and scoring and remain usable for analogue references.

**AS_RECORDED:** every feature version, mapping, ingestion, availability and manifest must be known at its row cutoff. Later labels must be known before a training cutoff. Backfilled data cannot masquerade as recorded historical knowledge.

**HISTORICAL_RECONSTRUCTION:** first valid final raw price revisions use explicit assumed close-plus-publication-lag availability and assumed historical mapping availability. Actual source envelopes remain intact. This permits retrospective price studies, not claims about what the application observed then. Later corrections are not silently substituted for initial price knowledge. Context receives no reconstruction exception: it requires actual publication, ingestion, recording and known manifest membership, validated source classification, known derivative contracts and a conservative three-day freshness limit. An older fact remains usable through its known earlier manifest even if the frozen source has a later head. Synthetic context cannot enter LIVE_SOURCE datasets. Treasury outstanding-bills average interest is not a policy rate, market yield or risk-free rate.

## Temporal validation and leakage defenses

Sessions are split chronologically across all assets, never randomly across rows. Test folds do not overlap. Each outer training set purges labels crossing the next window and applies embargo. Training also contains a purged inner validation slice for selecting regularization and a separate trailing calibration slice. Selection, means/scales, feature ranking, coefficients and calibration never use outer test outcomes. A rolling model discards older training rows; an expanding model retains eligible prior history. Later folds may learn from previously completed history, with target availability checks.

Top-k feature ranking uses training-only absolute correlation, with deterministic tie breaks. Scaling uses that training subset. Every inner alpha trial is checkpointed and retained. Test outcomes are used only for declared metrics and labelled exploratory diagnostics. Ablation uses frozen outer training data and the already selected alpha; it does not promote an OOS winner. Calibration is not refit during ablation, which is explicitly disclosed.

Golden tests cover linear association, noise, shifted distributions, future feature/target changes, future context publication/ingestion/revisions/manifests, label overlap, train-only transforms/selection, known analogues, unavailable latest labels, missing context and safe model serialization. Existing Phase 1–11 PIT/calendar/provider/risk/security/replay gates remain part of the full suite.

## Models and evaluation

| Registry | Behavior |
|---|---|
| mean | Training-only target mean/prior |
| momentum | Registered momentum-5 forecast/direction rule |
| ridge | NumPy L2 linear fit with temporal inner selection |
| logistic | Bounded regularized gradient fit for direction targets only |
| ensemble | Fixed equal ridge + training-mean combination; weights are not selected on test outcomes |

No sklearn/cloud/GPU dependency, pickle, joblib, uploaded estimator or dynamic import/execution is required. Artifacts contain only strict finite JSON metadata/arrays. Inference validates registry, dimensions, scales, features and task again. Exact replay is tested with the recorded NumPy runtime. A changed code/runtime returns VERSION_UNAVAILABLE; cross-runtime floating-point equivalence is not claimed.

MAE, RMSE, directional accuracy and baseline skill are recorded per fold and in aggregate. Direction adds Brier score and log loss. Sample N counts dependent instrument/session labels, not independent trades. Positive baseline skill means lower forecast error; it is not net investment return. Return/cost diagnostics use nonoverlapping anchor dates and a transparent long-if-positive forecast proxy, equal asset weights and declared bps costs. They are not bar fills, omit fixed fees without a notional, and are not a second backtester. Canonical Quant runs/studies provide trade/fill/cost/delay/slippage/holding/asset/period evidence with their own warnings and metrics.

Machine conclusions evaluate the frozen numerical minimum sample and error-improvement requirements. Qualitative falsification prose and robustness still require review. EXPLORATORY_IMPROVEMENT never awards supported edge or deployment.

## Probability and calibration

The event is positive raw forward close return over the declared horizon. A distinct past calibration window fits a bounded Platt-style transform only with at least 100 rows and 20 events/non-events. Test N must also be at least 100 to report EXPERIMENTAL_CALIBRATED. Otherwise PROBABILITY_UNAVAILABLE is explicit. Reliability bins, Brier/log loss, training cutoff, calibration N and model version are inspectable. Dependent labels, temporal instability and the modest calibration fit limit interpretation. These are experimental diagnostics, not validated live market probabilities.

## Factors, regimes, analogues, drift and robustness

Feature reports retain standardized coefficients, within-asset temporal block-rotation importance, fixed training refit ablation, train correlations, redundant-feature flags, fold stability and outlier-trimmed factor associations. They are noncausal. Asset, year and regime evaluation cells expose N; small cells remain insufficient. Regime transitions show descriptive counts and completed durations, excluding right-censored runs. They do not claim transition probabilities.

Analogue search fits scales on eligible past candidate features, chooses matches from feature distances only, enforces temporal separation and reads historical outcomes after selection. Candidate labels must already be known by the reference cutoff. The reference needs no forward label. Matches are historical comparisons, not forecast probabilities or identical future paths.

Drift uses training-vs-test standardized mean shifts, residual error and explicit missingness/complete-case coverage. STABLE/WATCH/DEGRADED thresholds are transparent research heuristics (>1/>2 mean shift); N<100 remains insufficient. No automatic retraining or activation follows a drift label.

Robustness combines fold/period/asset/regime behavior, feature ablations, missingness, forecast cost proxies and existing canonical Quant robustness. The standalone experiment can classify FRAGILE, MIXED or INSUFFICIENT_EVIDENCE, never a robust supported edge. Existing Portfolio & Risk supplies typed hypothetical shock scenarios; shocks are assumptions without forecast probabilities.

## Search, holdouts and uncertainty

The exposure ledger records every evaluated period/universe before outcomes, planned variant bounds, objectives and prior Quant run/study windows. The Phase 8 −7.82%, N=82 result is preserved as already examined. Reused historical source windows never become pristine because a new model or split was chosen. Preregistration records chronology of the question; it does not grant a genuinely unseen holdout. The current release reports NOT_ESTABLISHED for genuinely unseen validation.

Moving daily block bootstrap first aggregates cross-asset paired squared-loss differences, then resamples contiguous blocks of the declared horizon. It refuses very small samples and blocks spanning calendar/fold gaps. Seed, paths, block length, daily N, empirical mean and conditional 95% interval are recorded. The interval is conditional on the frozen search, block and stationarity assumptions. It does not correct selection or forecast future prices.

FDR, deflated Sharpe and PBO return STATISTICAL_METHOD_UNAVAILABLE with reasons because there are no justified independent p-values/net-return trials/combinatorial-CV outcomes. Meta-labeling is INSUFFICIENT_EVIDENCE until PIT candidate/rejected coverage and a representative outcome ledger exist. No numerical placeholder is substituted.

## CORTEX, Edge Library and personalization

`/experimental/tools` exposes the approved extension registry. Read tools inspect definitions/hypotheses, validation, models, features, regimes, calibration, drift, robustness and search history. The typed experimental mission wrapper can run one frozen registered experiment only with `authorize_run=true`, then inspect/challenge it and compose a canonical CORTEX market mission inside the remaining tool budget. Private free-text questions are treated as data; deterministic explanations quote recorded numerical evidence. Dossiers link result hashes, canonical mission hashes/replay and optional verified local personal snapshots. No arbitrary shell/SQL/code, model upload, provider writes, strategy-code changes or automatic promotion is exposed.

Phase 11 snapshots can carry question-priority context; numerical criteria remain frozen. The present pilot has zero genuine owner records and INSUFFICIENT_HISTORY. It does not infer owner habits or improvement from synthetic portfolios or pilot experiments. No personal memory/preference is written automatically by experiments.

Edge links retain stance, result/hash, metrics/N, costs, source manifest, robustness, search/exposure and conclusion. Falsified/inconclusive experiments cannot be attached as supporting evidence. Attaching evidence does not update Edge status or pre-registered predictions. The Learning pane and Laboratory governance pane expose these links. Governance supports EXPERIMENTAL, CANDIDATE_FOR_REVIEW, REJECTED, HUMAN_APPROVED_RESEARCH_BASELINE and ARCHIVED with revision checks. Human approval requires explicit confirmation in OWNER_MAIN with a non-test database, and still means research baseline only.

## Jobs and resource limits

Existing durable `JobQueue` handles queued/running/completed/failed/cancelled jobs. A database advisory lock limits concurrent experiments to one. Cooperative checks enforce timeouts and live attempt/lease/cancel state through dataset construction, model iterations, ablations and bootstrap. Accepted cancellation clears the job result reference and prevents further publication through that job. Completed immutable calculation artifacts can remain historical evidence if computation finished at the cancellation boundary. Retries are explicit and scoped to failed/cancelled experimental jobs; existing Quant jobs cannot be cancelled through these routes.

Defaults: 180 seconds per run; maximum 300; 10000 derived rows (maximum 15000); four alphas; six folds; at most 100 optimizer iterations; 200 bootstrap paths (maximum 1000); 12 MB artifacts (maximum 16 MB). Row/matrix/artifact sizes and loop budgets bound workloads. This is not an OS-level RSS or hard CPU preemption guarantee; a single native linear-algebra operation completes before the next cooperative check. No datasets/models are automatically downloaded. Replay is bounded by the same definition timeout.

## API, CLI and workstation

Typed request routes live under `/api/v1/experimental`: registry, hypotheses, experiments/history/result/dataset/reports, artifacts, jobs/cancel/retry, ledger, comparison, analogues, proposals, governance, Edge evidence, query, missions and dossier replay. The workstation proxy maintains explicit route allowlists, loopback backend restriction and body limits.

CLI: `experiment-list`, `experiment-models`, `experiment-ledger`, `experiment-hypothesis --input`, `experiment-register --input`, `experiment-run ID`, `experiment-inspect/result/history/replay/governance ID`, and typed `experiment-compare/analogue/proposal/govern/mission/query/attach-edge --input`. All reuse domain services. CLI file arguments are operator actions; they are not available to CORTEX.

Quant Lab has Canonical Quant Lab and Advanced Research Laboratory tabs. Eleven sections expose explorer, frozen hypotheses, dataset provenance/labels, models/baseline charts, feature/factor research, regimes, analogues, validation, robustness/drift, calibration and governance. Loading/empty/error states, negative findings, sample sizes, source hashes and unavailable diagnostics remain visible. There are no AI confidence gauges or fabricated table rows.

## Recovery and security

Derived datasets/models/results/dossiers are content-addressed JSON in PostgreSQL and ride the existing encrypted pg_dump + immutable Parquet backup. The actual pilot was restored to a fresh disposable UTF8 test database/data root and its artifacts, links and replay checked. Restore now checks UTF8 compatibility before writing table data, preventing Windows WIN1252 failures for rupee/Unicode research evidence. The archived format remains MCBACKUP1; the encoding field is additive. Older archives without that field retain the previous checks.

The accepted source/owner databases were never reset. The owner main DB and `C:\MarketCortexData` remain untouched. Local loopback APIs, strict registries, immutable checksums, prompt-injection fixtures, JSON artifact rejection, scoped cancellation, owner/test isolation and no order/trading route checks are regression tested. A compromised local OS or direct administrator database writes are outside application isolation; checksum verification detects altered evidence.

## Evidence and limitations

See `PHASE_12_PILOT_RESULTS.json`, `PHASE_12_SYSTEM_WORKFLOW.json`, `PHASE_12_RESTORE_RESULTS.json` and the Phase 12 exit matrix. Real stored Binance tests are distinct from synthetic golden tests. Upstox/Alpaca authenticated live validation remains DEFERRED_NOT_CONFIGURED with verified market mappings/calendars still required. Options/news/on-chain/event coverage and live owner personalization remain unavailable. No genuinely unseen prospective validation or scientifically supported profitable edge has been established.
