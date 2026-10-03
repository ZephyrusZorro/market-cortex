# CORTEX v1 — evidence-grounded research

CORTEX v1 is the Phase 4 explanation layer over the existing daily Binance Pilot 5 catalog. It does not fetch new market data, calculate canonical indicators in a model, forecast returns, or place orders. The supported instruments are BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, and XRPUSDT. Upstox and Alpaca remain `DEFERRED_NOT_CONFIGURED` for live authenticated data.

## Flow and trust boundary

`ResearchRequest → ResearchContext → bounded code-selected tools → deterministic evidence → analyst claims → skeptic and limitations → cited synthesis → ResearchRun`

One orchestrator in `cortex.py` performs the conceptual observer, researcher, technical analyst, quant analyst, historian, skeptic, risk, and synthesizer passes. The observer reads Phase 1/2 data. Technical and quant claims are formatted from returned values. The historian requests a second pinned context only when comparison is requested. The skeptic emits a conflict only when deterministic dimensions disagree. The risk pass reports drawdown, stale data, limited coverage, and the five-member universe. The synthesizer selects a question-relevant conclusion, evidence, counter-evidence, limits, and an invalidation condition where applicable. Claim types distinguish `OBSERVATION`, `CALCULATION`, `CLASSIFICATION`, `INTERPRETATION`, and `LIMITATION`; `HYPOTHESIS` is reserved in the contract but not emitted by v1.

The orchestrator uses a fixed allowlist. Neither the question nor a model response can call arbitrary SQL, Python, shell, filesystem, web, broker, or exchange tools. Only `POST /api/v1/cortex/research` creates a local research record; there is no trading or broker write route. Unsupported pilot symbols, invalid cutoffs, unapproved tools, and extra tool arguments are rejected.

## ModelGateway and privacy

`ModelGateway` is provider neutral. Implementations are `NoModelGateway` (deterministic fallback) and `LocalOpenAICompatibleGateway` (loopback HTTP `/v1/chat/completions`). The latter is configured with `MARKET_CORTEX_LOCAL_MODEL_URL` (base URL, such as `http://127.0.0.1:11434/v1`) and `MARKET_CORTEX_LOCAL_MODEL_ID`. Both must be set. URLs must resolve syntactically to `127.0.0.1`, `localhost`, or `::1`; credentials, paths outside `/v1`, HTTPS remote hosts, and HTTP redirects are refused. No local inference runtime was configured during Phase 4 validation, so actual market pilot research used the deterministic fallback. The local adapter was contract tested without downloading a model.

The model sees the owner question and candidate claim text only. It may return up to twelve existing claim IDs. It cannot submit market numbers, new claims, citations, or tool calls. The typed response is checked against issued claim IDs; malformed, timed-out, or unavailable local inference falls back to deterministic selection. All claims and numerical values originate in code-controlled tools, and every emitted claim must reference issued evidence IDs. No private chain of thought is requested or stored.

Cloud model integration is a future option. The policy gate runs before invocation. V1 treats freeform owner questions as unclassified private text and blocks cloud invocation even if a broad cloud-model setting is enabled. This also protects future portfolio, journal, notes, and prior research content. No credential or database URL enters a model prompt. The current model cost field is `local / ₹0 API spend`; input/output token usage is recorded only when a provider supplies it. Electricity cost is not estimated.

## Approved tool registry

`GET /api/v1/cortex/tools` publishes the exact versioned registry, Pydantic input and output schemas, allowed scope, and failure states. All tools return a typed `ToolRun` with validated inputs, manifest, cutoff, status (`ok`, `insufficient`, or `unavailable`), evidence list, SHA-256 output hash, and elapsed milliseconds.

| Tool ID | Input | Existing authority |
| --- | --- | --- |
| `dataset.context` | No arguments | Workstation manifest, cutoff, environment, pilot coverage |
| `instrument.features` | One supported symbol | Phase 1 stored close and Phase 2 feature engine |
| `market.state` | No arguments | Phase 2 `MarketStateEngine`, regime, dimensions and breadth |
| `asset.compare` | Two distinct supported symbols | Phase 2 aligned relative strength and Pearson correlation |
| `dataset.manifest` | No arguments | Published immutable artifact ancestry |
| `research.prior` | One supported symbol | Earlier local research conclusion and run provenance, labeled historical context |

All tool scopes are `binance_pilot_5_read_only`. Feature evidence records instrument, provider, source observation/batch or feature ID, session, parameters, version, unit, quality, freshness, coverage, manifest, and cutoff where available. A null has a reason; it is never replaced with zero. Relative strength uses Phase 2's fractional outperformance formula `(target_t/target_t−p)/(reference_t/reference_t−p)−1`; positive means the target led, negative means the reference led. Pearson correlation is not interpreted as causality.

## Context, history, and citations

`ResearchContext` records mode, manifest, offset-aware UTC availability cutoff, universe, selected symbols, common evaluation date, history start, canonical instrument IDs, environment, and display currencies. The question remains in `ResearchRequest`. Latest mode uses the current head and rejects a workstation context whose head moved. Pinned mode uses the supplied manifest. Historical mode applies the availability cutoff through existing point-in-time reads. A natural question of the form `as of June 1, 2025` is interpreted as the end of that date in Asia/Kolkata; explicit API cutoffs must include an offset. A requested older manifest is queried in a separate context with separate evidence IDs. Past observations or research conclusions are never silently promoted to current evidence.

The context also records each member's last visible session. In an early manifest with BTC observations but no common five-member evaluation date, CORTEX can compare BTC's own stored close while reporting market state as unavailable. It never manufactures a complete-universe snapshot from partial coverage.

Each answer citation is an internal evidence ID. The workstation citation button opens the evidence inspector with its source, value, unit, observation, feature/rule version, parameters, quality, freshness, manifest, and cutoff. The answer and structured claims reference exactly the evidence saved in that run. Model output does not supply citations.

Research runs are saved to local PostgreSQL by migration `0003_cortex_research.sql`. A run records the request, context, tools and versions, inputs and hashes, all evidence and claims, model status/usage and non-secret configuration, orchestration and claim-selection prompt versions, answer, warnings, failure state, and deterministic/model/total latency. `research.prior` retrieves up to three records created before the research cutoff, including the recorded conclusion, run ID, original manifest, original cutoff, and recorded time. The new answer labels each prior conclusion as historical context rather than a current market fact. This is bounded episodic memory, not automatic belief or strategy mutation.

`GET /api/v1/cortex/runs/{id}/replay` reruns each saved tool with its original manifest and cutoff and compares output hashes. It reports `evidence_reproducible` separately from `language_reproducible` (always false in v1). The run remains inspectable even when a replay mismatch is found. No model text regeneration is attempted.

## Evidence strength and failure behavior

The qualitative strength label is deterministic and is not a probability. It is `weak` when fewer than five pilot mappings are visible or any returned evidence reports stale/unknown freshness. With complete, fresh coverage, three independent analytical tool families and no interpretation conflict yield `strong`; two yield `moderate`. A detected interpretation conflict keeps strength `weak`; otherwise a single or empty family can be `moderate` only under complete fresh coverage. In the current stored pilot, the last daily session is stale at the latest cutoff, so live scenario answers correctly remain `weak` and the regime may be `insufficient_data`.

When there is no visible observation or usable state, the run reports `INSUFFICIENT_EVIDENCE` and does not synthesize a directional market conclusion. Model outages preserve all deterministic tools and data views. Questions asking whether to buy receive evidence and limits, never an order action or guaranteed outcome.

## API, CLI, and workstation

The loopback FastAPI routes are `GET /api/v1/cortex/status`, `GET /tools`, `POST /research`, `GET /runs`, `GET /runs/{id}`, and `GET /runs/{id}/replay`. The Next.js proxy permits only the CORTEX research POST plus the allowlisted GET routes. It caps request bodies and targets loopback FastAPI. OpenAPI provides exact JSON schemas.

CLI examples (after migration and setting `MARKET_CORTEX_DATABASE_URL` and `MARKET_CORTEX_DATA_ROOT` for the intended local catalog):

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py research "Analyze BTCUSDT." --symbol BTCUSDT
.\.venv\Scripts\python.exe scripts\market_cortex.py research "Compare ETHUSDT with BTCUSDT." --symbol ETHUSDT --compare-symbol BTCUSDT
.\.venv\Scripts\python.exe scripts\market_cortex.py research-runs --symbol BTCUSDT
.\.venv\Scripts\python.exe scripts\market_cortex.py inspect-research-run RUN_UUID
.\.venv\Scripts\python.exe scripts\market_cortex.py replay-research-run RUN_UUID
```

The workstation has a CORTEX pane reachable from navigation, instrument research, and Market State. It carries the visible instrument or market context, active manifest and cutoff, quick/deep depth, optional comparison or older manifest, saved runs, structured claims, citations, evidence inspector, tool activity, model status, and replay result. The top bar and pane show `PILOT / TEST`, `OWNER / MAIN`, or `UNLABELED` from the server setting. Set `MARKET_CORTEX_ENVIRONMENT=PILOT_TEST` for the isolated pilot or `OWNER_MAIN` only when intentionally connecting the owner catalog. A database name ending `_test` is inferred as `PILOT_TEST`; otherwise an unset label is `UNLABELED`. Inspect the badge before interpreting the data.

## Limits

The pilot is five Binance spot pairs on stored P1D bars, not live quotes. There is no news, fundamentals, on-chain, options, portfolio sizing, external web research, authenticated India/US live coverage, or autonomous trading. Local inference was not installed on the validation machine. Natural language date parsing covers ISO dates and full English month names after `as of`; other date phrasing requires the explicit historical context picker. Saved research includes the owner's questions in local PostgreSQL and its backups. A future governed cache must key by manifest, cutoff, tool/version, inputs, and source data; v1 computes on demand.
