# Phase 10 exit matrix — 2026-10-05

**Status: COMPLETE — acceptance A–T passed.** Release: annotated local tag `phase10-v0.10.0`; `phase10-v0.10.0^{commit}` identifies the accepted implementation. Baseline `phase9-v0.9.0` at `4fd3d1b53d004a7b789f06d8f75c704b3f42872f` is preserved. No push; Phase 11 has not begun.

Canonical repository: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`. Validation uses PostgreSQL 17 on loopback 55432, dedicated `_test` databases and isolated/disposable schemas. The owner main database on 5432 and `C:\MarketCortexData` were not modified.

## Acceptance A–T

| Gate | Result / evidence |
| --- | --- |
| A — Phase 1–9 regression | Both full runs: 236 backend tests + 13 subtests each, no skips; all PostgreSQL/restore/Phase 3–10 pilot gates enabled. |
| B — Structured research plans | Typed subquestions, exact tool/arguments, expected evidence, dependencies, required/optional status and current/previous scope; plan saved before execution. |
| C — Policy validation | Explicit capability allowlist, domain/exclusion/privacy policy, typed inputs, pinned manifest/context, DAG/depth, zero-cost and bounded experiment checks; forbidden-tool/cycle/override tests. |
| D — Autonomous approved tools | Actual stored-data pilot dossiers invoke features/state/context/scans, saved Quant, memory, candidate challenge and comparisons through registered local services. |
| E — Tool/model budgets | Counters charged before calls, hard caps/deadline, zero-cost literal, model privacy gate; exhaustion/resume/mock/remote tests. |
| F — Bounded replanning | Failed tool retries and a negative-OOS-triggered canonical candidate challenge are recorded; planner/replan/tool limits enforced. |
| G — Persistence/replay | Append-only hashed checkpoints, optimistic head and lease, versioned frozen references; all six actual pilot dossiers replay; missing implementation reported explicitly. |
| H — Grounded claims | Claim → evidence → tool → feature/context/backtest → manifest → observation/source graph; all important material claims cite canonical evidence. |
| I — Numeric integrity | Fact/calculation/classification ledger requires exact deterministic value reference/rendering; fabricated positive-return/unknown model-ID tests reject synthesis. |
| J — Skeptic/alternatives | Freshness/conflicts/RSI/negative OOS/canonical rejection checks; hypotheses have explicit statuses/test requirements; beta/volatility/derivative alternatives remain noncausal/inconclusive. |
| K — Quant incorporation | Actual saved walk-forward, robustness, sensitivity, Monte Carlo/comparison IDs/hashes/recording times; bounded preregistered registered-backtest test passes. |
| L — Negative evidence visible | All six dossiers preserve −7.82% momentum temporal OOS, N=82; historical-support hypothesis is CONTRADICTED. No supported edge claimed. |
| M — Point-in-time safety | Manifest ancestry/created time, context cutoffs, earlier checkpoint retrieval, candidate/thesis recorded times and frozen Quant recording times enforced; old-manifest pilot has no future context facts. |
| N — Prompt injection boundary | Unknown tools/SQL/shell/provider-sync/credentials/order paths rejected; source prose filtered from model candidates; hostile UI text is escaped. |
| O — Privacy | Local-only API/proxy, private-domain opt-in, filtered curation payloads, remote model blocked under ₹0 policy; no owner data or credentials sent to cloud. |
| P — Cancellation/recovery | Tests cancel during a call, preserve completed checkpoints, simulate process interruption, skip finished work on resume, preserve counters/scopes/deadline and handle stale revisions. Final hardening adds 60-second mission/job leases renewed every 15 seconds, active-worker rejection and an abandoned-process/queue-lease recovery test. |
| Q — Research Lab | Browser-verified create → structured plan → job execution → INCONCLUSIVE → citation/source inspection → VERIFIED replay. History wrapping/current status fixed after visual QA. |
| R — Model independent | Deterministic planner/evaluator/report work without an LLM; local/malicious/cloud mock gateways exercised. |
| S — Research only | No broker order/trade/transfer/source mutation/strategy rewrite/risk limit/Edge promotion capabilities. Pilot canonical catalog counts unchanged by missions. |
| T — Repeated suites | Frontend 28 tests passed twice; typecheck and production build passed twice. Backend 236 tests + 13 subtests passed twice, with no skips. |

## Delivered architecture and boundaries

One controlled orchestrator performs scope → plan → validation → deterministic evidence → hypothesis tests → alternatives → skeptic/adversarial review → claim grounding → cited dossier. Typed mission contracts/schema, capability metadata, explicit budgets, append-only checkpoint/hash store, cancel/resume, duplicate reuse/fresh policy, historical research memory, structured diffs and existing durable JobQueue integration are implemented.

Modes: QUICK, DEEP, HISTORICAL, STRATEGY, THESIS and CHANGE research. Templates: instrument deep dive, Pilot market review, thesis challenge, strategy review, what changed, historical, event/context. Required missing domains yield waiting; budget/failure yields partial work; inconclusive research is a valid completed investigation. No recurring autonomous scheduler or self-modifying memory is introduced.

Quant autonomy is limited to an exact owner-approved registered definition with a matching scope, at most 31 calendar days and a declared new-run budget. Hypothesis/definition/one-combination search/metrics/evaluation plan are recorded before computation. New results are labelled retrospective counterfactual and cannot become historical information known at the market cutoff. Canonical strategies/detectors/risk limits and Edge Library status remain unchanged.

The evidence evaluator exposes counts/coverage, freshness, contradictions, source/tool diversity, actual Quant sample count, independence limits and rejected claims. There is no invented confidence probability. The report/graph supports claim-to-source inspection. Replaying approved deterministic outputs is separate from reproducing model wording; incompatible loaded code reports `ORCHESTRATION_VERSION_UNAVAILABLE`.

## Actual Pilot 5 validation

Source: existing immutable market head `3bf002d2-15f2-4f9d-8c54-cc7eb3fb349c`, context head `158ad3f7-aab9-5d41-b79f-05eef01bc207`; five Binance spot pairs, 1,007 daily sessions each. Context catalog retains 1,234 observations including revisions; latest visible context is narrower. No new external market fetch was needed for Phase 10 missions. Final pilot run: 2026-10-05T17:47:34.034367+00:00.

| Mission | Persisted ID | Result | Tools | Work latency | Evidence |
| --- | --- | --- | --- | --- | --- |
| A — Comprehensive BTC | `800e1535-acd9-474d-9d7c-3a5ba45af4be` | INCONCLUSIVE, replay verified | 8 | 11.31s | 240 |
| B — ETH versus BTC | `d016bec1-7835-4928-8d6d-cb6c6520a80f` | INCONCLUSIVE, replay verified | 9 | 13.27s | 239 |
| C — Strongest current candidate challenge | `a6d799f8-f3ef-493c-8a79-6c249248876a` | INCONCLUSIVE, 55 counter-evidence artifacts, replay verified | 8 | 13.35s | 265 |
| D — Momentum historical support | `d75bcaa5-88bd-4c84-b2a1-cacf92ae9c66` | INCONCLUSIVE; saved historical-support hypothesis CONTRADICTED, replay verified | 10 | 12.02s | 263 |
| E — Derivatives + Treasury context | `69b04aea-65e1-4975-9273-49ac319bbd80` | INCONCLUSIVE; actual contextual values/limits, replay verified | 8 | 11.69s | 240 |
| F — Current versus older BTC manifest | `e16ba5ed-51be-4f85-9a4d-17f0e17cafdd` | INCONCLUSIVE; 3 bounded historical comparisons, replay verified | 11 | 12.86s | 294 |

All important numerical claims passed grounding; all six retained **−0.07817165407921722 (−7.82%), N=82** from the actual stored Phase 8 walk-forward study. This remains a reset-capital-fold aggregate on selected/dependent trades, not a continuous executable portfolio or a supported momentum edge.

Before/after pilot canonical counts matched: 5,035 market observations, 1,234 context facts, 433 opportunity candidates, 52 thesis versions, 10 portfolio versions, 3 predictions, 2 journal revisions and 158 Quant artifacts. Only mission/checkpoint artifacts were created. Existing regression tests create their separate research test artifacts outside this isolated six-mission count comparison.

Evidence: [pilot JSON](../cortex/PHASE_10_PILOT_RESULTS.json), mission dossiers [A](../cortex/PHASE_10_MISSION_A.md), [B](../cortex/PHASE_10_MISSION_B.md), [C](../cortex/PHASE_10_MISSION_C.md), [D](../cortex/PHASE_10_MISSION_D.md), [E](../cortex/PHASE_10_MISSION_E.md), [F](../cortex/PHASE_10_MISSION_F.md). Dossiers include internal evidence citations resolvable through the API/Research Lab.

## Model configuration actually used

No `ollama`, `lms` or `llama-server` command was found; checked conventional local runtime ports 11434/1234/8080 were not listening. No real local model was assumed, downloaded or installed. Actual pilot model provider: **deterministic**, zero model calls, ₹0 API cost. Local curation, malicious responses and remote privacy/cost blocking were validated with explicitly labelled mocks. Owner credentials/privacy settings were not altered.

## Tests and workstation verification

Phase 10 adds 44 backend cases: 19 pure planner/claim-policy cases, 19 isolated PostgreSQL/Parquet/API/job/recovery/model/experiment cases, and 6 actual pilot replay cases. Frontend adds four Research Lab journeys. Prior regression gates include storage/identity/calendar/as-of, encrypted backup/restore, indicators/state, CORTEX v1, opportunities/theses, portfolio risk, learning/journal, Quant and contextual intelligence.

Both complete backend gates: **236 passed + 13 subtests** each, 388.28 and 388.90 seconds, no skips. Only known warning: Starlette TestClient/httpx deprecation, not a functional failure. Frontend final gates: **28 passed twice**; TypeScript and Next.js production builds passed. Logs are local ignored runtime artifacts and contain no intentionally logged credentials/DSNs.

Browser QA used loopback pilot API/workstation ports 8001/3002. An actual goal produced a READY plan, eight approved tool calls, one recorded negative-OOS replan, INCONCLUSIVE dossier, ₹0 cost and verified replay. The negative OOS citation resolved to the immutable walk-forward study and loaded its actual `oos_N` source payload. Long history titles wrap and the selected mission history reflects its current checkpoint. [Browser QA screenshot](../workstation/PHASE_10_RESEARCH_LAB_QA.jpg).

## Known limitations and Phase 11 readiness

- No supported edge or causal explanation was established. Daily pilot bars/context can be stale; strict knowledge availability is not freshness. Hypotheses remain descriptive and bounded to the selected Pilot 5.
- Deterministic goal decomposition and claim-ID curation are intentionally narrower than an unrestricted language agent. Optional real local-model integration remains untested without an installed runtime.
- Upstox/Alpaca live authenticated India/US validation remains **DEFERRED_NOT_CONFIGURED**, awaiting credentials plus verified instrument mappings/calendars. Adapters and missing-credential/read-only regression checks remain intact.
- Live licensed news, verified events, options, on-chain and fundamentals remain deferred. Unavailable data are shown explicitly; no synthetic fixture is represented as a live source.
- Existing Quant artifacts are inspected; optional new research is a small registered backtest. No autonomous broad parameter search or newly generated strategy code is permitted.
- Cancellation is checked around bounded local tools. Resume preserves exhausted counters/deadline and cannot obtain newly arrived data or extend a mission; create a new investigation/change analysis for that.
- Mission history, reports and references are local. No vector database, unrestricted memory, agent swarm, cloud upload, microservice stack or capital execution was introduced.

Phase 11 may be considered after this release is accepted. No Phase 11 development or adaptive rule changes are included.
