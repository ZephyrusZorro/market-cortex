# Phase 7 exit matrix — 2026-10-04

**Status:** Complete for the Binance Pilot 5 journal/prediction/learning research scope. **Release:** `phase7-v0.7.0`; **commit reference:** `phase7-v0.7.0^{commit}` resolves to the final accepted implementation commit. **Baseline preserved:** `phase6-v0.6.0` at `a8acbc9`. No external push. All development, synthetic fixtures and persistence validation use the isolated `PILOT_TEST` PostgreSQL catalog ending `_test`; the owner main database was not modified.

## Acceptance

| Gate | Result | Evidence |
| --- | --- | --- |
| A — Phase 1–6 regression | Pass | Final complete suite passed twice: 125 tests and 13 subtests each, all integrations enabled and no skips. Existing storage/identity/calendar/provider/API/backup/analytics/workstation/CORTEX/opportunity/risk tests remain enabled. |
| B — Structured/versioned journal | Pass | Typed local drafts and full append-only revisions, reason, timestamps, optimistic conflicts, instrument/research links and original classification; historical preservation in PostgreSQL/API tests. |
| C — Prediction ledger | Pass | Seven typed daily expectations, exact rule/horizon/benchmark, explicit creation source, frozen original payload and separate status revisions; API/CLI/UI. |
| D — Frozen original context | Pass | Original manifest/as-of, baseline observation, canonical features, market state, detector/version, thesis/run/risk context and hash remain unchanged after outcome evaluation. |
| E — Deterministic outcomes | Pass | Golden known-price cases for return, relative confirmed/invalidated/tie, close survival/hold/invalidation, strength persistence and canonical volatility; null unknowns and separate evaluation lineage. |
| F — No future leakage | Pass | Source publication/cutoff guards, no features past baseline, exact calendar horizon, future bar end/availability gates, historical status reads, risk recording visibility, exact journal revision boundaries and no backward current evaluation cutoff. Dedicated regression tests passed in both final runs. |
| G — Registration distinction | Pass | PRE_REGISTERED and RETROSPECTIVE_EVALUATION contracts, application/database-clock guard, separate cohorts and explicit UI/CORTEX labels. Historical fixtures never masquerade as forecasts. |
| H — Version-aware performance | Pass | Groups separate detector/version, registration, classification, metric, horizon, comparator, threshold and benchmark; feature/calculation versions and manifests retained. Known version segregation fixture. |
| I — Rejection coverage | Pass | Actual Phase 5 ledger events count candidate/rejected/NO_EDGE/unsupported/insufficient outcomes at cutoff; distinct from explicit prediction outcome samples. |
| J — Sample disclosure | Pass | N/usable/missing/excluded/outcome counts, per-distribution/segment N, minimum 30 usable and small-sample/overlap/selection warnings. No calibrated probability claim. |
| K — Failure/lesson memory | Pass | Explicit journal categories and supported owner notes, deterministic pattern counts and CORTEX evidence; no invented mistakes from loss alone. |
| L — Edge foundation | Pass | Immutable owner hypothesis, detector/version/registration/regime, frozen report/statistics and sample counts; remains HYPOTHESIS, no automatic promotion. |
| M — Grounded CORTEX outcomes | Pass | Six fixed read-only learning tools, exact original rule/outcome, evidence citations and saved run/hash replay (`b46e7276-fc52-4f24-b5a2-47c3ebd8b68d`). Cloud privacy gate tested. |
| N — Workstation | Pass | Journal/revision/post-mortem, Prediction Ledger/frozen original/evaluations, Review Queue, descriptive Performance/quality filter, Lessons & Edges; thesis/run links. Automated frontend tests and live isolated browser inspection. |
| O — Privacy | Pass | Journal/prediction/portfolio context blocked from cloud despite broad cloud flag; loopback API, validated schemas/fixed proxy allowlist, parameterized SQL; runtime/notes/secrets remain ignored. |
| P — No self-modification | Pass | CORTEX tools read only; outcome engine code determines statuses; hypothesis saves do not alter detector, strategy, risk, model or gateway rules. |
| Q — No execution | Pass | Provider requests remain GET-only; learning writes only local research records. No order/trading route or inferred execution/realized P/L. |
| R — Repeated complete suites | Pass | 125 backend tests + 13 subtests twice; 18 frontend tests twice; typecheck and production build passed. |

## Contracts and calculations

- Migration `0006_journal_learning.sql`; authoritative typed/schema-registry JournalEntry, PredictionRecord and PredictionEvaluation. The other existing registry contracts compare equal to Phase 6.
- Horizon = next 2–20 open calendar sessions, with UTC crypto weekends and explicit holiday/missing-calendar tests. Missing observations never extend/shift the exact due session.
- Comparators are gt/gte/lt/lte; strict equality is INCONCLUSIVE. Returns are fractional; close rules use native levels. Annualized volatility reuses Phase 2's 20-session feature.
- Statuses: OPEN → PENDING_EVALUATION or CONFIRMED/INVALIDATED/INCONCLUSIVE/UNMEASURABLE; unresolved cancellation requires reason. Later corrections append evaluations. Identical input retries reuse stored ID and recording time; new earlier cutoffs cannot replace a later current outcome.
- Close-only excursions and optional hypothetical forward R are research measurements. No entry/exit fill, intraday stop, fees, execution or realized trade outcome is inferred.
- Performance uses transparent mean/median/sample standard deviation/interpolated quartiles; cohorts and evidence/regime/volatility segments expose exact N. Confirmation fraction is descriptive with its denominator. N ≥ 30 is a minimum disclosure policy and never proof of an edge. Probability/Brier/bootstrap/causal metrics are deferred.

## Public Binance data and stored learning chain

Public daily refresh succeeded for **BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT and XRPUSDT** through the completed **2026-10-03** session. Each stored one new complete raw bar with zero duplicates/quarantines and a new immutable descendant manifest. New head: `f87c2a62-7cdf-443d-8eed-0575b6dd8e17`. Read-only storage inventory: **85 referenced artifacts; no unreferenced, missing or corrupt files; no staged files or deletion**. The Windows `r+b` fsync fix is preserved.

The isolated script `scripts/validate_phase7_pilot.py` explicitly saved three SYNTHETIC_TEST research fixtures using actual stored prices and an existing Phase 5 momentum thesis (`8f255e20-c25c-4173-a71e-8964cdf29d22`). Synthetic refers to the demonstration expectation/notes; the public prices are real stored observations.

| Expectation | Registration | Baseline → due | Result | Metric / coverage |
| --- | --- | --- | --- | --- |
| BTC five-session forward return > 0 (`cdce1c35-d5cd-4880-b9a8-d652745af3c5`) | RETROSPECTIVE_EVALUATION | 2026-09-23 → 2026-09-28 | INVALIDATED | −0.01063526 fraction; 5/5 sessions |
| BTC five-session return minus ETH > 0 (`c91057a7-1aec-46f8-86d3-a0ef68ede7c0`) | RETROSPECTIVE_EVALUATION | 2026-09-23 → 2026-09-28 | INVALIDATED | −0.01212517 fraction; 5/5 sessions |
| BTC five-session forward return > 0 (`087ba407-2c4d-4732-952e-8b9c65b566a2`) | PRE_REGISTERED | 2026-10-03 → 2026-10-08 | PENDING_EVALUATION | null; 0/5, horizon not complete |

Historical source freshness is **stale** and explicitly warned; the pending pre-registered source is current at creation. Neither historical result establishes forecasting accuracy. At the initial measurement cutoff there were N=3 predictions, usable N=2, and **314 candidate/rejection ledger events**. The three rule/registration cohorts each have N=1. Later test scans can append ledger events; these are not additional independent evaluated predictions.

Saved chain: journal post-mortem `b0f918df-88ca-42ee-b77d-24674fffd010`; explicit demonstration lesson `e41c93b7-2c1d-48c2-a9fe-265a27f3a042`; Edge hypothesis `b17658b5-c24d-4403-8a61-5d13cb639b90` (HYPOTHESIS, usable N=2). All are synthetic, local and linked. The generated template leaves owner-judgment prompts unanswered instead of manufacturing a lesson or trade.

Final calculation/tool measurement at `2026-10-04T12:34:48Z`: the three existing fixtures were evaluated under the final calculation hash, preserving the original context hashes and earlier evaluation history. Exact retries reused the stored IDs. The two historical metrics remain unchanged; the pre-registered metric remains null. Performance reports N=3, usable N=2, eligible usable N=0, ledger-event N=354. Batched descriptive report took **0.063 seconds**. Saved CORTEX run `b46e7276-fc52-4f24-b5a2-47c3ebd8b68d` explains the original prediction and linked private template, uses the deterministic local fallback, and completed in **0.894 seconds**. After both final regression runs, all eight replayed tool hashes still matched and **evidence_reproducible=true**. Replay verifies evidence; natural-language regeneration is not claimed (`language_reproducible=false`).

Earlier development run `08b5d08b-d782-494d-a3a6-dd95fc666370` replayed at its creation; subsequent development changed performance tool output, so it is a development artifact and is not the release replay acceptance evidence.

## Verification results

- Final targeted Phase 7 run: **31 tests passed in 20.98 seconds**, including a self-contained synthetic risk recording guard and exact journal revision boundaries. Golden rules and isolated persistence checks passed. The new risk test initially depended on a pre-existing snapshot that earlier tests clean up; its fixture now creates/removes its own guarded portfolio/snapshot and preserves all original assertions.
- Initial full run: 122 passed / 2 failed / 13 subtests passed. Both failures were PostgreSQL connection timeouts, including an existing Phase 1 job test. This run is not acceptance evidence. Subsequent direct connection measurements were 0.025–0.142 seconds; temporary UI servers were stopped before clean reruns. No timeout gate was weakened.
- Preliminary clean full runs: 124 passed / 13 subtests passed in 155.80 and 152.55 seconds, before the final safeguards and added risk visibility case.
- **Final complete backend runs: 125 tests + 13 subtests passed twice**, in **154.76 s / 158.02 s**, with no skips. All PostgreSQL, encrypted restore and Phase 3–7 pilot integrations were enabled. Local ignored evidence logs: `runtime/phase7-backend-final-7.log` and `runtime/phase7-backend-final-8.log`.
- Final frontend: **18 tests across 6 files passed twice** (1.95 s / 1.96 s); typecheck and production build passed. These include journal creation/revisions, retrospective labeling, null missing-session outcomes, accepted post-mortems, queue counts, rejection coverage and sample limits.
- Live browser QA on the loopback isolated API/workstation confirmed stored journal/template/revision, exact −0.01063526 outcome and immutable hash/manifest, stale warning, PRE_REGISTERED pending status, due N=0, descriptive N=3/usable N=2, eligibility filter usable N=0, explicit lessons and HYPOTHESIS status. Report cutoff is shown separately from source market context. Temporary test servers/tabs were stopped afterward.
- One known Starlette/TestClient/httpx deprecation warning remains; no functional failure is attributed to it.

## Security and scope

No owner notes, tokens, DSNs containing credentials, database exports or downloaded market artifacts are included in this report or release. Development used a dedicated local test role/catalog and loopback servers. Existing private-model policy remained enforced. Provider source inspection and regression tests retain safe missing-credential behavior and GET-only adapters.

Upstox/Alpaca authenticated India/US validation and verified equity mappings/calendars remain **DEFERRED_NOT_CONFIGURED**. No credentials were requested. Trusted FX conversion, portfolio equity-curve drawdown, realized execution/R history, probability calibration, event/fundamental predictions and intraday excursions remain unavailable/deferred.

Phase 7 establishes reusable original-context, evaluation and cohort contracts for later experimentation. **Phase 8 has not begun**. A future Phase 8 request may build systematic backtests, walk-forward, Monte Carlo and sensitivity analysis on these records; the tiny retrospective pilot sample provides no edge or causal performance claim.
