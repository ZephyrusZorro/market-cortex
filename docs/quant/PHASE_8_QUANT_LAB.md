# Phase 8 — Quant Lab

Local, single-user research only. No order placement, broker writes, leverage or arbitrary strategy code. India/US authenticated provider validation remains **DEFERRED_NOT_CONFIGURED**. Crypto accounting is in native USDT, without an assumed INR/USD conversion.

## The historical availability boundary

The original Pilot 5 daily history was recorded on October 3–4, 2026. A candle dated 2025 does **not** mean MARKET CORTEX knew it in 2025. Backfilling increases event history; it does not create historical knowledge.

**AS_RECORDED is the default.** Each decision requires the observation's availability, actual ingestion, original manifest publication, mapping knowledge and completed event time to be at or before its cutoff. Unknown availability is excluded. The pinned source manifest bounds eligible evidence; earlier ancestors supply only observations actually known then. Corrections are selected through the existing Phase 1 revision resolver. A future correction, candle or mapping cannot affect an earlier decision. Unavailable history produces WATCHING/insufficient data and no simulated entry.

**HISTORICAL_RECONSTRUCTION is an explicit assumption-based experiment.** It exposes only completed daily candles after a declared publication lag, selects the earliest original valid revision, excludes correction descendants, and assumes mapping discovery at the mapping's valid-from date. Source envelopes retain their real ingestion and availability timestamps. It cannot establish observed historical knowledge, unseen pre-ingestion revisions, survivorship safety, or prospective OOS evidence. Reports, CORTEX and UI disclose this distinction. Reconstructed studies cannot promote an Edge Library hypothesis to SUPPORTED.

The initial universe is the selected, currently surviving Binance Pilot 5. It is not a historical investable-universe reconstruction. No equity split/dividend/delisting correctness is claimed. Only raw crypto spot data with native USDT and verified 24×7 calendars is supported.

## Architecture and lineage

`quant_contracts.py` contains frozen, strict, versioned definitions. `quant_replay.py` bulk-verifies and captures the immutable source, including envelopes, instruments, mappings, manifest publication times, file hashes and calendar versions. The in-memory replay catalog restricts each historical read.

`ReplayOpportunityService` overrides context discovery and records the market-state snapshot. It calls the same `OpportunityService.scan`, canonical Phase 5 detectors, Phase 2 feature engine, alignment and market-state implementation. There is no second detector formula implementation. The canonical service's shared state hook does not change its rules.

Reconstruction uses a transient publication-lag proxy only in the canonical freshness classifier. Numerical inputs and original observation/feature timestamps remain unchanged. Every reconstructed run discloses the freshness assumption.

`quant_engine.py` handles deterministic long-only simulated fills and accounting. `quant_metrics.py` calculates descriptive metrics independently. `quant.py` freezes run identities, coordinates experiments and attaches explicit edge evidence. `quant_store.py` saves content-addressed PostgreSQL JSON artifacts. PostgreSQL and encrypted catalog backups include these research records; source snapshots allow recomputation without mutable dataset-head reads.

Lineage: strategy/version → definition → source/manifest/cutoff → features/state → candidate/rules → explicit entry decision → simulated fills/costs → trade → reconciled equity → metrics → bounded studies → explicit edge revision.

## Registered strategies

| ID | Signal | Entry | Exit |
|---|---|---|---|
| momentum | Canonical 1.0.0 momentum detector | Current-session VALID only | Fixed initial stop, target R, holding limit |
| breakout | Canonical 1.0.0 breakout detector | Current-session VALID only | Same registered exit policy |
| trend_continuation | Canonical 1.0.0 trend detector | Current-session VALID only | Same registered exit policy |
| pullback | Canonical 1.0.0 pullback detector | Current-session VALID only | Same registered exit policy |
| buy_hold | Predetermined one-instrument allocation | First eligible period entry | Period-end liquidation |
| equal_weight | Predetermined selected-universe allocation | First eligible period entry | Period-end liquidation |

Detector thresholds and their lookbacks stay canonical. The bounded initial parameter searches change only strategy holding periods and initial stop distances. This separates detector quality from entry/exit framework performance. Neutral volatility detectors and unsupported event/order-book detectors are not forced into directional strategies. No outcome-informed candidates are written into the Phase 5 ledger by replay.

Definitions freeze the registered strategy/version, source manifest and cutoff, raw basis, selected symbols/universe, dates, execution, publication lag, fees, slippage, spread proxy, sizing, capital, concurrency, benchmark, annualization, risk-free assumption and exit parameters. The run manifest freezes engine, detector, feature and dependent code hashes, calendar versions and runtime versions. Definitions that differ in these inputs have different identities.

## Execution conventions

- Signals use completed daily bars at bar-end plus an explicit lag (default 60 seconds).
- `next_open` uses the first session open **strictly after** the signal cutoff, plus the requested delay. A midnight-plus-60-second signal has missed the immediately following midnight open. With UTC daily bars the default is therefore the subsequent day's open. This prevents an impossible fill.
- `next_close` uses the first subsequent session close strictly after the cutoff and requested delay. A full-day publication lag therefore requires a later close. The entry candle's earlier high/low cannot trigger an exit or excursion for a close entry.
- Same-close execution is rejected by the contract.
- Entries expire if their scheduled bar is missing; open positions with a missing valuation bar invalidate the run instead of being forward-filled.
- One open/pending position per asset; symbols resolve cash contention in sorted order. Signals during an open position do not automatically add another position.
- Stops use a worse opening price on a gap below the stop. Targets receive their threshold price, without favorable opening-gap improvement.
- If both stop and target occur within one daily OHLC range, default `stop_first` applies. `target_first` is an explicitly optimistic sensitivity setting. Exact intrabar order is unknown.
- Holding limits are session counts. Open entries count their entry session; close entries start monitoring on the following session. Remaining positions are liquidated at the final period close and marked `period_end`.
- Stop/target exit timestamps are session-window upper bounds, not exact broker-fill timestamps.
- MAE/MFE are whole-bar potential bounds. The exit day's extrema may occur after the simulated exit; neither exact timing nor realized intraday excursion is claimed.

## Costs, sizing and accounting

The configurable bps model includes each-side fees, each-fill fixed costs, slippage and half of the full spread proxy on each side. Defaults (10 bps fees and 5 bps slippage) are **research assumptions**, not claimed universal Binance charges. Daily OHLCV cannot identify observed spreads, liquidity depth or precise market impact. There is no volume-capacity or sophisticated impact model.

Sizing supports fixed quantity, fixed notional, equal allocation slots and fixed fractional risk. Fractional risk calls the existing Phase 6 `research_sizing`. All entry quantities are capped by cash including entry fees. No leverage, borrowing, shorting or capital deployment exists. Equal-weight and buy-hold baselines allocate across their selected symbols. Fees can leave unequal residual cash allocation on the final sorted symbol.

Sizing also reserves existing/new positions' fixed exit fees. Baselines have no stop policy: R and open-position stop-based heat are unavailable, and fractional-risk baseline sizing is rejected. Scheduled open entries are processed before that day's simulated exits; proceeds from a later exit cannot fund an earlier entry.

For every session the engine checks:

`net equity = cash + marked position value = initial capital + realized P/L + unrealized P/L`

Gross equity uses the **same simulated quantities** and removes accumulated fee/slippage/spread drag. It is not a separately sized frictionless strategy. Exposure is marked value divided by net equity; heat is initial stop-distance risk divided by net equity. Turnover is absolute entry/exit reference notional divided by initial capital. Cash cannot be negative. Final closed-trade P/L reconciles to final equity change. Stops are hypotheses, not guarantees on loss.

## Metrics and drawdown

All returns are fractions. Total and benchmark-relative returns, conditional CAGR, annualized daily volatility, downside deviation, win/loss rates, trade mean/median/extremes, mean R/expectancy, payoff, profit factor, exposure, turnover, holding duration and streaks include sample sizes. Undefined divisions, absent losing trades and absent trades produce nulls.

CAGR requires at least 365 elapsed days and positive final equity. Daily simple equity returns use 365 annualization for this 24×7 universe. Sharpe requires at least 30 return observations and nonzero sample volatility; the explicit annual risk-free assumption is converted to a daily compounded rate. Sortino uses RMS negative excess returns over all daily observations. These are descriptive; correlated/overlapping trades and small trade samples undermine inference. No p-value or statistical-significance claim is made.

Drawdown is `equity / running peak − 1`. The report includes the series and episodes with peak start, trough, depth, recovery, duration and unrecovered status. The initial capital point precedes the first session, so early losses are included.

Benchmarks are explicit: selected-universe static equal-weight buy-and-hold, BTC buy-and-hold or cash. Price benchmarks are gross before costs and begin at the first period open. An unavailable benchmark is disclosed rather than called an investable historical benchmark. Separate cost-inclusive baseline runs provide a closer comparison. Comparison tables show N, period, replay policy and assumptions, and identify mismatched definitions.

## Walk-forward and sensitivity

Rolling or expanding training windows use a bounded grid (maximum 24 combinations; maximum 144 fold-search combinations). The objective is training net total return. Every training row is retained; deterministic grid ordering breaks ties. The winner is frozen before the next validation period. No validation metric enters selection. OOS periods cannot overlap. Each fold starts flat; training positions close at the training boundary. Previous completed history is allowed for indicator warmup, while candidate cutoffs remain causal. No trade extends past a fold boundary.

Reports include train/OOS ranges, all search results, selected parameters, their freeze hash, train score and OOS run IDs/metrics. Aggregate OOS return compounds separate reset-capital fold returns; it is not a continuous portfolio with carried positions. Reconstructed temporal holdouts are labeled separately from prospective observed OOS results. Reusing a holdout across repeated research is still multiple testing.

Sensitivity displays the complete grid, N per cell, return range and positive-cell fraction. There is no hidden optimization loop or profitable threshold tuning. Artifact/run counts expose searches and unique strategy combinations; they are not independence-adjusted hypothesis counts.

## Robustness, regimes and controls

Initial robustness compares assets, zero/stressed costs, next-close timing, extra entry delay, split periods and adjacent holding durations. Regime grouping uses the canonical market-state category frozen at the signal cutoff. Cells expose N, net P/L and win rate. The standalone rule is transparent: any cell with N<30 → INSUFFICIENT_EVIDENCE; otherwise at least half positive → MIXED; otherwise FRAGILE. A standalone study cannot award ROBUST_CANDIDATE or SUPPORTED.

The report also groups trades by trend, momentum, volatility, breadth, participation and correlation dimensions frozen at the signal. Dimension rows overlap: their Ns must not be added as independent trades.

Candidate/rejected/NO_EDGE groups also have a five-session next-close counterfactual return control. This is zero-cost descriptive, retrospective, overlapping event research. It neither measures a traded strategy nor establishes the causal benefit of a rejection rule. It never modifies genuine pre-registered predictions or their outcomes.

## Seeded Monte Carlo

Bootstrap samples closed-trade **net P/L contributions to initial capital**, with replacement. Permutation changes their order without replacement. Paths add these contributions, retaining a fixed initial-capital convention rather than pretending every trade invested the full portfolio. Reports show method, seed, simulation count, source-trade N and 5/25/50/75/95 percentiles for terminal return, maximum drawdown and losing streak.

Fewer than two trades is rejected. N<30 has an explicit insufficiency warning. This initial model ignores serial dependence, concurrent positions and changing allocation. It is not a predictive price distribution or a calibrated forecast. Permutations preserve terminal sum; they only vary the path. Block bootstrap is deferred.

## Edge Library quality gates

Evidence attachments require an explicit existing matching detector/version/classification, expected edge revision, run/study IDs and reason. They append a separate immutable revision visible only after its actual recording time. No model tool writes an edge, and no profitable run automatically changes status.

EARLY_EVIDENCE needs at least 10 trades in an attached run. SUPPORTED requires recorded replay, ≥30 trades, ≥3 assets, ≥2 known regimes, ≥30 OOS trades with positive aggregate OOS return, ≥70% positive sensitivity and robustness cells, sufficient robustness cell N, and a run with positive both-side fee assumptions. Unrelated studies are rejected. These conservative research gates are not an estimated probability of profit. Historical reconstructions cannot satisfy the recorded-evidence requirement.

The ≥30-trade threshold must be met by at least one run; duplicate parameter variants cannot manufacture that sample requirement.

## Local jobs, API, CLI and CORTEX

`POST /api/v1/quant/jobs` accepts only a typed registered operation: backtest, walk_forward, sensitivity, robustness, monte_carlo or comparison. It validates its nested payload before enqueueing. Existing JobQueue handles queued/running/completed/failed states, a bounded lease and idempotency. Background execution claims only the requested quant job. Failure messages are fixed codes; explicit retry is available. There is no distributed queue or arbitrary command input. Process interruption can be recovered after a lease expires and the same request is submitted again.

GET routes expose registry, recent runs, run detail/trades/metrics, recent studies, study detail and job status. POST routes verify saved replay and attach explicit edge evidence. The workstation proxy allows only these fixed loopback paths and bounded requests.

CLI: `quant-strategies`, `quant-backtest`, `quant-inspect`, `quant-replay`, `quant-walk-forward`, `quant-sensitivity`, `quant-robustness`, `quant-monte-carlo`, `quant-compare`. Research commands take `--input` with strict JSON. CORTEX research also accepts `--backtest-run-id` and `--quant-study-id`.

CORTEX allowlisted tools read run summaries, exact runs, studies and trades at the research visibility cutoff. They explain stored deterministic values and cite their original source/context. Questions about quant research avoid accidentally selecting a live portfolio or learning outcome as strategy performance. Run evidence exposes N, period, costs, timing, OOS status and limitations. Quant records remain private and cannot be sent to a cloud model under the existing private-data gate. No Python strategy generation/execution tool exists.

The Quant Lab workstation includes strategy registry, typed creation, job status, saved runs, net/gross/benchmark/drawdown curves, metrics, trade/evidence inspector, regimes, controls, complete sensitivity tables, fold views, robustness, seeded Monte Carlo, comparison and explicit edge attachments. Source manifests and cutoffs remain visible.

## Verification and pilot evidence

See `PHASE_8_PILOT_RESULTS.json` and the Phase 8 exit matrix for actual results, final test totals and representative timings. Synthetic fixtures independently check profits/losses, cash reconciliation, fees/slippage, next-open/next-close, gap stops, ambiguous bars, drawdown, seeded paths, complete grids and train/OOS isolation. Actual stored Binance validation compares canonical live/pinned detector outputs to recorded replay and checks saved result/evidence hashes.

The public backfill extends 2024-01-01 through 2026-10-03: 1,007 sessions per asset. This is sufficient for functional temporal experiments, not proof of an edge. Negative and no-trade results remain in the report. Strict observed historical evidence is still insufficient because actual recording began recently. Longer history does not cure this limitation.

The full detector/study pilot was computed with preserved local commit `e2c9554`; its source hash matches the stored implementation manifest. The accepted release additionally stores a small derived PostgreSQL summary projection to avoid repeatedly decompressing large decision ledgers for list requests. Numerical calculator files remain identical. Since the broad implementation hash includes storage code, old studies require their archived commit/runtime for cold recomputation; the release returns VERSION_UNAVAILABLE instead of falsely claiming equivalence. Full payload/hash inspection and CORTEX evidence replay remain available. A fresh full-history BTC baseline cold replay validates the release implementation.

[PHASE_8_ENVIRONMENT.json](PHASE_8_ENVIRONMENT.json) records the actual Python, architecture and installed package versions used for these experiments. It contains no credentials or local paths. Retain that inventory with the archived computation commit and the immutable source artifacts when reproducing a pilot study.

Apply migrations through `0009_quant_summaries.sql` and restart the local API when upgrading. Summary projection migration reads existing records once; it does not replace their payloads, result hashes, source history or timestamps. Summary lists are browsing aids; full saved payloads remain authoritative. Representative full-history studies took 57.28 minutes in total under concurrent regression load; shared canonical scans reduced later full-period detector runs to about 52–54 seconds. Summary browsing returned 50 items in 633 ms after the projection fix. All timings are measured local workloads.

An encrypted quant catalog subset restore reproduced the actual full-history BTC run, its embedded source and its derived summary exactly, then recomputed the same result hash. This subset drill complements the full regression's underlying Parquet/identity/as-of restore drill; its scope is recorded explicitly in the pilot JSON and exit matrix.
