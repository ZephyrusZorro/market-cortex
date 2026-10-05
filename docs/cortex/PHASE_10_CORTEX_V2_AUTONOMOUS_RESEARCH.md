# CORTEX v2 — bounded autonomous research

Phase 10 adds one deterministic orchestrator over existing MARKET CORTEX research services. It interprets a typed goal and Pilot 5 instrument mentions, freezes knowledge scope, plans approved tool calls, gathers evidence, tests descriptive hypotheses, challenges positive interpretations and saves a cited dossier. A local model may curate existing claim IDs. The system functions without a model.

## Architecture

```mermaid
flowchart LR
  G[Typed research goal] --> S[Freeze scope and references]
  S --> P[Structured deterministic planner]
  P --> V[Capability and budget policy]
  V --> T[Approved local research tools]
  T --> C[Append-only checkpoints]
  C --> H[Hypotheses and alternative tests]
  H --> K[Skeptic and adversarial review]
  K --> E[Claim grounding and evidence graph]
  E --> R[Cited mission dossier]
```

Implementation: `mission_contracts.py`, `mission_policy.py`, `mission_store.py`, `mission_evaluator.py`, `missions.py`, `mission_api.py`. Contracts also export to `packages/contracts/research_mission.schema.json`. PostgreSQL migration `0011_research_missions.sql` adds mission heads and append-only hashed checkpoints. Existing Parquet/manifest storage remains authoritative for market and contextual observations.

## ResearchMission and lifecycle

Each checkpoint captures the owner request, goal, mode/template, instruments, universe, horizon, approved/required/excluded domains, budgets/usage, frozen current/earlier market and context scopes, structured plan, tool outputs/hashes, source references, hypotheses, claims, contradictions, limitations, preregistered experiments, quality dimensions, graph, report, model metadata and implementation version.

`CREATED → PLANNING → READY → RUNNING → COMPLETED / INCONCLUSIVE / WAITING_FOR_DATA / PARTIAL / FAILED`. Cancellation is available before or during work. Terminal completed/inconclusive/cancelled investigations do not execute again. Partial/failed/waiting missions may resume when their original scope remains valid and budget/deadline remains. A mission without a visible initial scope stays waiting; new information requires a new mission. The transition table, optimistic revision checks and execution lease enforce state changes. Mission and job leases last 60 seconds and renew every 15 seconds in local process-bound heartbeats. An OS-killed worker therefore becomes reclaimable before the default 120/300-second deadline; stale leases cannot save or renew. Resume rejects an active worker and can recover an abandoned RUNNING checkpoint after lease expiry.

Checkpoints are sealed with SHA256 of typed content. Reads verify the payload and seal. Worker counters are charged before calls and persist through crashes. A worker may retry an interrupted step; finished steps are reused. Counter resets, scope/reference changes, budget changes and deadline resets are rejected. Cancellation preserves completed outputs and a cancellation checkpoint. In-progress local tools finish their bounded call before the worker observes cancellation; their outputs are discarded after cancellation. A crash cannot resume into current head.

## Scope and historical correctness

Market manifests must exist at or before the explicit knowledge cutoff. With no pin, the resolver walks the current manifest ancestry to the most recent known ancestor. This handles equal source timestamps without choosing an arbitrary partial manifest. Context manifests use their own knowledge cutoff. Missing identity, historical manifests or context remain unavailable.

Earlier mission memory is retrieved by the last checkpoint recorded **at the historical cutoff**, not the current mission head. Quant artifact IDs/hashes and actual catalog recording times are frozen at creation; static report timestamps never establish artifact visibility. Recorded candidates and thesis versions are checked against creation/update time as well as their source scope. External historical facts retain their original availability/ingestion timestamps. Price reconstruction never grants retrospective knowledge of context.

Default latest missions can reuse an identical recent investigation within one hour when goal, policy, market/context manifests and implementation match. Explicit pinned requests are idempotent by request/scope/version. `duplicate_policy=fresh` creates a new mission. Relevant older mission IDs and exact checkpoint/hash references remain inspectable; they are historical research, not present truth or inferred subsequent performance.

## Planning, modes and templates

Every plan step specifies a subquestion, approved tool/typed arguments, expected evidence, reason, dependencies, required/optional status and current/previous scope. Planning happens before tools. Unknown tools, domain conflicts, unsupported overrides, absent scopes, cycles, excessive depth or oversize budgets are rejected.

| Mode | Actual behavior |
| --- | --- |
| QUICK_RESEARCH | Availability + focal features + optional context; normally six calls/120 seconds, no broad scan/state/learning unless needed |
| DEEP_RESEARCH | Features, state, context, ephemeral opportunities, saved Quant evidence, prior missions and bounded adversarial review |
| HISTORICAL_RESEARCH | Mandatory explicit historical cutoff; every source and remembered artifact must have been known then |
| STRATEGY_RESEARCH | Required stored Quant support, descriptive learning/outcomes; optional exact owner-approved bounded backtest definition |
| THESIS_REVIEW | Exact recorded thesis ID/version, condition challenge, status/transitions, outcomes and counter-evidence |
| CHANGE_ANALYSIS | Frozen earlier mission or earlier manifest/cutoff, previous features/context and cited compatible-value/coverage changes |

Templates: instrument deep dive, narrow Pilot market review, thesis challenge, strategy review, what changed, historical investigation, event/context inquiry. Required options/events/news/fundamentals/on-chain domains receive explicit probes. Unavailable mandatory coverage yields `WAITING_FOR_DATA`, even if a snapshot hash is available. Templates are bounded procedures, not generated executable programs.

Replanning is explicit and bounded: one failed approved tool can be retried; nonpositive stored momentum OOS can add one approved candidate challenge if the tool/planner/replan budget allows it. The trigger, proposed action, timestamp and unchanged scope are recorded. No new source, private domain or paid capability is enabled by replanning.

## Budgets and termination

Defaults: 16 tool calls, 2 planner iterations, 1 replan, 0 new Quant runs, 3 historical comparisons, 0 model calls, 300 seconds, ₹0 paid API cost. Quick defaults are six tools/120 seconds. Hard caps: 32 tools, 4 planner iterations, 2 replans, 2 Quant runs, 5 comparisons, 2 model calls and 900 seconds. API cost is the literal zero in the contract.

Policy validates planned work and the executor checks remaining counters, cancellation, deadline and loaded implementation before/after each tool. Deadline starts on first execution and is never extended on resume. Exhaustion persists a partial grounded report and an explicit termination reason. Missing mandatory data stays waiting. Repeated required failures terminate partial work. Completed factual quick research can be `COMPLETED`; attraction/edge investigations can successfully end `INCONCLUSIVE`.

## Approved autonomy

Capability metadata explicitly names tool/version, determinism, access, cost, bounded latency class, privacy, required domains, historical support, autonomy permission and side effects. Future registrations are not automatically safe. The mission API exposes these capabilities.

Read tools cover market data/features/state/comparison, contextual facts/provenance, ephemeral opportunity scans, frozen candidate/thesis inspection, local risk/learning/journal/Edge Library reads and saved Quant artifacts. New tools retrieve frozen OOS evidence and earlier missions, compare pinned states, challenge canonical candidates and run one predeclared registered backtest.

There is no shell, filesystem, SQL, arbitrary Python, browser, credential, source-sync, order, transfer or broker-write capability. The orchestrator cannot change portfolios, predictions, journal entries, detectors, strategy definitions, risk limits, source data, privacy policy or canonical Edge Library status. Existing human research endpoints retain their existing controls. Mission creation/execution only writes mission/checkpoint/job artifacts; an explicitly approved experiment may additionally write immutable Quant research artifacts.

## Hypotheses, skeptic and adversarial review

Current momentum tests canonical rolling return and MACD, with freshness limits. Positive descriptive measurements can support an observational statement without establishing profitability or improvement. Contradictory measurements weaken it. Historical momentum support is separately contradicted by the saved negative OOS result. Hypothesis states never include `PROVEN`.

Alternative passes use only available evidence: aligned beta/relative strength/breadth, volatility and funding/OI. Causality, short covering, position ownership or volatility expansion cannot be inferred from a single level. Missing tests are listed explicitly. A deeper negative-OOS investigation can escalate to the canonical candidate challenge. Skeptic artifacts retain stale data, source conflicts, extreme RSI, nonpositive OOS, rejection/invalidation conditions, small/dependent samples, selection bias and untested alternatives. No artificial counter-argument or invented backtest is generated.

The report exposes findings/support, contextual evidence, opportunity/thesis challenge, changes, historical/Quant evidence, contradictions, alternatives, unknowns, conclusion and next research. Quality is a set of transparent dimensions: examined/missing domains, freshness, evidence/source/tool counts, contradictions, actual OOS sample count, sample independence limits and grounding rejections. It is not a probability or a generic AI confidence score.

## Claim ledger and graph

Claims carry explicit type and evidence IDs. Canonical factual/calculation/classification claims reference the exact tool value and deterministic rendering. Grounding rejects absent citations, mismatched values, wrong manifest/cutoff, later source recording, wrong context manifest, invalid numeric evidence or instruments outside scope. Models cannot author canonical claims. Unsupported evidence stays a limitation/hypothesis.

Graph nodes/edges connect claims, evidence, approved tools, feature/context/backtest artifacts, manifests and observations/sources. The UI resolves citations into the exact evidence object, source times/IDs, hashes, parameters, units and raw artifact inspection. Structured diffs compare compatible tool/kind/label/symbol/unit/version/parameters; incompatible evidence is added/removed rather than assigned a fake numerical delta. Coverage changes are distinct from market changes and causal interpretation.

## Quant and experiment boundary

Stored Phase 8 momentum temporal OOS remains **−7.82%, N=82**. It uses compounded reset-capital folds, dependent trades and a selected survivor universe; it is not an executable continuous portfolio or a proven edge. Stored negative evidence and limitations survive every pilot report and model curation.

Optional experiments require STRATEGY_RESEARCH, a matching frozen manifest/source cutoff, registered strategy/parameters/filter, window at most 31 calendar days and explicit new-Quant budget. The exact hypothesis, definition, one-combination search space, metrics, evaluation plan and overfitting risks are registered before invoking Quant Lab. No strategy code is generated or changed. Existing definitions/results use Quant Lab hashes/cache identities.

New results are explicitly `RETROSPECTIVE_COUNTERFACTUAL`, recorded after the research cutoff and labelled as descriptive in-sample work requiring independent OOS. This narrowly permitted artifact is never represented as information known then. Grounding's exception is restricted to the explicitly approved mission backtest tool/proposal; ordinary historical sources cannot bypass availability.

## Model routing, privacy and cost

Scope, planning, execution, hypotheses, evaluation and numeric synthesis are deterministic. Optional local OpenAI-compatible curation uses the Phase 4 ModelGateway and returns only up to twelve existing claim IDs. Selected IDs cannot hide the canonical claim ledger, limitations, negative results or contradictions.

No `ollama`, `lms` or `llama-server` command or listening local runtime was discovered on the checked conventional ports. Acceptance uses deterministic fallback plus mock local, hostile and cloud gateways. No model was installed/downloaded and no cloud API was called. Optional configuration remains environment-only: `MARKET_CORTEX_LOCAL_MODEL_URL` must be loopback HTTP and `MARKET_CORTEX_LOCAL_MODEL_ID` names an already installed model. Allow local model calls in the mission budget only when intentionally configured.

Before constructing any model payload the executor enforces locality/privacy and zero paid API cost. Cloud providers are blocked in Phase 10 regardless of the owner's future cloud preference. Source prose, journal/notes, portfolio details and private strategy/memory outputs are filtered from curation candidates. Provider/model/status, latency, optional token usage, calls and zero cost are recorded. Timeout/unknown-ID/malicious output falls back to deterministic claims. External news or contextual text never controls plans/tools or becomes executable instructions.

## API, CLI, jobs and UI

Prefix `/api/v1/cortex/missions`: typed create/list/inspect, status/tools/templates, plan/evidence/hypotheses/report/history/diff, execute/resume/cancel and replay. Execute/resume return HTTP 202 with an existing durable JobQueue job; a local BackgroundTask processes it. `mission-worker` processes one pending/recoverable job after a process restart. There is no automatic recurring research loop or new scheduler infrastructure.

CLI examples (configure the intended local environment first):

```powershell
python scripts/market_cortex.py mission-create --input mission-request.json
python scripts/market_cortex.py mission-run <mission-id>
python scripts/market_cortex.py mission-inspect <mission-id>
python scripts/market_cortex.py mission-replay <mission-id>
python scripts/market_cortex.py mission-compare <older-id> <newer-id>
python scripts/market_cortex.py mission-cancel <mission-id>
python scripts/market_cortex.py mission-resume <mission-id>
python scripts/market_cortex.py mission-worker
```

Research Lab is a new workstation page alongside CORTEX v1. It supports goals, modes/templates, comparison, historical cutoff, thesis version, optional required options domain, reuse/fresh requests, tool/local-model limits, plan review/start, process activity, budgets/cost, cancel/resume, report, hypotheses, Quant evidence, contradictions, history/diffs, citations, source inspection and replay. The Next.js proxy allowlists the new typed routes. Source text is React-escaped. Activity contains actions/results/latency, not private model reasoning.

## Validation and limitations

`test_phase10_policy.py` tests golden structure, forbidden capabilities, DAG/depth/domain/scope/paid-budget gates, numbers, future evidence, negative results and prompt injection. `test_phase10_catalog.py` uses an isolated disposable PostgreSQL schema and actual immutable Parquet fixtures to verify checkpoints, recovery, cancellation, model privacy, typed APIs/jobs, duplicate reuse, strategy preregistration, candidate challenge and change analysis. `test_phase10_pilot.py` reads/replays six actual stored Binance/Treasury dossiers. The pilot script verifies canonical state counts before/after and stores reports/results without DSNs/secrets.

See `PHASE_10_PILOT_RESULTS.json`, six mission Markdown dossiers and the Phase 10 exit matrix for final gates. Default research uses no new external network source fetch. Daily bars are stale at the pilot cutoff; this remains explicit. Narrow observational hypotheses and deterministic question decomposition are intentionally limited. No local LLM language interpretation, cloud synthesis, prospective causal confirmation or independent profitable edge was established. Upstox/Alpaca remain `DEFERRED_NOT_CONFIGURED`; live options/news/events/on-chain/fundamentals await verified sources, mappings and calendars. Phase 11 adaptation has not started.
