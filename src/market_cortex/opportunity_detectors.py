"""Pure, versioned daily-bar research detector rules. No trade decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .opportunity_contracts import Condition, DetectorDefinition


@dataclass(frozen=True)
class Rule:
    metric: str
    operator: Literal["gt", "gte", "lt", "lte", "eq", "between"]
    threshold: float | tuple[float, float]
    description: str


@dataclass(frozen=True)
class Detector:
    definition: DetectorDefinition
    bias: Literal["bullish", "bearish", "neutral"]
    triggers: tuple[Rule, ...]
    confirmations: tuple[Rule, ...]
    invalidations: tuple[Rule, ...]
    rejections: tuple[Rule, ...]


def _rule(metric: str, operator: str, threshold: float | tuple[float, float], description: str) -> Rule:
    return Rule(metric, operator, threshold, description)


def _detector(name: str, description: str, minimum: int, bias: str,
              triggers: tuple[Rule, ...], confirmations: tuple[Rule, ...],
              invalidations: tuple[Rule, ...], rejections: tuple[Rule, ...],
              *, policy: str = "Require complete source coverage; market-state uncertainty prevents VALID") -> Detector:
    metrics = {rule.metric for rule in triggers + confirmations + invalidations + rejections}
    phase2 = {"return20": "rolling_return(period=20)", "return5": "rolling_return(period=5)",
        "rsi14": "rsi(period=14)", "macd_histogram": "macd_histogram",
        "ma_alignment": "ma_alignment(fast=20,slow=50)",
        "relative_volume": "relative_volume(period=20)",
        "price_vs_ma20": "price_vs_ma(period=20)",
        "price_vs_ma50": "price_vs_ma(period=50)",
        "ma_slope20": "ma_slope(period=20,slope_period=5)",
        "volatility_percentile": "volatility_percentile(period=20,rank_window=90)",
        "bollinger_bandwidth": "bollinger_bandwidth(period=20)",
        "annualized_volatility": "annualized_volatility(period=20)",
        "drawdown": "drawdown", "close": "raw_close",
        "prior_high20": "derived_prior_high(period=20)",
        "relative_strength_btc20": "aligned_relative_strength(reference=BTCUSDT,window=20)"}
    features = sorted(phase2[metric] for metric in metrics)
    definition = DetectorDefinition(detector_id=name, version="1.0.0", description=description,
        required_features=features, minimum_history=minimum, market_state_policy=policy,
        trigger_rules=[item.description for item in triggers],
        confirmation_rules=[item.description for item in confirmations],
        invalidation_rules=[item.description for item in invalidations],
        rejection_rules=[item.description for item in rejections])
    return Detector(definition, bias, triggers, confirmations, invalidations, rejections)


DETECTORS: dict[str, Detector] = {item.definition.detector_id: item for item in (
    _detector("momentum", "Positive medium-term return with non-extreme RSI", 55, "bullish",
        (_rule("return20", "gt", .05, "20-session return exceeds 5%"),
         _rule("rsi14", "between", (55, 75), "RSI14 is between 55 and 75")),
        (_rule("macd_histogram", "gt", 0, "MACD histogram is positive"),
         _rule("ma_alignment", "gt", 0, "SMA20 is above SMA50")),
        (_rule("return20", "lt", 0, "20-session return turns negative"),),
        (_rule("rsi14", "gt", 85, "RSI14 exceeds 85; extension risk"),)),
    _detector("breakout", "Daily close above prior 20-session high; close-only evidence", 55, "bullish",
        (_rule("close", "gt", 0, "Close exceeds prior 20-session high; dynamic threshold"),),
        (_rule("relative_volume", "gte", 1.2, "Relative volume20 is at least 1.2"),
         _rule("ma_alignment", "gt", 0, "SMA20 is above SMA50")),
        (_rule("close", "lt", 0, "Close falls below prior breakout level; dynamic threshold"),),
        (_rule("relative_volume", "lt", .8, "Thin relative volume raises false-breakout risk"),)),
    _detector("pullback", "Negative short return inside a still-positive longer trend", 55, "bullish",
        (_rule("ma_alignment", "gt", 0, "SMA20 remains above SMA50"),
         _rule("return5", "lt", 0, "Five-session return is negative")),
        (_rule("price_vs_ma50", "gte", 0, "Close remains at or above SMA50"),
         _rule("rsi14", "between", (40, 60), "RSI14 has cooled to 40–60")),
        (_rule("price_vs_ma50", "lt", -.03, "Close falls over 3% below SMA50"),),
        (_rule("return20", "lt", -.10, "20-session return below -10% suggests reversal"),)),
    _detector("trend_continuation", "Aligned moving averages, positive slope and momentum", 55, "bullish",
        (_rule("ma_alignment", "gt", 0, "SMA20 is above SMA50"),
         _rule("price_vs_ma20", "gt", 0, "Close is above SMA20")),
        (_rule("ma_slope20", "gt", 0, "SMA20 slope over five sessions is positive"),
         _rule("macd_histogram", "gt", 0, "MACD histogram confirms trend")),
        (_rule("ma_alignment", "lt", 0, "SMA20 falls below SMA50"),),
        (_rule("price_vs_ma20", "lt", -.08, "Close is more than 8% below SMA20"),)),
    _detector("relative_strength", "Alt-asset performance relative to BTC over aligned 20 sessions", 25, "bullish",
        (_rule("relative_strength_btc20", "gt", .03, "20-session relative outperformance exceeds 3%"),),
        (_rule("return20", "gt", 0, "Absolute 20-session return is positive"),),
        (_rule("relative_strength_btc20", "lt", 0, "Relative strength reverses below zero"),),
        (_rule("return20", "lt", -.10, "Absolute return falls below -10%"),),
        policy="Require aligned same-session BTC reference; BTC itself is unsupported"),
    _detector("volatility_expansion", "High realized-volatility rank with widening bands", 115, "neutral",
        (_rule("volatility_percentile", "gte", 75, "Volatility rank90 reaches 75th percentile"),),
        (_rule("bollinger_bandwidth", "gte", .10, "Bollinger bandwidth is at least 10%"),
         _rule("relative_volume", "gte", 1.2, "Relative volume20 is at least 1.2")),
        (_rule("volatility_percentile", "lt", 40, "Volatility rank falls below 40"),),
        (_rule("relative_volume", "lt", .8, "Low volume weakens expansion evidence"),)),
    _detector("mean_reversion", "Large deviation below SMA20, subject to downtrend veto", 115, "bullish",
        (_rule("price_vs_ma20", "lte", -.08, "Close is at least 8% below SMA20"),),
        (_rule("rsi14", "lte", 35, "RSI14 is at most 35"),
         _rule("volatility_percentile", "lt", 80, "Volatility rank is below 80")),
        (_rule("price_vs_ma20", "gte", 0, "Deviation has reverted to SMA20"),),
        (_rule("ma_alignment", "lt", 0, "Downtrend veto: SMA20 below SMA50"),)),
    _detector("swing_trend", "Multi-session positive trend with bounded volatility and drawdown", 55, "bullish",
        (_rule("return20", "gte", .05, "20-session return at least 5%"),
         _rule("ma_alignment", "gt", 0, "SMA20 above SMA50")),
        (_rule("annualized_volatility", "lt", .8, "Annualized volatility below 80%"),
         _rule("drawdown", "gt", -.25, "Current drawdown less than 25%")),
        (_rule("ma_alignment", "lt", 0, "SMA20 falls below SMA50"),),
        (_rule("drawdown", "lte", -.25, "Current drawdown reaches 25%"),)),
)}

UNSUPPORTED = {
    "liquidity_sweep": "Daily OHLCV cannot establish order-book liquidity sweeps",
    "event_driven": "No timestamped, verified event feed is available",
    "accumulation_proxy": "No validated flow or inventory evidence is available",
}


def definitions() -> list[DetectorDefinition]:
    return [item.definition for item in DETECTORS.values()] + [
        DetectorDefinition(detector_id=name, version="0.0.0", description=reason,
            required_features=[], minimum_history=0, market_state_policy="unsupported",
            trigger_rules=[], confirmation_rules=[], invalidation_rules=[], rejection_rules=[],
            enabled=False, unsupported_reason=reason)
        for name, reason in UNSUPPORTED.items()]


def condition(rule: Rule, kind: str, value: float | None, evidence_id: str,
              *, dynamic_threshold: float | None = None) -> Condition:
    threshold = dynamic_threshold if dynamic_threshold is not None else rule.threshold
    met = None if value is None or threshold is None else (
        value > threshold if rule.operator == "gt" else
        value >= threshold if rule.operator == "gte" else
        value < threshold if rule.operator == "lt" else
        value <= threshold if rule.operator == "lte" else
        value == threshold if rule.operator == "eq" else
        threshold[0] <= value <= threshold[1])
    return Condition(condition_id=f"{kind}:{rule.metric}:{rule.operator}", kind=kind,
        metric=rule.metric, operator=rule.operator,
        threshold=list(threshold) if isinstance(threshold, tuple) else threshold,
        observed=value, met=met, evidence_ids=[evidence_id] if evidence_id else [],
        description=rule.description)
