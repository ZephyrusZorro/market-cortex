# Phase 4 exit matrix — 2026-10-03

**Status: COMPLETE for CORTEX v1 over stored Binance Pilot 5 daily data.** The owner can ask a local workstation question and trace the answer through claims, inspectable evidence, six approved deterministic tools, Phase 2 features/market state, a pinned manifest, and immutable Phase 1 observations. This release retains Phases 1–3 and adds no trading or broker write path. Upstox and Alpaca live authenticated coverage remains `DEFERRED_NOT_CONFIGURED`.

**Implementation commits:** `6eef994` (CORTEX v1) and `b6d87a5` (partial-manifest history and research metadata). **Release tag:** `phase4-v0.4.0` points to the commit containing this report. Earlier `phase2-v0.2.0` and `phase3-v0.3.0` tags are unchanged. No Git remote is configured and nothing was pushed.

## Acceptance matrix

| Criterion | Evidence |
| --- | --- |
| A — Phase 1–3 regression | Two consecutive full backend runs after final code: **64 passed, 13 subtests passed** each. This includes prior PostgreSQL, backup/restore, analytics, and workstation cases. One nonfunctional Starlette `TestClient`/`httpx` deprecation warning remains. |
| B–C — Approved tools and numeric integrity | Six typed allowlisted tools call existing Phase 1/2 engines. The model can only return IDs of already-issued claims. All structured claims are checked against tool-issued evidence IDs; no model-provided number or tool call is accepted. |
| D–E — Manifest and historical safety | Requests carry a published manifest and offset-aware availability cutoff. The June 1, 2025 scenario has `INSUFFICIENT_EVIDENCE`, no future BTC observation, and no October 2026 close in its answer. The oldest manifest exposes the September 26 BTC close independently while its incomplete five-member market state remains unavailable. |
| F–G — Analyst, skeptic, limits | Actual BTC evidence produces close, return, SMA, RSI, volatility, drawdown and regime claims. Trend `up` versus momentum `mixed` creates a specific counterclaim. Stale data, narrow universe and deferred equity sources are explicit. Qualitative strength follows documented coverage/freshness/conflict rules; the current pilot is `weak`, with no invented probability. |
| H — Citations | Every claim cites an issued evidence ID. In the browser, selecting RSI14 showed the Binance provider, 64.81545793716082 source value, feature version and parameters, observation ID, quality, freshness, manifest and cutoff. |
| I–J — Runs and replay | `0003_cortex_research.sql` stores local JSONB research manifests with context, tools, versions, hashes, evidence, claims, answer, model usage, prompt/orchestration versions and latency. BTC and earlier-manifest runs persisted; both replayed with matching deterministic hashes. The UI correctly says language generation is not replayed. Prior research conclusions are retrieved with original run and manifest provenance and labeled historical context. |
| K–L — Privacy and model independence | Cloud invocation is blocked for unclassified owner questions before model selection, even when the broad cloud setting allows cloud use. No local model runtime was installed or listening on the checked loopback port; the deterministic gateway produced all live pilot answers. A malformed mock model response fell back safely. The local OpenAI-compatible adapter is loopback-only and refuses redirects. |
| M — Workstation | Production Next.js build and a real browser walkthrough passed at `127.0.0.1:3000`. The CORTEX pane used BTC context, displayed `PILOT / TEST`, manifest, cutoff, question, weak strength, answer, counter-evidence, limitations, saved run, tool activity, citations, evidence inspector and successful replay. Prior-run citations exposed original run, manifest, cutoff and recorded time. |
| N — No execution | OpenAPI exposes exactly one POST, `/api/v1/cortex/research`, which writes a local research record. There are no order/trade/broker write routes or unrestricted SQL/shell/filesystem/web tools. |
| O — Tests and build | **64 backend tests plus 13 subtests** passed twice after final changes; **12 frontend tests** passed in repeated runs. `npm run typecheck`, `npm run build`, and `git diff --check` passed. The compiled frontend static bundle contained none of the scanned database URL/credential key patterns. |

## Architecture and validated scope

The single `CortexService` orchestrator resolves `ResearchContext`, chooses a bounded plan, executes `dataset.context`, `instrument.features`, `market.state`, `asset.compare`, `dataset.manifest`, and `research.prior`, creates typed observer/technical/quant/historian claims, runs skeptic and limitation checks, and assembles a cited response. It does not create parallel agents. `ModelGateway` supports deterministic no-model mode and optional local OpenAI-compatible claim selection; no cloud adapter or paid service was used. Tool schemas, failure states, provenance, strength rules, privacy policy, API/CLI/UI operations and replay semantics are documented in [CORTEX v1](../cortex/PHASE_4_CORTEX_V1.md).

The live pilot is the existing isolated PostgreSQL `*_test` catalog and immutable Parquet root, with 396 stored daily sessions per pair in the current manifest and latest stored BTC session on **2026-10-01**. The owner's main `market_cortex` database was not migrated, reset, or written during this validation. The visible environment badge was `PILOT / TEST`; the backend explicitly used `PILOT_TEST`.

## Eight live acceptance scenarios

One final pass on actual stored pilot data issued each question with deterministic model fallback and validated that every claim citation resolved to tool evidence. The results below are descriptions of the stored data and selected cutoffs, not current trade guidance.

| Question | Verified outcome | Total latency sample |
| --- | --- | ---: |
| Analyze BTCUSDT | 84,880.05 USDT close on 2026-10-01; above 81,709.91 SMA20; stale/weak caveat and momentum counter-evidence | 3,424 ms |
| Current Binance Pilot 5 market state | Versioned regime `insufficient_data` at the selected cutoff; five-member scope disclosed | 3,251 ms |
| Compare ETHUSDT with BTCUSDT | BTC led on Phase 2's 20-session fractional-outperformance measure; ETH versus BTC was −2.1%; Pearson evidence also returned | 4,300 ms |
| Strongest pilot relative strength | SOLUSDT had the highest measured 20-session return, +15.6%, among the five paired pilot members | 6,877 ms |
| Evidence contradicting BTC trend | Upward trend versus mixed momentum surfaced as a cited conflict | 3,523 ms |
| Change versus earlier manifest | Oldest manifest BTC close 84,433.10 USDT on 2026-09-26 versus current 84,880.05 USDT on 2026-10-01, each with distinct manifest evidence | 3,960 ms |
| BTC at 2025-06-01 cutoff | `INSUFFICIENT_EVIDENCE`; no later observation admitted | 268 ms |
| Missing or insufficient information | Stale observations, limited five-pair scope and deferred India/US providers surfaced | 3,150 ms |

These are one-run owner-machine measurements, not latency guarantees. Deterministic tool times are separately recorded in each run, as are model time and total research time; model time was 0 ms in fallback mode. A real browser BTC research request took 3,932 ms total with 3,688 ms in deterministic tools. The widest eight-scenario sample was the five-member ranking at 6,877 ms. No cross-manifest/as-of cache was introduced.

After restarting the final backend, a production Next.js proxy POST created an earlier-manifest BTC run in `PILOT_TEST`; its response recorded `cortex_claim_selection_v1`, the 84,433.10 → 84,880.05 USDT comparison, and 4,330 ms total latency. The proxy replay GET returned `evidence_reproducible: true`.

## Security and remaining boundaries

Input and tool schemas reject unsupported symbols, unapproved tool IDs, extra arguments, and naive historical cutoffs. The local model URL must be loopback HTTP; crafted userinfo hostnames and off-scope paths are rejected. The model response must select known claim IDs, and malformed output falls back without executing any command. The Next.js proxy allows fixed GET paths and the single bounded research POST to a loopback backend. Frontend bundle scans found no database URL or provider credential key. Research questions and conclusions are stored locally in PostgreSQL; no chain-of-thought is stored.

The last stored daily bar is stale relative to the validation date. This release has no quote/tick feed, news, macro, fundamentals, on-chain, options, portfolio sizing, external web research, or AI strategy mutation. Local inference was not available for real-model integration, so only the deterministic fallback and mocked model boundary were validated. Upstox/Alpaca need owner credentials plus verified equity mappings and calendars before live India/US validation; their existing adapters remain intact. Native USDT prices are not converted to INR without a governed FX source. Browser-local Phase 3 notes/watchlists remain outside PostgreSQL backup. Research runs are local and single-user. The remaining Starlette warning does not affect the tested API behavior.

**Readiness:** Phase 4's scoped CORTEX v1 acceptance criteria are met. Phase 5 opportunities and theses can build on these evidence contracts when separately authorized; no Phase 5 implementation is included here.
