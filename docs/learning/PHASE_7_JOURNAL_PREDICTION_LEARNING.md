# Phase 7 — Journal, prediction ledger and learning

Version: `0.7.0`. Scope: private daily-bar research over Binance Pilot 5. Learning means recording expectations, evaluating exact rules, measuring outcomes and summarizing evidence. Phase 7 does not change detector, strategy or risk rules automatically.

## Records and history

`JournalDraft` supports observations, research/thesis/decision notes, reviews, mistakes, lessons, hypotheses and outcome reviews. It stores title, private notes, bounded structured fields, tags, instrument and research links, manifest, effective cutoff, classification and author. `JournalEntry` adds its ID, creation/recording timestamps, revision and frozen linked context.

Every edit appends a complete `journal_revisions` payload and an explicit reason. An expected-revision check rejects concurrent stale edits. Original classification is immutable. The head pointer changes; earlier payloads remain available. `as_of` describes the note's effective market context; recording time identifies when the note was actually written. The revision row and payload use the same recording timestamp; historical list reads select the last revision recorded by the requested cutoff, including exact boundary tests. Editing a CORTEX template creates an owner revision, preserving the template's authorship in history.

`PredictionDefinition` requires a supported symbol, exact metric, comparator, threshold, 2–20 sessions, manifest and UTC cutoff. Optional links include candidate, thesis, ResearchRunManifest, risk snapshot and explicit portfolio/position. Creation is an owner action, accepted CORTEX suggestion or thesis milestone; there is no background prediction generator.

`PredictionRecord` freezes the definition, baseline price/observation, feature values/IDs/versions, market state, qualitative evidence strength, detector/version, calendar horizon, linked evidence and original context hash. Later evaluations cannot modify this payload. Thesis links resolve the version known at the source cutoff. Portfolio links require an explicit position and preserve the visible portfolio version; no trade is inferred.

`prediction_revisions` holds status changes separately. `PredictionEvaluation` is immutable and records both manifests, cutoff, actual recording time, original hash, calculation version/code hash, observation/feature IDs, coverage, quality, freshness, metric and warnings. Corrected data can create a new evaluation without rewriting the original expectation or earlier outcome.

Migration: `infra/migrations/0006_journal_learning.sql`. Contracts are registered in `packages/contracts/registry.schema.json`.

## Registration and time

| Registration | Meaning |
| --- | --- |
| `PRE_REGISTERED` | Recorded before the first forward session completed. The daily-bar policy uses completed sessions, not session opening. Both application and database-clock guards reject an already completed first outcome session. Future bars must end and become available after registration. |
| `RETROSPECTIVE_EVALUATION` | Explicit historical research created after outcomes could already be known. Its results never become pre-registered forecasting evidence. |

The source cutoff cannot be in the future or precede source-manifest publication. Baseline data and linked artifacts must be visible at that cutoff, including the actual recording time of risk snapshots. Synthetic risk context requires a synthetic learning record. Source features and state cannot read beyond the baseline. The source manifest must be an ancestor of the evaluation manifest. Manifest and valid/available time constraints remain Phase 1's canonical read policy.

The horizon is the next N **open calendar sessions** after baseline. Crypto sessions are UTC daily, including weekends. Future equities require verified venue calendars; holidays are skipped and unavailable calendars fail explicitly. Missing observations do not shift the due session or compress the horizon.

## Deterministic rules

All returns and thresholds use fractions: `0.05` means 5%. Close-level thresholds use native quote-price units. Comparators are `gt`, `gte`, `lt`, `lte`; exact equality under a strict comparator is inconclusive. These are research rules rather than executed strategy returns.

| Type | Evaluation metric |
| --- | --- |
| `forward_return` | Final close / frozen baseline close − 1 |
| `relative_performance` | Instrument forward return minus benchmark forward return |
| `relative_strength_persistence` | Minimum of same-session cumulative instrument-minus-benchmark return over the horizon |
| `thesis_survival`, `breakout_hold` | Minimum horizon close compared with an explicit positive level using `gt`/`gte` |
| `invalidation` | Minimum horizon close compared with an explicit positive level using `lt`/`lte` |
| `volatility_state` | Existing Phase 2 annualized 20-session volatility at the due session; no replacement formula |

Thesis survival measures the explicit close rule. A Phase 5 `VALID` state does not imply profitability. Event/fundamental outcomes and regime-transition predictions are deferred until trusted inputs and rules exist.

Close-only adverse/favorable excursions include the baseline zero return and all exact horizon closes. They do not represent intraday MAE/MFE. Optional hypothetical forward R is `(final close − baseline close) / (baseline close − explicit invalidation)`, for positive long-side risk distance. It assumes no execution, stop fill, fee or realized P/L.

### Lifecycle and retries

- Creation records `OPEN`.
- Before the due session closes, evaluation records `PENDING_EVALUATION` with null outcome.
- Complete data yields `CONFIRMED`, `INVALIDATED` or strict-boundary `INCONCLUSIVE`.
- Missing required horizon sessions yield `INCONCLUSIVE`; unavailable metric history yields `UNMEASURABLE`. Neither is invented success/failure.
- An unresolved record may become `CANCELLED` with a reason; confirmed/invalidated records cannot be cancelled to hide an outcome.
- A later cutoff or corrected descendant manifest may append a new evaluation. A new evaluation cannot move the current evaluation cutoff backward. Identical retries return the original stored evaluation without adding revisions.

Evaluation identity includes canonical inputs, original hash, manifest, cutoff and calculation hash, while excluding the wall-clock recording time. Historical prediction reads select only revisions/evaluations actually recorded by that cutoff. Replaying an old cutoff never presents a subsequently recorded outcome as known then.

## Performance and honest samples

The report batches catalog reads, then groups predictions by detector ID/version, registration, classification, prediction type, horizon, comparator, threshold and benchmark. Feature versions and both source/evaluation manifest sets are exposed. Unrelated rules and versions are not silently pooled.

Each cohort exposes N, usable N, missing/inconclusive N, excluded-quality N, all status counts, usable confirmed/invalidated counts, and measured confirmation fraction with its denominator. Pending, cancelled and inconclusive records stay visible. `eligible_only=true` requires valid evaluation coverage and current prediction-time freshness; excluded records remain counted.

Descriptive mean, median, sample standard deviation and interpolated quartiles are returned for forward returns, defined metric, benchmark return, close excursions and available hypothetical R. Each distribution has its own N. One observation has no sample standard deviation. R expectancy is mean hypothetical R with its N, never a guaranteed future return.

Evidence-strength, deterministic regime and volatility-regime segments expose usable counts and returns. Research-run linkage and structured counter-evidence presence are counted; freeform prose correctness is not scored. The candidate/rejection ledger separately counts actual accepted, rejected, `NO_EDGE`, unsupported and insufficient-evidence detector events at the cutoff. Its N is a ledger-event count, not independent trades. Only explicit predictions have forward outcomes, so rejection visibility reduces hidden selection but does not eliminate selection bias.

Minimum descriptive sufficiency is **30 usable observations per compatible cohort**. This is a disclosure threshold, not proof of an edge or calibrated confidence. Overlapping horizons, observational selection and retrospective bias remain warnings even above 30. There are no numeric forecast probabilities, Brier scores, bootstrap intervals, causal claims or automatic recalibration in Phase 7.

## Lessons, hypotheses and post-mortems

Failure memory counts explicit supported journal categories such as stale data, insufficient history, ignored contradiction, undefined invalidation, concentration, late thesis, missing participation and overlooked correlation. No mistake is inferred from a losing research outcome alone.

Edge Library entries are owner hypotheses with detector/version, registration, optional regime and frozen supporting statistics/report ID. The Phase 7 status remains `HYPOTHESIS`; no threshold crossing automatically promotes it to proven/supported or changes a strategy.

An evaluated prediction can produce a CORTEX evidence template containing original rule/hash, actual outcome, recorded contradictions, data limits and owner prompts for what was missed/done correctly and the reusable lesson. It remains unsaved until accepted through the local journal workflow. Owner observations and generated templates remain distinguishable.

## Workstation and API

Open **Journal & Learning** for Journal, Prediction Ledger, Review Queue, Performance, and Lessons & Edges. Journal supports create, revision, reason, timeline, search, tags and links. Predictions expose original context, status history, evaluation lineage/quality and post-mortem drafting. Review Queue includes all unresolved/due records and recent outcomes. Evaluation is explicitly invoked with the active manifest and cutoff; no scheduler/daemon is required.

Thesis and saved CORTEX run detail show related predictions, statuses and journal/post-mortem/lesson records. The workstation performs display and local writes; canonical numerical evaluation remains Python.

Routes under `/api/v1/learning`:

| Route | Method / purpose |
| --- | --- |
| `/journal`, `/journal/{id}` | GET list/detail; POST create on collection |
| `/journal/{id}/revisions` | GET history; POST append validated revision |
| `/predictions`, `/predictions/{id}` | GET ledger/detail with historical cutoff; POST create on collection |
| `/predictions/{id}/evaluate`, `/cancel` | POST exact evaluation or unresolved cancellation |
| `/predictions/{id}/postmortem` | GET unsaved evidence template |
| `/evaluations/{id}` | GET immutable outcome |
| `/review-queue`, `/evaluate-due` | GET queue; POST explicitly evaluate all due unresolved records |
| `/performance`, `/failures`, `/links` | GET statistics, explicit lesson patterns, thesis/run linkage |
| `/edges` | GET hypotheses; POST save owner hypothesis and frozen statistics |

Recent list endpoints are bounded to 100 journals/200 predictions/100 hypotheses. Complete performance, due queue, failure counts and thesis/run link queries do not use those recent-list limits. Individual IDs and journal revisions remain inspectable.

CLI operations: `create-prediction --definition <local JSON>`, `evaluate-prediction <id> --manifest-id <id> --as-of <UTC>`, `evaluate-due-predictions`, `inspect-prediction`, `learning-performance --eligible-only`, `review-queue`. The evaluation commands require explicit manifests/cutoffs. `research` also accepts `--prediction-id` and `--journal-entry-id`.

## CORTEX and privacy

Six approved read-only tools expose ledger, exact prediction/outcome, performance, journal, exact entry and hypotheses: `learning.predictions`, `learning.prediction`, `learning.performance`, `learning.journal`, `learning.entry`, `learning.edges`. Evidence is versioned, cited and pinned; saved research replay verifies its hashes rather than claiming to regenerate identical language. The answer reports observed metrics and sample limitations. It cannot author canonical outcomes, mutate rules, mark an edge proven, issue SQL or access arbitrary files.

Learning/journal/portfolio context is private. The ModelGateway privacy policy blocks cloud transmission even when the broad cloud-model flag is enabled. Local models or the deterministic fallback can explain evidence; no model is required. FastAPI and the workstation proxy remain loopback-only with validated schemas and fixed route allowlists. Logs must exclude notes and credentials. Owner configuration, downloaded data, runtime measurements and database backups remain Git-ignored.

Synthetic fixtures require `PILOT_TEST` **and** a database name ending `_test`. Development uses the isolated public Binance catalog, never the owner main DB. Run the normal `migrate` command when deliberately adopting this release in an owner environment.

## Validation and remaining scope

Golden arithmetic cases, exact-session/calendar tests, immutable original context, historical cutoffs, idempotent revisions, detector/version/registration segregation, rejection counts, local API/CLI/CORTEX integration, cloud privacy and frontend tests cover the foundation. The [exit matrix](../planning/PHASE_7_EXIT_MATRIX_2026-10-04.md) records repeated complete-suite and stored-pilot evidence.

The pilot's historical outcomes are explicitly retrospective and very small. A real pre-registered expectation remains pending until actual later complete bars are stored. India/US authenticated validation and verified mappings/calendars remain `DEFERRED_NOT_CONFIGURED`. Trusted FX, portfolio equity-curve drawdown and realized execution/R history remain unavailable. Phase 8 backtesting, walk-forward, Monte Carlo and systematic experiment machinery have not begun.
