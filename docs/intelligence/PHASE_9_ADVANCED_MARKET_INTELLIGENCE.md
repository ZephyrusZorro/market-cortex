# Phase 9 — Advanced Market Intelligence & Event Context

Release: `phase9-v0.9.0`. Local, private, single-user research software. The accepted scope is partial contextual coverage with explicit provenance, immutable revisions and strict recorded availability. No subscription, cloud model or trading account is required.

## Architecture

```text
Fixed public GET / future reviewed provider
  → typed ObservationEnvelope + EntityRef + domain fact
  → validation + revision lineage
  → PostgreSQL catalog + content-addressed ContextFact Parquet
  → immutable context manifest
  → ContextSnapshot at a specified knowledge cutoff
  → approved CORTEX tools / thesis supplement / risk context / frozen Quant source
```

The modular monolith reuses the existing catalog connection, identity registry, calendars, market manifest, immutable lake, backup publication lock and local API. Migration `0010_context_intelligence.sql` adds facts, files, manifest membership, head and snapshots. Price data and contextual data have separate manifest identities because their publication schedules differ. A snapshot records both pins.

The contracts are in `src/market_cortex/intelligence_contracts.py`; exported schemas are in `packages/contracts/intelligence.schema.json`. Each fact has a version, entity mapping version, logical key, source envelope, revision number, validation state and `LIVE_SOURCE` or `SYNTHETIC_TEST` scope. Contracts cover macro observations, fundamental facts/statements, economic/corporate events, news metadata, derivative observations/contracts, option contracts/chains and on-chain metrics. Instrument identities use UUIDs; issuers, regions and macro series have typed namespaced keys. Free-text ticker matching does not establish derivative identity.

## Knowledge time and revisions

| Field | Meaning |
| --- | --- |
| `event_at` | Source event or observation instant; never sufficient to establish knowledge |
| `period_start/end` | Economic/reporting period; never a release date |
| `published_at` | Actual source publication, if known; otherwise null |
| `available_at` | Earliest supported availability; the live adapters use observed local arrival |
| `ingested_at` | Local normalization/ingestion instant |
| Catalog `recorded_at` | Actual catalog insertion time; prevents backdated envelopes from creating earlier local knowledge |
| `effective_at` | Optional effective instant |
| `revised_at` / supersedes ID | New revision time and previous observation identity |

Reads require availability, ingestion and catalog recording at or before the cutoff. A known publication must also precede it. Derivative contract discovery and the observation event must precede the cutoff. Scheduled events can describe a future event once its announcement is known. A reported actual result cannot precede its release. Missing availability excludes a fact.

Append changes create new observations and manifests. Earlier files and manifest membership remain intact. Semantic retries preserve the original recorded arrival rather than inventing a later revision. Metadata enrichment can produce an explicit revision without changing the numerical value. The second real Binance batch enriched contract metadata provenance and extended history; its revisions remain visible alongside the first batch in historical manifests.

`ContextStore.freeze()` retains **all revisions**, catalog recording times and manifest ancestry. Quant decisions first select the manifest known by their cutoff, exclude later recorded facts, then select the latest visible revision per source/logical key. Capturing a newer revision cannot erase the value known at an earlier decision.

## Source registry and live validation

| Provider/domain | Accepted status | Actual coverage | Limits |
| --- | --- | --- | --- |
| Binance USD-M / derivatives | `PUBLIC_VALIDATED` | Pilot 5 USDT perpetuals; funding, daily OI, current mark/index | Arrival-only knowledge; funding request default 90/max 1000; OI API latest month; no liquidation history |
| US Treasury / macro | `PUBLIC_VALIDATED` | 24 monthly average interest rates on outstanding Treasury Bills | Publication/vintage time unknown; not a policy rate, market yield curve or spot risk-free rate |
| Equity sources / fundamentals | `DEFERRED_NOT_CONFIGURED` | Provider-neutral contracts, ratio validation and fixtures | Upstox/Alpaca credentials plus verified equity mappings/calendars await configuration; existence of their bar adapters does not prove fundamental coverage |
| Calendar / events | `DEFERRED_DATA_SOURCE` | Economic/corporate event contracts and synthetic event-risk workflow | No verified live calendar or consensus |
| News | `DEFERRED_DATA_SOURCE` | Metadata, deduplication, structured conflicts and security fixtures | No licensed live feed or article extraction pipeline |
| Options | `DEFERRED_DATA_SOURCE` | Exact identity, nullable chain fields, European IV/Greeks calculation | No live chain, GEX, DEX, max pain or dealer-position inference |
| On-chain | `DEFERRED_DATA_SOURCE` | Versioned metrics with source/network/availability semantics | No verified live source |
| Liquidations | `UNAVAILABLE` | Contract-ready capability only | No fabricated values or complete-feed claim |
| Cross-asset contextual state | `UNKNOWN` | Existing Phase 2 synchronized price-pair analytics remain usable | No aligned macro/FX/commodity market series verified in Phase 9 |

`PUBLIC_VALIDATED` reflects persisted live source evidence at the requested cutoff, not adapter presence or a claim that a provider is currently online. Source coverage includes fact counts, native instruments, authentication, cost, history, arrival times and limitations. Snapshot domain states are separate: `AVAILABLE`, `PARTIAL`, `STALE`, `UNKNOWN`, `UNSUPPORTED`. Current live macro and derivatives dimensions are `PARTIAL`.

The source adapters use the existing read transport's fixed host/path GET allowlist. No arbitrary URL is accepted. Limits include 4 MB responses, no followed redirects, three bounded retry attempts, 300 ms request spacing, process-local 60-second caching and one-hour metadata caching. This is a bounded manual sync foundation, not a distributed rate coordinator. Restarting a process resets its cache. The official endpoint limits still apply across processes.

Official source references:

- [Binance USD-M market data documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data): `/fapi/v1/exchangeInfo`, `/fapi/v1/fundingRate`, `/futures/data/openInterestHist`, `/fapi/v1/premiumIndex` are the implemented public GET paths.
- [US Treasury Average Interest Rates dataset](https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/) and [official API endpoint](https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates): filtered to Treasury Bills. The source period is retained; unavailable original publication times remain null.

## Deterministic domain behavior

### Macro and fundamentals

Macro primitives expose per-series/per-source direction over compatible units, currency and reporting periods. They do not manufacture a single macro score or infer inflation, liquidity, USD strength, yield-curve or risk-free state from the Treasury series.

Fundamental facts require issuer, reporting period, fiscal period, currency and units. Margin and leverage calculations require compatible validated `SOURCE_FACT` numerator/denominator concepts and nonzero denominators; otherwise the value is unavailable. Restatements preserve lineage. Growth, FCF, valuation and broader ratios are future capabilities requiring suitable facts.

### Events and news

Events retain scheduled/actual release times, category, sourced importance and optional actual/prior/revised prior. Consensus requires its own source. `corporate_action_ref` can refer to foundation action evidence rather than replacing it.

News stores bounded titles, references, language, category, entity mappings, hashes and optional structured assertions. It stores no article body. `EXTRACTED` requires model/version metadata and remains distinct from `SOURCE_FACT`; no live LLM extraction is enabled. Deduplication uses entity, category, time proximity, syndication and title similarity. Multiple duplicate articles form one event group, not independent confirmations. Compatible numeric-source disagreement and conflicting structured news assertions retain both facts as `UNRESOLVED`.

Event risk requires visible, validated, trusted source events explicitly relevant to the instrument. High importance must be sourced. Only an upcoming event inside the thesis's declared horizon can trigger `EVENT_RISK`; uncertain/extracted news cannot do so. `EVENT_IMMINENT`, `EVENT_UPCOMING` and `EVENT_RECENT` are descriptive proximity states. `NO_KNOWN_EVENT` requires verified calendar completeness through the horizon; otherwise the answer is `EVENT_DATA_UNAVAILABLE`.

### Derivatives

Binance metadata must verify a trading linear USDT perpetual and an existing canonical Binance spot mapping. The contract has a distinct canonical derivative UUID, underlying UUID, native ID, base/quote/margin currencies, quantity unit, discovery time and metadata reference/hash.

Funding is a fraction per funding event, not an annual yield or percent. OI quantity is the contract's base asset; the companion value is USDT. Calculations select one exact contract and expose latest value/time, funding empirical percentile, positive fraction, same-sign run, OI change and mark/index premium. The percentile is a rank in the actual retained sample, not a predictive probability.

The price/OI matrix uses the funding-event mark associated with each OI timestamp within one second, retaining actual timestamps and applying no interpolation. Binance funding charges can have millisecond offsets. Missing matches produce an explicit unavailable state. `PRICE_UP_OI_DOWN` and its other combinations are descriptive; positive funding is not automatically bearish and no directional guarantee is emitted.

### Options and on-chain

Option identity includes canonical underlying, native contract ID, expiry, strike, call/put, multiplier, settlement, exercise style and currency. Duplicate contracts, crossed quotes and missing calculation provenance are rejected. Missing bid, ask, IV or Greeks remain null.

`option_analytics()` supports European Black–Scholes only, with an explicitly supplied price, underlying, strike, year fraction, annual rate and annual dividend/carry assumption. It never invents a mid quote or rate. IV uses bisection on `[1e-8, 5]`, at most 100 iterations and absolute price tolerance `1e-8`; invalid/no-arbitrage/boundary/out-of-bracket inputs return no IV/Greeks. Theta is price per calendar day; vega/rho are price per unit fraction. American pricing and exposure/positioning analytics are unavailable. A textbook call/put golden fixture verifies calculation output.

On-chain facts retain network, metric, units, provider identity and temporal provenance. There is no live on-chain dashboard or invented history.

## ContextSnapshot and integration

Snapshot identity hashes source manifests, cutoff, instrument, domain values, full visible facts, revisions, conflicts, warnings, calculation version and normalized implementation hash. It is deterministic for the same pinned inputs/code and is saved immutably. New ingestion cannot alter a saved snapshot. Comparison returns added/removed/revised fact IDs and both sets of dimensions. Snapshot `market_state` records the canonical Phase 2 market manifest; it does not duplicate the market-state engine or change detectors.

Thesis monitoring first runs the canonical detector lifecycle, then appends a contextual supplement. It validates instrument/market pin/cutoff, preserves candidate/supporting evidence, and can append a sourced event-risk transition within the canonical 2–20 day swing horizon. Unsupported horizons produce no invented transition.

Risk snapshots add separate per-instrument contextual risk, event proximity, derivative state and uncertainty. Numerical sizing, stop, heat, exposure and R calculations retain their existing formulas; unavailable events do not become a sizing multiplier.

CORTEX adds approved typed `intelligence.context`, `.macro`, `.events`, `.news`, `.derivatives`, `.fundamentals`, `.options`, `.onchain` and `.provenance` tools. Inputs accept fixed symbols, manifest IDs and fact UUIDs. Evidence retains source IDs, raw hashes, arrival/ingestion, quality, revision and calculation version. The answer labels source facts and calculations and always retains domain coverage/conflict limitations even if an optional local model omits them. Titles, article prose and arbitrary URLs are excluded from model claims. News content analysis is therefore limited to structured metadata; it is not unrestricted article summarization.

Quant has optional `funding_nonpositive` and `oi_expanding` filters, with minimum 20 visible funding/OI observations respectively. Defaults remain unfiltered. Context is **AS_RECORDED_ONLY**, including when prices use labelled historical reconstruction. Inadequate recorded context blocks a contextual-filter entry; it is not imputed from later downloads. Snapshot/quant code hashes intentionally change when implementation changes. Phase 8 saved artifacts remain viewable; recomputation under newer code returns `VERSION_UNAVAILABLE` and requires the preserved Phase 8 tag.

The event-study foundation aligns the event to the first actual calendar session opening at/after it, uses the prior close as anchor, and computes explicit session-window returns, daily volatility, volume response and drawdown. Missing sessions reject the window. It does not mix equity holidays/weekends with crypto calendar days. The demonstration in the live-results report is explicitly `SYNTHETIC_TEST`, `N=1`, with `causality=NOT_ESTABLISHED`. Cross-sectional event studies are not implemented.

## Local API and CLI

Read routes under `/api/v1/intelligence`:

| Route | Scope |
| --- | --- |
| `GET /context` | Snapshot; cutoff, instrument, market/context manifests, bounded horizon |
| `GET /coverage` | Source registry at cutoff |
| `GET /domains/{domain}` | Typed domain values/coverage; limit ≤1000 and offset |
| `GET /facts/{uuid}` | Visible source provenance |
| `GET /snapshots/{uuid}` | Saved immutable snapshot |
| `GET /compare?left=…&right=…` | Saved snapshot comparison |
| `POST /event-study` | Bounded local calculation over an existing visible event and pinned bars |

There is no HTTP source-sync endpoint. Workstation proxy routes are explicitly allowlisted. CLI source sync is fixed to two reviewed public providers:

```powershell
.\.venv\Scripts\python.exe scripts\market_cortex.py migrate
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-sync --source binance_usdm --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-sync --source us_treasury
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-coverage
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-context --instrument-id <canonical-UUID> --as-of <aware-ISO-time>
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-events --instrument-id <canonical-UUID>
.\.venv\Scripts\python.exe scripts\market_cortex.py intelligence-inspect <fact-UUID> --as-of <aware-ISO-time>
```

Set catalog/data-root environment variables as in the local runbook. `intelligence-probe` normalizes source data without storing facts; Binance verification may register newly discovered local derivative identities. Live equity credentials remain environment-only and unconfigured. Repeating a sync preserves existing semantic facts and appends genuine changes; a failed fetch does not publish a partial contextual batch.

The Intelligence workspace and instrument context panel show actual funding/OI histories, macro history, domain status, source coverage, explicit missing-data reasons, conflicts and a modal source inspector. Text is React-escaped. Event rows retain distinct categories; chart-aligned live event markers await a validated calendar/news source. Offline reads continue to work on stored immutable evidence without source calls.

## Security, backups and evidence

External text is untrusted data. It cannot add tools, read secrets, invoke shell/SQL, change privacy policy or override model instructions. Tests cover malicious news text, HTML/script escaping, SSRF targets, trading paths, credentials in queries, unsafe redirects, oversized responses, malformed JSON and unsafe source references. Queries use parameters; schemas/temporary databases use quoted identifiers. Source references are metadata, not download instructions.

Synthetic facts are restricted to dedicated `_test` databases. Regression schemas and restore databases are disposable and isolated. Backups include context files with the catalog under the foundation publication lock; restore verifies hashes and immutable snapshots. The Windows durable staging operation retains `r+b` before `fsync`.

See [live validation evidence](PHASE_9_LIVE_RESULTS.json) and the [exit matrix](../planning/PHASE_9_EXIT_MATRIX_2026-10-05.md) for exact pins, source times, test results and limits. The accepted Phase 8 momentum temporal OOS finding remains **−7.82%, N=82; no supported edge**. The short Phase 9 filter exercise has zero historically known contextual facts and cannot establish a funding-conditioned edge. No hypothesis is promoted on narrative intuition.

Phase 10 has not been started. Future work requires separately verified data and explicit sample sufficiency; Phase 9 completion does not establish live equity/options/news/on-chain coverage.
