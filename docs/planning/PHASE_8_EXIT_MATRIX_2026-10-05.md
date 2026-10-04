# Phase 8 exit matrix — 2026-10-05

**Status:** Final acceptance checks in progress. **Release target:** `phase8-v0.8.0`; commit reference `phase8-v0.8.0^{commit}` will resolve to the accepted implementation. Baseline `phase7-v0.7.0` at `2bcb33f` is preserved. No external push; Phase 9 has not begun. Development and public Binance validation use the isolated `PILOT_TEST` catalog ending `_test`; the owner main database and `C:\MarketCortexData` were not modified.

## Acceptance A–S

| Gate | Result | Evidence |
| --- | --- | --- |
| A — Phase 1–7 regression | Pending final repeats | All existing gates remain enabled, including PostgreSQL, encrypted backup/restore, API, analytics, CORTEX, opportunity, risk and learning pilot integrations. |
| B — Point-in-time replay | Pass | Default AS_RECORDED excludes unavailable/late ingestion, future manifest publication, future mapping, future candle and future correction. Real old history produces no entries. Separate labelled reconstruction assumes publication-lag freshness/mapping; original timestamps stay unchanged. |
| C — Canonical detector parity | Pass | Actual known Binance manifest/as-of: full candidate payloads compare equal for live/pinned scan and strict replay, excluding wall-clock calculation metadata. No second detector implementation. |
| D — Frozen reproducibility | Pass | Strict versioned definitions, source snapshot/file checksums, calendar/features/detector/engine/runtime hashes, immutable JSON artifacts, guarded result/definition/study hashes and recomputation. Future dataset-head changes do not replace pinned evidence. |
| E — Explicit execution timing | Pass | First eligible open/close strictly after signal cutoff; full-day-lag boundary fixture; no same-close; next-close entry excludes earlier candle extrema. Stops/targets are daily window proxies. |
| F — Costs/slippage | Pass | Each-side fee bps, fixed fee per fill, each-side slippage and full-spread proxy; manual fee/slippage examples. Defaults are research assumptions, not observed universal exchange fees. |
| G — Portfolio accounting | Pass | Cash capped including fixed exit fee reserves; Phase 6 fractional-risk sizing; deterministic concurrency; every session reconciles net equity to cash/marked value and capital/realized/unrealized P/L. No borrowing. |
| H — Independent metrics | Pass | Hand-calculated wins/losses, fee impact, profit factor, payoff, R, daily alternating-return CAGR, sample volatility, downside, zero Sharpe/Sortino and inappropriate-statistic nulls. |
| I — Equity/drawdown | Pass | Net/gross/benchmark/drawdown chart, known peak/trough/recovery/unrecovered fixture, durations and trade MAE/MFE daily-bar bounds. Baseline R/stop heat unavailable. |
| J — Walk-forward isolation | Pass | Rolling/expanding bounded training search, all rows retained, deterministic tie, parameters frozen before subsequent non-overlapping OOS ranges, flat fold boundaries. Tests assert train ranges and chosen parameter equality. |
| K — Parameter sensitivity | Pass | Complete bounded grid, per-cell N, winner and every losing region, tested deterministic output. No canonical detector threshold tuning. |
| L — Robustness | Pass | Assets, zero/stress costs, execution/delay, periods and holding perturbations; frozen state dimension/regime breakdowns and explicit sample classification. No automatic robust promotion. |
| M — Monte Carlo | Pass | Seeded empirical net P/L bootstrap/permutation; terminal/drawdown/streak percentiles, source N and small-sample warning; N<2 rejected; permutation terminal invariant. No price forecasting. |
| N — Comparison | Pass | Every requested run retained with N, period, replay policy, costs and comparability warning. Four detector strategies and cost-inclusive baseline. |
| O — Grounded CORTEX quant | Pass | Fixed read-only run/list/study/trade tools, stored numerical metrics/context/limitations, citations and saved evidence replay. Cloud spy proves private quant context blocked even with cloud flag enabled. |
| P — Quant Lab workstation | Pass | Browser QA covered typed creation/job completion, exact saved-run opening, costs/assumptions, curves/trade evidence, six fold timelines/all training rows and actual Monte Carlo sample/methodology. Repeated 21-test suites, production build and typecheck passed. Overview calculation is independent of Quant Lab loading. |
| Q — Edge evidence quality | Pass | Explicit matching hypothesis/version/classification, append-only recording-time revision and optimistic conflict; SUPPORTED gate requires recorded OOS/sample/assets/regimes/costs/sensitivity/robustness. Reconstruction cannot promote SUPPORTED. Predictions remain untouched. |
| R — Research-only boundary | Pass | Whitelisted typed strategies/operations; no eval/exec/uploaded Python; provider GET-only source adapters; no order, broker write, leverage or capital deployment. |
| S — Repeated complete suites | Pending | Final backend/frontend repeat totals and build recorded below after completion. |

## Implemented scope

Four canonical 1.0.0 Phase 5 strategies: momentum, breakout, trend_continuation and pullback. Two predetermined baselines: buy_hold (one asset) and equal_weight. Raw USDT crypto spot, P1D, selected surviving Binance Pilot 5 and verified 24×7 calendars. No fake equity corporate-action or survivorship correctness.

Replay bulk-verifies immutable Parquet, freezes envelopes/mappings/manifest publication/calendar data in PostgreSQL, then exposes only cutoff-eligible observations to the Phase 2 numerical engine and Phase 5 detector. Simulated decisions/candidates/state/observation lineage remain separate from trade execution, subsequent outcomes, portfolio paths and Phase 7 pre-registered predictions. Cache identity freezes source, strategy/version, period, symbols, parameters, sizing, costs, execution, calculation hashes and runtime. Shared daily canonical scans reduce repeated grid computation without changing decisions.

Default assumptions: 10,000 USDT initial capital, up to five long positions, cash-capped equal slots, fixed initial 8% stop, 2R target, 10-session holding cap; 10 bps entry/exit fee and 5 bps each-side slippage; spread proxy/fixed fee zero. Publication lag 60 seconds means the immediately following midnight open is unavailable, so next_open uses the later UTC open. stop_first resolves ambiguous high/low; favorable target-first is optional labelled sensitivity. No volume/impact precision is inferred from daily OHLCV.

Gross curve removes accumulated friction from the same quantities; price benchmarks are explicit gross static buy-and-hold. Baseline simulation includes costs, and has no invented stop R/heat. Daily returns annualize at 365 with explicit RF=0. Undefined ratios remain null; CAGR requires ≥365 elapsed days; Sharpe/Sortino need ≥30 daily returns and valid denominators. Dimension groups overlap and their Ns cannot be summed as independent trades.

## Actual Binance history and strategy results

Public immutable backfill appended 609 sessions per asset (2024-01-01–2025-08-31), 3,045 bars total, extending preserved September 2025–October 2026 evidence. Current common depth: 1,007 sessions/asset, 2024-01-01–2026-10-03. Preserved Phase 7 head `f87c2a62-7cdf-443d-8eed-0575b6dd8e17`; descendant head `3bf002d2-15f2-4f9d-8c54-cc7eb3fb349c`. Actual recording began October 3–4, 2026; backfill does not create 2024 knowledge. The final experiment invocation reused this completed backfill; it did not ingest a second copy. Its recorded SQL evidence contains the actual publication times and counts.

Strict AS_RECORDED full-period research: N=0, no trades, cash unchanged, historical benchmark unavailable. This is insufficient observed evidence, not a profitable or fully invested historical result. Reconstruction is assumption-based temporal research and cannot prove prospective OOS performance.

All results below are HISTORICAL_RECONSTRUCTION under the disclosed default assumptions. They are descriptive simulated outcomes, not a claim of observed historical availability or an investable forecast. Exact IDs, definitions, every grid/fold/robustness row, source cutoffs and unrounded values are retained in [the generated pilot evidence](../quant/PHASE_8_PILOT_RESULTS.json).

| Strategy | Closed trades N | Gross return, same quantities | Net return | Maximum net drawdown |
| --- | ---: | ---: | ---: | ---: |
| Momentum | 108 | −19.94% | −26.24% | −29.25% |
| Breakout | 67 | +4.79% | +0.77% | −16.01% |
| Trend continuation | 145 | −12.70% | −21.04% | −31.23% |
| Pullback | 133 | +3.91% | −3.92% | −24.65% |
| Equal-weight Pilot 5 baseline | 5 | +85.73% | +85.30% | −61.13% |
| BTC buy-and-hold baseline, final storage implementation | 1 | +100.29% | +99.84% | −52.97% |

The explicit gross static Pilot 5 benchmark returned +85.92%; the BTC gross static benchmark returned +100.44%. Cost-inclusive simulated baselines use eligible execution timing, cash caps and liquidation, so they differ from the gross price benchmark. N=1/5 baselines cannot establish detector quality, expectancy or significance. Their stop-based R and heat are unavailable. Costs changed the pullback's positive gross result into a net loss. Breakout's small positive return alone does not establish a robust edge; its OOS and robustness were not separately searched in this pilot. No threshold was changed to make a result profitable.

### Walk-forward

Momentum study `e70e6b51-827d-5d69-9248-e2bad774f0db`: rolling 180-session training, 90-session validation and step, six folds, holdings 5/10/15 × stops 6%/8%, 2R target. All 36 training combinations remain visible. Selection maximizes training net return only. Each fold starts flat; aggregate compounds the separate reset-capital returns.

| Fold | Training range | Hold / stop selected | Training return | Validation range | OOS N | OOS net return |
| --- | --- | --- | ---: | --- | ---: | ---: |
| 1 | 2024-01-01–2024-06-28 | 15 / 6% | −3.29% | 2024-06-29–2024-09-26 | 7 | −7.29% |
| 2 | 2024-03-31–2024-09-26 | 10 / 6% | −9.99% | 2024-09-27–2024-12-25 | 30 | +3.41% |
| 3 | 2024-06-29–2024-12-25 | 15 / 6% | −1.46% | 2024-12-26–2025-03-25 | 7 | −5.14% |
| 4 | 2024-09-27–2025-03-25 | 5 / 8% | +1.34% | 2025-03-26–2025-06-23 | 17 | +0.38% |
| 5 | 2024-12-26–2025-06-23 | 15 / 8% | −0.28% | 2025-06-24–2025-09-21 | 16 | +10.05% |
| 6 | 2025-03-26–2025-09-21 | 15 / 8% | +13.21% | 2025-09-22–2025-12-20 | 5 | −8.24% |

Aggregate: **82 OOS trades, −7.82% compounded net return**. This is a temporal holdout from reconstructed history, not prospective recorded OOS evidence. Several folds have small trade counts. The configured six-fold cap ends validation on 2025-12-20; it does not imply OOS evaluation of the remaining 2026 history.

### Sensitivity, robustness and regimes

Momentum sensitivity `6319a0dc-9a68-55df-88b3-9147aa80fe62` tested all nine holdings 5/10/15 × stops 6%/8%/10%. **Zero of nine cells was positive**; net returns ranged from −26.24% to −7.77%. The least negative cell is shown as an in-sample descriptive winner, without a profitability claim.

Robustness `a752070f-f8b3-5eef-8852-6d7a9ecaece8` returns **INSUFFICIENT_EVIDENCE**: minimum cell N=15; only one of 13 cells positive. Cells are dependent, not 13 independent tests.

| Dimension | N | Net return |
| --- | ---: | ---: |
| BTC only | 25 | −3.82% |
| ETH only | 21 | +3.96% |
| SOL only | 22 | −5.81% |
| BNB only | 27 | −10.90% |
| XRP only | 15 | −12.75% |
| Zero-cost rerun | 109 | −20.73% |
| Stress costs | 108 | −40.06% |
| Next-close timing | 109 | −26.34% |
| Additional session delay | 100 | −7.33% |
| First half | 54 | −15.87% |
| Second half | 57 | −12.67% |
| Holding 8 sessions | 117 | −26.46% |
| Holding 12 sessions | 98 | −21.97% |

Zero-cost reruns can change quantities and subsequent fills; they are distinct from the same-quantity gross curve. All robustness rows retain their frozen overall/trend/momentum/volatility/breadth/participation/correlation regime Ns, P/L and mean returns. Small favourable subgroups do not demonstrate a regime edge. Rejection and NO_EDGE controls remain labelled zero-cost, overlapping, retrospective five-session next-close outcomes; they never become pre-registered predictions.

### Monte Carlo

`5b2d707e-2b49-5d45-8063-fc44b84110fc`: 108 observed simulated net trade contributions, 1,000 empirical bootstrap paths, seed 20261004, additive fixed-initial-capital convention.

| Percentile | Terminal return | Maximum drawdown | Longest losing streak |
| --- | ---: | ---: | ---: |
| 5 | −51.21% | −54.29% | 5 |
| 25 | −37.68% | −41.29% | 7 |
| 50 | −26.82% | −32.47% | 8 |
| 75 | −15.98% | −23.34% | 10 |
| 95 | +2.32% | −14.51% | 13 |

Drawdown percentiles are numerically ordered negative values. This resampling ignores overlap, allocation changes and serial dependence; it is not a calibrated future distribution. `ruin_paths_N=0` counts nonpositive terminal capital under this implementation, not an absorbing intrapath ruin probability. Permutation and small-sample boundaries are independently tested.

### Preserved versions and replay

An earlier saved baseline `c03dd9cb-a2af-59ea-9f29-5e2161ec7462` was created at 2026-10-04T17:35:42.866524Z, before the first backfill manifest at 17:35:44.383922Z. Its original result hash remains `f279bec5f0d58af875d75f8f14c42b5679443bf4533a911cd4ad689f5cf3c70c` and verifies after ingestion. It is an early development-version artifact; its computation version is unavailable in the accepted release, so no current cold-replay match is claimed.

The complete detector studies and preserved-pin recomputation were produced with archived local commit **`e2c9554`**, implementation hash `484c408f18e06dddc648efd5b843eef9139af27eb9e1531f95aad007d7c3791b`. The stored momentum hash was checked against that commit's actual source bytes. Its preserved-pin run `4b72e3e7-b4a9-5a12-a89c-46d03feb8e67` recomputed MATCH while the actual catalog head was the descendant. This run was created after backfill at the old pin; the separate earlier baseline above proves preservation across actual ingestion.

The final release adds a derived PostgreSQL summary projection for efficient browsing; numerical calculator files are identical to `e2c9554`. The broad implementation hash includes storage code, so older research remains inspectable and integrity-verifiable but correctly returns VERSION_UNAVAILABLE for recomputation under a different implementation. Recompute those studies using `e2c9554` and their recorded runtime/source. Fresh full-history BTC baseline `5200c74d-b1ed-5efb-907e-94e238fc1448` and cold replay returned **MATCH**, result hash `70b5d9dc7598b52c117311a319a188f3a37e1c724ce921132f9bce280dfe3187`, under final implementation hash `5a2b6ddb60123572e1c12d52104cd2fe4f681190b08aefce41fcb8cca5c51353`. Calculation plus cold replay took 21.79 seconds.

## Edge Library and CORTEX

No owner hypothesis was promoted. Only labelled SYNTHETIC_TEST fixtures exercised attachments/conflicts and were cleaned up; prediction registrations and outcomes are preserved. The pending Phase 7 pre-registered prediction remains pending until its exact horizon has completed.

CORTEX reads stored research metrics. Explanations expose N, period, exact costs/execution, replay policy, in-sample or temporal OOS status and limitations. Private cloud blocking, safe missing-artifact failure, explicit failed-job retry and evidence hash replay are tested. No strategy code generation/execution is enabled.

Actual saved deterministic explanations: `a4c406b8-1e87-4e56-9a5a-c04fcaf63778` for momentum plus walk-forward, and `4a1a2ea5-9148-4ec7-afa7-8db988e94474` for Monte Carlo. Both have no failure state; all five stored tool-evidence hashes replayed identically. Language reproducibility is explicitly not claimed. Required quant disclosures survive model claim selection and truncation, and unrelated live SMA invalidation is suppressed for quant answers.

## Verification and performance

Final complete regression/build totals are recorded after their completion. Prior complete runs passed 149 tests + 13 subtests in 677.76 seconds and 150 tests + 13 subtests in 630.71 seconds as boundary/disclosure tests were added. Intermediate runs interrupted for implementation changes are excluded from acceptance evidence. One known Starlette/TestClient/httpx deprecation warning remains.

The first full regression under the frozen final implementation passed **150 tests + 13 subtests**, no skips, in **672.17 seconds**. The identical final implementation is being repeated before acceptance.

The final frontend suite passed **21/21 tests twice** (9.63 s and 7.86 s, seven files). Next.js production build compiled successfully in 19.5 s, passed its TypeScript/static generation stages, and the separate `tsc --noEmit` check passed. Temporary localhost QA servers/tabs were stopped, and their generated development agent files were removed. The build restored the tracked production type imports.

One later backend attempt exposed test setup contamination: migration checks had populated the explicitly disposable restore target, violating its empty-database precondition. That attempt was interrupted, both dedicated `_test` public schemas on port 55432 were reset after verifying database/role/port, and the complete final suite was restarted. This is recorded as a corrected test-environment failure, not a passing run; no owner data was involved.

A separate encrypted **quant catalog subset** drill copied the actual 1,007-session BTC run and its captured immutable source into a fresh disposable catalog, backed up/restored it, verified identical full run/source/derived summary payloads, and cold-replayed MATCH with the same result hash. It took **17.51 seconds**. That subset has no underlying Parquet catalog files; it specifically validates quant record/summary survival and embedded-source recomputation. The complete regression's separate encrypted restore drill validates underlying immutable Parquet/as-of/identity/revision lineage. Both temporary quant databases and their files were removed; no owner catalog was used.

The complete full-history experiment took **3,437.07 seconds (57.28 minutes)** while regression work ran concurrently. The first momentum replay took 19.32 minutes; shared canonical scan caching reduced subsequent full-period detector runs to approximately 51.81–54.17 seconds and the equal-weight baseline to 38.85 seconds. These are measured workloads on this local machine, not guaranteed interactive latency. The final BTC baseline is measured separately in the JSON evidence.

At the complete experiment measurement: 88 unique run combinations, five strategies examined, 24 captured source artifacts and one each of walk-forward/sensitivity/robustness/Monte Carlo/comparison. Later baseline/regression artifacts raise these counts; API search counts expose current totals. No multiple-testing correction is claimed. Storage verification found **185 referenced Parquet artifacts**, zero missing/corrupt/unreferenced files and zero staged files; no deletion was performed.

Growing full decision ledgers exposed a list-request timeout. Migration `0009_quant_summaries.sql` builds a small derived browsing projection and new writes save it atomically with the immutable record. Detail/replay use the authoritative full payload and hashes. A loopback API request returned 50 summaries in **633 ms**, compared with the earlier request exceeding 40 seconds. Apply migrations and restart the local API before using the new summary schema.

## Limitations and readiness

- Historical reconstruction cannot establish what the local system actually knew before recording, unseen prior provider revisions or prospective OOS performance. Strict replay honestly returns insufficient evidence for the older pilot period.
- Selected surviving crypto universe; no equity corporate actions, historical delisting/membership, authenticated India/US validation or FX conversion. Upstox/Alpaca remain DEFERRED_NOT_CONFIGURED with no credential requests.
- Daily OHLC gives no exact stop/target sequence, fill time, realized intraday excursion, quote spread, depth, queue position, volume capacity or calibrated impact. Exit-day MAE/MFE can include extrema after the simulated exit.
- Dependent/overlapping trades, reused temporal holdouts and multiple searches invalidate simplistic independence/significance claims. Search/artifact counts are disclosed; no statistical correction or calibrated probability is claimed.
- Walk-forward starts flat and compounds separate reset-capital fold returns; it is not a continuous carried-position portfolio. Train-only selection does not turn reconstructed holdouts into prospective evidence.
- Monte Carlo is additive empirical trade-P/L research with fixed initial-capital contributions, ignoring allocation changes, overlap and serial dependence; block bootstrap deferred. Small samples explicitly warned.
- Large historical studies run as bounded local jobs and may take minutes. Immutable development artifacts remain inspectable under their recorded implementation version; incompatible replay returns VERSION_UNAVAILABLE.

Phase 9 must remain unstarted until final Phase 8 acceptance is recorded. The research capabilities can support later work; the pilot does not establish a proven market edge.
