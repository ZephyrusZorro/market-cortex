# Phase 9 exit matrix — 2026-10-05

**Status: COMPLETE — accepted 2026-10-05 (Asia/Kolkata).** Release: annotated local tag `phase9-v0.9.0`; `phase9-v0.9.0^{commit}` resolves to the accepted implementation. Baseline `phase8-v0.8.0` at `e4da9c563ecbea89cbf6ba5353e0b89d41a948fd` is preserved. No push; Phase 10 has not begun.

Implementation and live validation use the isolated PostgreSQL 17 catalog on loopback port 55432, dedicated `_test` databases and pilot data. The owner main database and `C:\MarketCortexData` were not modified. The canonical repository remains `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`.

## Acceptance A–O

| Gate | Result | Evidence |
| --- | --- | --- |
| A — Phase 1–8 regression | Pass | All PostgreSQL, restore and Phase 3–8 real-pilot gates enabled; 192 tests + 13 subtests passed twice, no skips |
| B — Versioned provenance contracts | Pass | Domain facts reuse ObservationEnvelope; typed entities/contracts, normalizer/mapping versions, quality, source/raw SHA256, revision lineage; exported schema |
| C — Availability | Pass | Available/publication/ingestion/catalog recording and contract knowledge enforced; reporting period never establishes knowledge |
| D — Revisions | Pass | Append-only observations, immutable Parquet/manifests, explicit supersedes; old pin returns old value; frozen Quant source retains all revisions |
| E — Genuine advanced live domain | Pass | Two sources fetched, normalized, persisted, queried and checked: Binance derivatives and US Treasury macro |
| F — Explicit missing domains | Pass | Registry, snapshot, API, CLI, CORTEX and UI expose unavailable/deferred coverage; no invented calendar, consensus, liquidation, chain or on-chain history |
| G — Partial ContextSnapshot | Pass | Deterministic identity, independent market/context pins, full visible facts, domain/code versions, dimensions, conflicts, event risk and warnings; saved snapshot immutable |
| H — Approved CORTEX tools | Pass | Typed allowlisted contextual tools; actual persisted answer and evidence replay match; mandatory coverage limits survive model selection |
| I — External text safety | Pass | Malicious news requests cannot invoke tools/shell/SQL/secrets; HTML escaped; fixed GET paths reject SSRF/order routes; redirect/parser/size/credential-query tests |
| J — Thesis/event-risk integration | Pass | Clearly synthetic relevant high-impact earnings fixture appends EVENT_RISK within declared horizon, preserves canonical evidence and is idempotent; uncertainty/extractions cannot trigger it |
| K — Quant leakage prevention | Pass | Recorded-only frozen context even with reconstructed prices; future facts/revisions/late recording excluded; old revision available before newer manifest; real filtered run has zero known context |
| L — Visible source coverage | Pass | Intelligence Center, instrument panel, genuine funding/OI histories, source status/limits and modal inspector; actual browser verification |
| M — Repeated tests | Pass | Backend 192 tests + 13 subtests and frontend 24 tests passed twice; typecheck and production build pass |
| N — No execution | Pass | Fixed public market-data GETs; local research POSTs only; no broker order/trade/account write endpoints |
| O — ₹0/month | Pass | Public Binance and Treasury sources; no mandatory paid feed or cloud model; other capabilities remain deferred |

## Implemented contextual scope

Macro observations/revisions, fundamental facts/statements with compatible margin/leverage calculation, economic/corporate events and sourced consensus/importance, metadata-only news deduplication/conflicts, crypto derivative identities/funding/OI/mark context, exact option identities/nullable chains/European IV and Greeks, on-chain metric contracts, deterministic snapshots, event proximity, calendar-aware event studies, approved CORTEX tools and integration with thesis/risk/Quant.

The market-state snapshot records the existing market manifest; canonical state/detector calculations remain in Phase 2/5. Cross-asset price alignment remains available from Phase 2. Phase 9 contextual cross-asset state is `UNKNOWN` because synchronized macro/FX/commodity market inputs are not verified. No sentiment signal, magic macro score, positioning inference or adaptive model is introduced.

## Sources evaluated and real evidence

| Source/domain | Status | Validation and limitations |
| --- | --- | --- |
| Binance USD-M derivatives | `PUBLIC_VALIDATED` | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT linear USDT perpetuals verified via native metadata + canonical spot mappings; actual public funding/OI/mark GETs; 625 visible facts after two batches |
| US Treasury macro | `PUBLIC_VALIDATED` | 24 actual monthly average rates on outstanding Treasury Bills, periods September 2024–August 2026; not market yields or policy rates |
| Upstox/Alpaca India/US live validation | `DEFERRED_NOT_CONFIGURED` | Existing read-only adapters and missing-credential tests retained; environment-only credentials plus verified market mappings/calendars await configuration; no live authenticated result claimed |
| Fundamentals | `DEFERRED_NOT_CONFIGURED` | Contracts, ratio/restatement/period/currency fixtures; a future actual fundamentals source still needs verification |
| Economic/corporate live calendar | `DEFERRED_DATA_SOURCE` | Typed events and synthetic workflow; no verified complete calendar, actual live releases or analyst consensus |
| Live news | `DEFERRED_DATA_SOURCE` | Metadata/dedup/conflict/security fixtures only; no licensed source or article extraction pipeline |
| Live option chains | `DEFERRED_DATA_SOURCE` | Provider-neutral identity/chain/European analytics foundation only |
| Live on-chain | `DEFERRED_DATA_SOURCE` | Provider-neutral metrics only |
| Liquidations | `UNAVAILABLE` | No complete verified free historical feed; no synthetic liquidation claim |

The accepted [live report](../intelligence/PHASE_9_LIVE_RESULTS.json) records source status, timestamps, native coverage, raw hashes, actual metrics, CORTEX output and replay, quant comparison and encrypted restore.

- Validation cutoff: **2026-10-05 12:07:58.561098 UTC** (see report for the exact aware instant).
- Raw market head unchanged: `3bf002d2-15f2-4f9d-8c54-cc7eb3fb349c`; 1,007 daily sessions per Pilot 5 asset through 2026-10-03.
- Context head: `158ad3f7-aab9-5d41-b79f-05eef01bc207`.
- Snapshot SHA256: `331ca1866956d0af355903e23df3d6b2405e4eed1163b86823b212d657bb8346`.
- Visible latest facts: **649** (625 derivatives + 24 macro). Catalog retains **1,234 observations including superseded revisions**, across three original contextual Parquet files; visible facts and total stored revisions are different counts.
- Derivative source event history: 2026-09-05 through 2026-10-05 11:54:33.002 UTC. The OI API fetch is limited to its latest month; append-only local accumulation now retains 31 daily observations per contract.
- BTC at that cutoff: funding fraction **0.00004186**, funding N=92; OI **97,452.28 BTC**, N=31; OI change fraction **−0.004856279641403321**; descriptive **PRICE_UP_OI_DOWN**. This is historical validation evidence, not a current quote or recommendation.
- Source publication/vintage times are unavailable for these ingestions and remain null. Arrival is recorded honestly; downloaded historical periods/events cannot enter earlier decisions.
- Three contextual file hashes/row counts verified, plus foundation storage inventory: no missing/corrupt/unreferenced artifacts.
- Complete pinned context encrypted backup and restore: **MATCH**, 1,234 stored observations including revisions, 649 latest visible facts, all three original contextual Parquet artifacts, original manifest lineage/timestamps and accepted snapshot, approximately **3.06 seconds**. The frozen lineage hash also matches after restore. Foundation/catalog backup and restore are separately covered by regression.

The second Binance batch adds full contract metadata reference/hash/discovery evidence. Numerical repeats with enriched metadata create preserved revisions; genuine new timestamps extend history. Old manifests retain the previous evidence. No source numerical result was fabricated.

## CORTEX, thesis and risk

Actual BTC research invoked `dataset.context` and `intelligence.context`, produced sourced funding/OI/macro calculations and disclosed unknown fundamentals/events/news/options/on-chain domains. Saved evidence replay matched both tool output hashes. `language_reproducible=false` is an explicit language limitation, not an evidence mismatch. There is no mandatory model API.

The sourced event-risk transition is demonstrated with a labelled synthetic earnings fixture because no complete live calendar is configured. Only trusted visible relevant high-impact source events inside the canonical 20-day swing horizon trigger it. News extraction, unrelated events and missing calendars cannot establish event safety or force a transition. Canonical candidate/supporting evidence remains unchanged. Risk adds contextual uncertainty separately from numerical position sizing/R/heat.

## Quant validation and negative findings

**Preserved Phase 8 momentum temporal OOS: −7.82%, N=82. No supported edge.** Historical Phase 8 reports and tag remain intact. Phase 9 intentionally adds implementation hashes; old saved quant results remain viewable, and attempting a cold recompute under different code returns `VERSION_UNAVAILABLE`. Checkout the recorded Phase 8 tag to reproduce its original code.

One predeclared short comparison uses 2026-09-29–2026-10-03, the default momentum parameters/costs, reconstructed prices and strictly recorded context. There is **no parameter search**:

| Context filter | Decisions | Historically known context facts | Trades | Net return | Replay |
| --- | ---: | ---: | ---: | ---: | --- |
| none | 25 | 0 | 2 | +0.0853% | MATCH |
| funding_nonpositive | 25 | 0 | 0 | 0% | MATCH |

Status: **INSUFFICIENT_AS_RECORDED_CONTEXT_HISTORY**. All contextual facts arrived after those decision cutoffs. The filtered no-trade result tests the missing-history gate; it does not establish filter effectiveness or a positive edge. The unfiltered two-trade sample is insufficient. No hypothesis was promoted.

Leakage tests cover later macro revisions, restatements/period versus release, later news/earnings/derivatives, future derivative events despite early arrival, contract discovery, catalog recording, snapshot cutoffs and earlier revisions before newer manifests. Quant freezes all revisions and manifest ancestry rather than only the latest value.

Event-study demonstration: explicitly **SYNTHETIC_TEST**, `[-3,+3]` crypto sessions, prior-close anchor, post-window return **3.7037%** from fixed fixture prices; N=1, causality `NOT_ESTABLISHED`. Separate tests prove an equity closed weekend respects its own session calendar and missing sessions reject computation. No live calendar/event research outcome is claimed.

## Repeated validation

| Check | Result |
| --- | --- |
| Backend final 1 | 192 passed + 13 subtests, no skips, 259.32 seconds |
| Backend final 2 | 192 passed + 13 subtests, no skips, 251.91 seconds |
| Frontend final 1 | 24 passed, 2.16 seconds |
| Frontend final 2 | 24 passed, 2.05 seconds |
| TypeScript | `tsc --noEmit` passed |
| Production build | Next.js build passed; compile 9.1 seconds |
| UI | Real BTC histories, partial dimensions, negative OOS finding, metadata/raw hash/source-time inspector and truthful source coverage verified in browser |
| Live pipeline | Two real public sources → normalized facts → PostgreSQL/Parquet/manifests → as-of snapshot/API/CORTEX → replay/restore |

One known Starlette/httpx TestClient deprecation warning remains; it is not a functional failure. Local raw logs are ignored under `runtime/phase9-*`. No credentials or private owner configuration are committed.

Corrected validation setup issues are recorded honestly: after the local test cluster stopped, three Phase 9 catalog tests timed out; restarting only the isolated cluster restored them. One new derivative fixture initially specified the wrong funding unit and was corrected. An existing frontend trade-inspector assertion needed to await React state rendering; both final suites now use that awaited check. An editable install without build isolation initially found no local setuptools; the standard isolated package build installed project version 0.9.0 successfully. These attempts are not reported as passes.

## Limitations and readiness

Recorded contextual history is newly collected; historical source publication vintages are not reconstructed. Macro coverage is one narrow monthly Treasury series. There is no complete live event calendar/news/fundamentals/options/on-chain coverage, cross-sectional event study, live chart event markers, liquidation history, GEX/DEX/max pain, sentiment signal or causality claim. Options calculations assume European exercise and caller-supplied rate/carry. Request caching is per process; owner sync remains an explicit CLI action. Upstox/Alpaca are deferred without repeated credential requests.

The architecture is ready for separately scoped Phase 10 work after acceptance, with these limitations preserved. **Phase 10 has not started.** Research-only policy, strict availability, source provenance, local-first operation and ₹0/month remain intact.
