# Phase 5 — Opportunity Engine and structured theses

MARKET CORTEX Phase 5 turns stored Binance Pilot 5 daily observations into inspectable **research situations**. A `VALID` thesis means its versioned rules currently pass; it is neither a trade instruction nor a probability of profit. No route or command can place an order. Upstox and Alpaca live validation remains `DEFERRED_NOT_CONFIGURED`.

## Deterministic pipeline

`manifest + UTC availability cutoff → Phase 2 features / aligned comparison / MarketStateSnapshot → detector rules → Candidate → optional CORTEX review → append-only Thesis versions`

`ScanRequest` selects latest head, a published manifest, or a historical as-of cutoff. A manifest whose `created_at` is after the cutoff is refused. `FeatureEngine.load` uses raw Binance P1D bars and the catalog's as-of revision selection; missing sessions remain missing. The scan pins one manifest and cutoff across every instrument. Each symbol's latest *visible* session is evaluated. The market-state snapshot is calculated once at the common Pilot 5 session and identifies its own date and rule version. A state older than the instrument's evaluated session cannot support `VALID`.

The eight enabled detectors use existing Phase 2 feature functions and same-session Phase 2 relative-strength alignment. They do not recalculate RSI, returns, volatility or moving averages in AI or the browser. Breakout's previous 20-session high is derived from the 20 visible prior daily highs, excluding the current bar; a gap makes it unavailable. All rule comparisons are inclusive or strict exactly as shown below. Parameters, feature version, feature/result IDs, source observation, manifest, cutoff, freshness, quality and coverage are retained as evidence.

## Detector rules, version `1.0.0`

All use crypto spot, `P1D`, the named five-pair Binance pilot, and at least 90% visible-session coverage. At least the detector's minimum history must be visible. A missing required trigger or confirmation produces `insufficient_data` unless a known failed trigger already establishes rejection. A rejection veto beats a qualifying trigger. The directional detectors have bullish *research bias* only; volatility expansion is neutral. The recorded horizon is `swing_days_2_to_20`.

| Detector | Minimum bars | Triggers | Confirmations | Rejection veto | Research invalidation |
| --- | ---: | --- | --- | --- | --- |
| Momentum | 55 | Return20 > 5%; RSI14 in 55–75 | MACD histogram > 0; SMA20 > SMA50 | RSI14 > 85 (extension) | Return20 < 0 |
| Breakout | 55 | Close > prior 20-session high | Relative volume20 ≥ 1.2; SMA20 > SMA50 | Relative volume20 < 0.8 (false-breakout risk) | Close < recorded prior high |
| Pullback | 55 | SMA20 > SMA50; return5 < 0 | Close ≥ SMA50; RSI14 in 40–60 | Return20 < −10% (possible reversal) | Close >3% below SMA50 |
| Trend continuation | 55 | SMA20 > SMA50; close > SMA20 | SMA20 five-session slope > 0; MACD histogram > 0 | Close >8% below SMA20 | SMA20 < SMA50 |
| Relative strength | 25 | Aligned 20-session alt/BTC fractional outperformance > 3% | Own return20 > 0 | Own return20 < −10% | Alt/BTC relative performance < 0 |
| Volatility expansion | 115 | Volatility rank90 ≥ 75 | Bollinger bandwidth20 ≥ 10%; relative volume20 ≥ 1.2 | Relative volume20 < 0.8 | Volatility rank90 < 40 |
| Mean reversion | 115 | Close ≥8% below SMA20 | RSI14 ≤ 35; volatility rank90 < 80 | SMA20 < SMA50 (downtrend veto) | Close reaches SMA20 |
| Swing trend | 55 | Return20 ≥ 5%; SMA20 > SMA50 | Annualized volatility20 < 80%; drawdown > −25% | Drawdown ≤ −25% | SMA20 < SMA50 |

`relative_strength` is **fractional outperformance versus BTCUSDT** in the same USDT quote currency and daily calendar. BTC compared with itself is an explicit `unsupported` result. The comparison does not rank the whole crypto market. `liquidity_sweep`, `event_driven` and `accumulation_proxy` are registered as disabled/unsupported because daily OHLCV cannot substantiate order-book sweeps, timestamped events or institutional accumulation. There is no order book, funding or verified event feed in this phase.

The registry in `opportunity_detectors.py` is canonical. A changed rule requires a new detector version; the candidate identity also includes the detector and scanner code hash so a changed implementation does not silently reuse an old event. A breakout with no complete prior high is `insufficient_data`, even if its current close is positive. There is no opaque numeric score or fitted win probability.

## Candidate outcomes, evidence and strength

For each supported symbol/detector pair, the scanner returns a versioned `Candidate` with `candidate`, `rejected`, `insufficient_data` or `unsupported` outcome. An unavailable instrument mapping is reported in `ScanResult.unavailable_members` rather than inventing an instrument ID. A scan of all eight enabled detectors across Pilot 5 returns 40 records, including the unsupported BTC-versus-BTC comparison.

Each candidate includes the detector ID/version, instrument, raw manifest/cutoff, event date, market-state snapshot ID, bias, horizon, machine-readable trigger/confirmation/invalidation/rejection conditions, observed values and thresholds, referenced evidence IDs, supporting and opposing evidence IDs, contradictions, rejection reasons, coverage, freshness, quality, and `evidence_hash`. `created_at` and elapsed time are operational metadata; the rule result and candidate ID are deterministic for the same evidence state.

Rules for outcome and status:

1. Inadequate visible history, coverage below 90%, missing evaluated bar, or an unknown required condition yields `insufficient_data` / `WATCHING`.
2. A known false trigger yields `rejected` / `NO_EDGE`. A met rejection veto yields `rejected` / `AVOID`.
3. A triggered candidate has `DEVELOPING` when multiple confirmations are outstanding, `AWAITING_CONFIRMATION` when one is outstanding, or `VALID` when all confirm. An observed invalidation condition changes status to `INVALIDATED`.
4. `VALID` is downgraded to `WATCHING` if source freshness/quality or market-state coverage is inadequate or if the market-state session trails the candidate session. A broad downtrend downgrades a bullish `VALID` candidate to `AWAITING_CONFIRMATION`.
5. Contradictions retain their actual reasons. Source not current, unavailable market state, rejection vetoes, invalidation conditions and broad downtrend are visible rather than suppressed.

Strength is **weak** for every rejected/insufficient/unsupported outcome, `WATCHING`/`DEVELOPING`, stale or uncertain source, unavailable market state, or unacceptable bar quality. It is **strong** only for a fully `VALID`, current, quality-passing candidate without contradictions. Other qualifying candidates are **moderate**. It is an evidence-completeness label, never a forecast.

`NO_EDGE` and the rejection ledger are first-class research outputs. The workstation never relaxes thresholds just to fill a scanner table. The ledger captures all recorded rejected/insufficient/unsupported events, not only almost-qualifying winners, to reduce future selection bias.

## Persistence and lifecycle

Scans are ephemeral by default. `record=true` appends candidates and rejections to `opportunity_candidates`; repeat scans with the same manifest, bar, detector version, measured values, status and freshness deduplicate by deterministic `candidate_id`. A new manifest, observation revision, result or freshness state creates a new event. The first persisted payload keeps the original cutoff; subsequent equivalent scans do not overwrite it. This is a bounded five-pair daily ledger, not a tick-level event stream.

A recorded candidate or rejection can become a `research_theses` head plus immutable `research_thesis_versions`. The `Thesis` snapshot stores its candidate, status, statement, conditions, supporting/opposing evidence references, assumptions, risk factors, limitations, feature versions, manifest/as-of, CORTEX run references and transition history. The head updates only its version pointer; historical version payloads are never overwritten. PostgreSQL row locking serializes updates. Creation from the same candidate is idempotent.

Status semantics and permitted transitions are enforced by `VALID_TRANSITIONS` in `opportunity_store.py`:

| Status | Meaning | Normal next states |
| --- | --- | --- |
| `WATCHING` | Interesting, immature or data-limited | `DEVELOPING`, `AWAITING_CONFIRMATION`, `VALID`, `NO_EDGE`, `EVENT_RISK`, `AVOID` |
| `DEVELOPING` | Multiple confirmations incomplete | `WATCHING`, `AWAITING_CONFIRMATION`, `VALID`, `NO_EDGE`, `EVENT_RISK`, `AVOID`, `INVALIDATED` |
| `AWAITING_CONFIRMATION` | One explicit confirmation outstanding | `WATCHING`, `DEVELOPING`, `VALID`, `NO_EDGE`, `EVENT_RISK`, `AVOID`, `INVALIDATED` |
| `VALID` | Present deterministic requirements pass | `WATCHING`, `DEVELOPING`, `AWAITING_CONFIRMATION`, `NO_EDGE`, `EVENT_RISK`, `AVOID`, `INVALIDATED` |
| `NO_EDGE` | No advantage under these rules | `WATCHING` only by an audited owner reopening; detector monitoring otherwise preserves it |
| `EVENT_RISK` | Owner-identified event/data concern; no verified event feed yet | `WATCHING`, `NO_EDGE`, `AVOID` by owner; detector monitoring preserves it |
| `AVOID` | Rejection or risk veto | `WATCHING` only by an audited owner reopening; detector monitoring otherwise preserves it |
| `INVALIDATED` | Prior thesis has broken a recorded condition or lost its basis | `WATCHING` only by an audited owner reopening; detector monitoring otherwise preserves it |

Same-status updates are versioned when meaningful evidence changes or the owner records a decision. Detector monitoring cannot silently reopen terminal or owner-held statuses. A prior `VALID` thesis whose new evaluation is `NO_EDGE`, `AVOID` or `INVALIDATED` becomes `INVALIDATED`. The owner may set only `WATCHING`, `NO_EDGE`, `EVENT_RISK` or `AVOID`, with a written reason. An owner cannot declare `VALID`. `ThesisTransition` records actor, reason, from/to status, timestamp, manifest, cutoff and changed evidence IDs. Monitoring rejects a cutoff older than the current thesis cutoff. The comparison API reports status, manifest, evidence and contradictions between stored versions.

## CORTEX boundary

CORTEX v1 has three new allowlisted, read-only tools: ephemeral `opportunity.scan`, immutable `opportunity.candidate` and version-pinned `opportunity.thesis`. General opportunity questions use the scanner tool; a candidate ID causes CORTEX to cite the recorded status, conditions and contradictions. With an explicit older manifest, or a question about the previous manifest, CORTEX scans both pinned contexts and emits paired status/outcome comparisons that cite evidence from each manifest. "Previous" resolves the selected manifest's parent. The thesis review endpoint creates a Phase 4 research run pinned to the candidate manifest and cutoff, then attaches its run ID to a new thesis version after verifying exact symbol/manifest/cutoff and successful evidence retrieval. CORTEX can explain or challenge, but cannot write candidate calculations or set `VALID`. Its optional local model selects pre-grounded claim IDs only; deterministic fallback works without a model. Saved research runs retain their own evidence replay.

## Local API and CLI

All routes are loopback-only under `/api/v1/opportunities`:

| Method | Route | Use |
| --- | --- | --- |
| GET | `/detectors` | Enabled and explicitly unsupported rule definitions |
| POST | `/scan` | `ScanRequest`: mode, manifest, cutoff, optional symbol/detector, optional `record` |
| GET | `/candidates`, `/candidates/{id}` | Bounded list/filter and full evidence detail |
| POST | `/theses` | Create from a recorded candidate ID |
| GET | `/theses`, `/theses/{id}`, `/theses/{id}/versions` | Current and immutable version history |
| GET | `/theses/{id}/comparison?from_version=1&to_version=2` | Deterministic version difference |
| POST | `/theses/{id}/monitor` | Re-evaluate with a new selected market context |
| POST | `/theses/{id}/decision` | Audited owner status and reason |
| POST | `/theses/{id}/review` | Grounded CORTEX review and research-run linkage |

CLI commands: `scan-opportunities`, `inspect-candidate`, `create-thesis`, `inspect-thesis`, `monitor-thesis`. `scan-opportunities --record` persists; omission remains read-only. The existing `research` command accepts `--candidate-id` and `--thesis-id` for grounded CORTEX review and `--older-manifest-id` for paired opportunity comparisons. Standard `--mode`, `--manifest-id`, `--as-of`, `--symbol`, and `--detector-id` controls apply. Database credentials remain environment-only. Apply migration `0004_opportunity_theses.sql` with the existing `migrate` command to a selected catalog before using the new routes.

The Next.js workstation has an **Opportunities** section with an ephemeral scanner, explicit record action, outcome/status/strength/freshness filters, watchlist badges, candidate detail with backend chart and lineage, a rejection ledger, and a thesis board with review, monitoring and version history. The browser only renders returned canonical values. The existing local watchlist stays browser-local and holds instrument IDs, not trade intentions.

## Limits and next phase

Only Binance Pilot 5 public daily spot bars are live validated. Daily bars do not prove intraday breakout quality, liquidity sweeps, execution feasibility or institutional flows. `EVENT_RISK` requires an owner decision until a verified event feed exists. The pilot state can be `insufficient_data` when daily data is stale; no `VALID` status may be inferred from that state. There is no calibrated probability, backtested edge, portfolio sizing, broker write, or execution surface. Phase 6 can consume structured volatility, drawdown, regime, quality and invalidation evidence without treating `VALID` as permission to deploy capital.
