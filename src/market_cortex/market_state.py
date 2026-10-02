"""Explainable rule-based market-state vector for an explicitly named universe."""

from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, time as daytime, timezone
from pathlib import Path
from statistics import mean
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .alignment import compare
from .breadth import BreadthSnapshot, calculate_breadth
from .contracts import utc
from .features import AnalyticalSeries, FeatureEngine, FeatureRequest, FeatureSeries, _digest
from .identity import IdentityRegistry, IdentityError
from .storage import PostgresCatalog


PILOT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
STATE_RULE_VERSION = "market_state_rules_v1"
REGIME_RULE_VERSION = "regime_rules_v1"
STATE_CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class MarketStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    universe_id: str = "binance_pilot_5"
    symbols: tuple[str, ...] = PILOT_SYMBOLS
    history_start: date
    evaluation_date: date
    as_of: datetime
    manifest_id: UUID | None = None
    provider_id: str = "binance"
    adjustment_basis: str = "raw"

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def valid_request(self) -> "MarketStateRequest":
        if (not self.universe_id or not self.symbols or len(set(self.symbols)) != len(self.symbols) or
            self.history_start > self.evaluation_date or
            (self.evaluation_date - self.history_start).days > 5000 or
            self.provider_id != "binance" and self.universe_id == "binance_pilot_5"):
            raise ValueError("INVALID_MARKET_STATE_REQUEST")
        if self.universe_id == "binance_pilot_5" and self.symbols != PILOT_SYMBOLS:
            raise ValueError("PILOT_UNIVERSE_MEMBERSHIP_MISMATCH")
        return self


class MarketStateDimension(BaseModel):
    name: str
    category: str
    metrics: dict[str, float | int | None]
    evidence_refs: list[str]
    scope: str
    timeframe: str = "P1D"
    source_manifest_id: UUID
    rule_version: str = STATE_RULE_VERSION
    rule_code_hash: str = STATE_CODE_HASH
    eligible_members: int
    total_members: int
    freshness: str
    unknown_reason: str | None = None


class RegimeState(BaseModel):
    category: str
    rules_fired: list[str]
    evidence_refs: list[str]
    rule_version: str = REGIME_RULE_VERSION
    rule_code_hash: str = STATE_CODE_HASH
    unknown_reason: str | None = None


class MarketStateSnapshot(BaseModel):
    snapshot_id: str
    request: MarketStateRequest
    source_manifest_id: UUID
    calculation_version: str = STATE_RULE_VERSION
    calculation_code_hash: str = STATE_CODE_HASH
    calculated_at: datetime
    elapsed_ms: float
    universe_members: dict[str, UUID]
    missing_members: list[str]
    dimensions: list[MarketStateDimension]
    regime: RegimeState
    breadth: BreadthSnapshot | None


def classify_regime(dimensions: list[MarketStateDimension]) -> RegimeState:
    by_name = {item.name: item for item in dimensions}
    required = ("trend", "momentum", "volatility", "market_participation", "data_freshness")
    if any(by_name.get(name) is None or by_name[name].category in ("unknown", "insufficient", "stale")
           for name in required):
        return RegimeState(category="insufficient_data", rules_fired=["R0_REQUIRED_DIMENSION_UNAVAILABLE"],
                           evidence_refs=[ref for name in required if name in by_name
                                          for ref in by_name[name].evidence_refs],
                           unknown_reason="REQUIRED_DIMENSION_UNAVAILABLE_OR_STALE")
    if by_name["market_participation"].category != "complete":
        return RegimeState(category="insufficient_data", rules_fired=["R0_INCOMPLETE_UNIVERSE"],
                           evidence_refs=by_name["market_participation"].evidence_refs,
                           unknown_reason="INCOMPLETE_UNIVERSE_COVERAGE")
    trend = by_name["trend"].category
    momentum = by_name["momentum"].category
    volatility = by_name["volatility"].category
    refs = [ref for name in ("trend", "momentum", "volatility") for ref in by_name[name].evidence_refs]
    if trend == "up" and momentum == "positive":
        return RegimeState(category="uptrend_volatile" if volatility == "elevated" else "uptrend_other",
                           rules_fired=["R1_UP_TREND", "R2_POSITIVE_MOMENTUM",
                                        "R3_ELEVATED_VOL" if volatility == "elevated" else "R4_NON_ELEVATED_VOL"],
                           evidence_refs=refs)
    if trend == "down" and momentum == "negative":
        return RegimeState(category="downtrend_volatile" if volatility == "elevated" else "downtrend_other",
                           rules_fired=["R5_DOWN_TREND", "R6_NEGATIVE_MOMENTUM",
                                        "R3_ELEVATED_VOL" if volatility == "elevated" else "R4_NON_ELEVATED_VOL"],
                           evidence_refs=refs)
    return RegimeState(category="mixed", rules_fired=["R7_MIXED_OR_DISAGREEING_DIMENSIONS"], evidence_refs=refs)


class MarketStateEngine:
    def __init__(self, catalog: PostgresCatalog):
        self.catalog = catalog
        self.features = FeatureEngine(catalog)

    def compute(self, request: MarketStateRequest) -> MarketStateSnapshot:
        started = time.perf_counter()
        identities, mappings = self.catalog.load_identity()
        registry = IdentityRegistry(identities, mappings)
        loaded: dict[str, AnalyticalSeries] = {}
        missing_symbols = []
        at = datetime.combine(request.evaluation_date, daytime.min, timezone.utc)
        pinned = request.manifest_id or self.catalog.head()
        if pinned is None:
            raise LookupError("DATASET_EMPTY")
        for symbol in request.symbols:
            try:
                instrument = registry.resolve(provider_id=request.provider_id,
                                              identifier_type="exchange_pair", identifier_value=symbol,
                                              at=at, known_at=request.as_of)
            except IdentityError:
                missing_symbols.append(symbol)
                continue
            loaded[symbol] = self.features.load(instrument_id=instrument.instrument_id,
                                                start_date=request.history_start,
                                                end_date=request.evaluation_date,
                                                as_of=request.as_of, manifest_id=pinned,
                                                provider_id=request.provider_id,
                                                adjustment_basis=request.adjustment_basis)
        total = len(request.symbols)
        dimensions: list[MarketStateDimension] = []
        feature_cache: dict[tuple[str, str, tuple[tuple[str, int | float], ...]], FeatureSeries] = {}

        def feature(symbol: str, name: str, **params: int | float) -> FeatureSeries | None:
            if symbol not in loaded:
                return None
            key = (symbol, name, tuple(sorted(params.items())))
            if key not in feature_cache:
                member = loaded[symbol]
                feature_cache[key] = self.features.calculate(FeatureRequest(
                    instrument_id=member.instrument.instrument_id, feature=name,
                    start_date=request.history_start, end_date=request.evaluation_date,
                    as_of=request.as_of, manifest_id=pinned, provider_id=request.provider_id,
                    adjustment_basis=request.adjustment_basis, parameters=params), member)
            return feature_cache[key]

        def last(result: FeatureSeries | None) -> float | None:
            return result.points[-1].value if result and result.points else None

        def refs(*results: FeatureSeries | None) -> list[str]:
            return [item.feature_id for item in results if item is not None]

        def dimension(name: str, category: str, metrics: dict[str, float | int | None],
                      evidence: list[str], *, scope: str | None = None, eligible: int = 1,
                      denominator: int | None = None, freshness: str | None = None,
                      reason: str | None = None) -> None:
            dimensions.append(MarketStateDimension(name=name, category=category, metrics=metrics,
                evidence_refs=evidence, scope=scope or request.universe_id, source_manifest_id=pinned,
                eligible_members=eligible, total_members=total if denominator is None else denominator,
                freshness=freshness or (loaded["BTCUSDT"].freshness_state if "BTCUSDT" in loaded else "no_data"),
                unknown_reason=reason))

        btc = loaded.get("BTCUSDT")
        btc_freshness = btc.freshness_state if btc else "no_data"
        btc_close = float(btc.columns["close"][-1]) if btc and len(btc.dates) and btc.bars[-1] else None
        ema20, sma50, slope20 = feature("BTCUSDT", "ema", period=20), feature("BTCUSDT", "sma", period=50), feature("BTCUSDT", "ma_slope", period=20, slope_period=5)
        e20, s50, slope = last(ema20), last(sma50), last(slope20)
        trend_category = ("unknown" if None in (btc_close, e20, s50, slope) else
                          "up" if btc_close > e20 > s50 and slope > 0 else
                          "down" if btc_close < e20 < s50 and slope < 0 else "mixed")
        dimension("trend", trend_category, {"btc_close": btc_close, "ema20": e20, "sma50": s50,
                                            "sma20_slope_5_pct": slope}, refs(ema20, sma50, slope20),
                  scope="BTCUSDT", eligible=1 if btc else 0, denominator=1, freshness=btc_freshness,
                  reason="INSUFFICIENT_HISTORY_OR_MISSING_BTC" if trend_category == "unknown" else None)

        rsi, histogram = feature("BTCUSDT", "rsi", period=14), feature("BTCUSDT", "macd_histogram")
        rsi_value, hist_value = last(rsi), last(histogram)
        momentum_category = ("unknown" if None in (rsi_value, hist_value) else
                             "positive" if rsi_value > 55 and hist_value > 0 else
                             "negative" if rsi_value < 45 and hist_value < 0 else "mixed")
        dimension("momentum", momentum_category, {"rsi14": rsi_value, "macd_histogram": hist_value},
                  refs(rsi, histogram), scope="BTCUSDT", eligible=1 if btc else 0,
                  denominator=1, freshness=btc_freshness,
                  reason="INSUFFICIENT_HISTORY_OR_MISSING_BTC" if momentum_category == "unknown" else None)

        volatility, percentile, atr = (feature("BTCUSDT", "annualized_volatility", period=20),
                                      feature("BTCUSDT", "volatility_percentile", period=20, rank_window=90),
                                      feature("BTCUSDT", "atr", period=14))
        vol_value, rank_value, atr_value = last(volatility), last(percentile), last(atr)
        volatility_category = ("unknown" if rank_value is None else "elevated" if rank_value >= 80 else
                               "subdued" if rank_value <= 20 else "middle")
        dimension("volatility", volatility_category,
                  {"annualized_log_return_vol20": vol_value, "volatility_rank90": rank_value, "atr14": atr_value},
                  refs(volatility, percentile, atr), scope="BTCUSDT", eligible=1 if btc else 0,
                  denominator=1, freshness=btc_freshness,
                  reason="INSUFFICIENT_HISTORY_OR_MISSING_BTC" if volatility_category == "unknown" else None)

        relvol = feature("BTCUSDT", "relative_volume", period=20)
        rv = last(relvol)
        volume_category = "unknown" if rv is None else "elevated" if rv >= 1.2 else "thin" if rv <= 0.8 else "typical"
        dimension("volume_proxy", volume_category, {"btc_relative_volume20": rv}, refs(relvol),
                  scope="BTCUSDT; traded base-asset volume, not order-book liquidity",
                  eligible=1 if btc else 0, denominator=1, freshness=btc_freshness,
                  reason="VOLUME_UNAVAILABLE" if rv is None else None)

        breadth: BreadthSnapshot | None = None
        if loaded and all(request.evaluation_date in member.dates for member in loaded.values()):
            breadth = calculate_breadth(self.features, request.universe_id, loaded, request.evaluation_date, period=20)
        observed = sum(member.bars[-1] is not None for member in loaded.values() if member.bars)
        participation_category = "complete" if observed == total else "partial" if observed else "insufficient"
        dimension("market_participation", participation_category,
                  {"observed_members": observed, "expected_members": total,
                   "fraction": observed / total}, [breadth.snapshot_id] if breadth else [],
                  eligible=observed, freshness="mixed" if len({item.freshness_state for item in loaded.values()}) > 1 else btc_freshness,
                  reason="NO_VISIBLE_BAR_FOR_EVALUATION_SESSION" if observed == 0 else None)

        breadth_category = "unknown"
        if breadth and breadth.above_sma.eligible >= max(3, total - 1) and breadth.positive_lookback.eligible >= max(3, total - 1):
            above, positive = breadth.above_sma.percentage, breadth.positive_lookback.percentage
            breadth_category = "broad_positive" if above >= 80 and positive >= 80 else "broad_negative" if above <= 20 and positive <= 20 else "mixed"
        dimension("breadth", breadth_category,
                  {"above_sma20_pct": breadth.above_sma.percentage if breadth else None,
                   "positive_return20_pct": breadth.positive_lookback.percentage if breadth else None,
                   "new_high20_pct": breadth.new_high.percentage if breadth else None,
                   "new_low20_pct": breadth.new_low.percentage if breadth else None},
                  [breadth.snapshot_id] if breadth else [], eligible=breadth.observed_members if breadth else 0,
                  reason="INSUFFICIENT_UNIVERSE_COVERAGE" if breadth_category == "unknown" else None)

        strength_values, correlations, comparison_refs = [], [], []
        if btc:
            for symbol, member in loaded.items():
                if symbol == "BTCUSDT": continue
                strength = compare(member, btc, kind="relative_strength", window=20)
                correlation = compare(member, btc, kind="correlation", window=60)
                comparison_refs.extend((strength.result_id, correlation.result_id))
                if strength.points and strength.points[-1].value is not None:
                    strength_values.append(strength.points[-1].value)
                if correlation.points and correlation.points[-1].value is not None:
                    correlations.append(correlation.points[-1].value)
        strength_category = "unknown" if len(strength_values) < 3 else "alts_outperforming" if mean(strength_values) > 0 else "btc_outperforming"
        dimension("relative_strength", strength_category,
                  {"alt_vs_btc_mean_return_ratio20": mean(strength_values) if strength_values else None,
                   "alt_count": len(strength_values)}, comparison_refs[::2],
                  eligible=len(strength_values), denominator=total - 1,
                  reason="INSUFFICIENT_ALIGNED_ALT_HISTORY" if strength_category == "unknown" else None)
        correlation_category = "unknown" if len(correlations) < 3 else "high" if mean(correlations) >= 0.75 else "low" if mean(correlations) < 0.3 else "middle"
        dimension("correlation_state", correlation_category,
                  {"alt_btc_mean_pearson60": mean(correlations) if correlations else None,
                   "pair_count": len(correlations), "window_returns": 60}, comparison_refs[1::2],
                  eligible=len(correlations), denominator=total - 1,
                  reason="INSUFFICIENT_ALIGNED_ALT_HISTORY" if correlation_category == "unknown" else None)
        appetite_category = "unknown" if strength_category == "unknown" or not breadth or breadth.positive_lookback.eligible < 4 else (
            "risk_on_proxy" if mean(strength_values) > 0 and breadth.positive_lookback.positive >= 4 else
            "risk_off_proxy" if mean(strength_values) < 0 and breadth.positive_lookback.positive <= 1 else "mixed")
        dimension("risk_appetite_proxy", appetite_category,
                  {"alt_vs_btc_mean20": mean(strength_values) if strength_values else None,
                   "universe_positive20": breadth.positive_lookback.positive if breadth else None},
                  comparison_refs[::2] + ([breadth.snapshot_id] if breadth else []),
                  eligible=len(strength_values), denominator=total - 1,
                  reason="INSUFFICIENT_PROXY_COVERAGE" if appetite_category == "unknown" else None)

        current_count = sum(member.freshness_state == "current" for member in loaded.values())
        freshness_category = "current" if current_count == total else "stale" if current_count < total else "unknown"
        dimension("data_freshness", freshness_category,
                  {"current_members": current_count, "total_members": total},
                  [str(member.bars[-1].envelope.observation_id) for member in loaded.values()
                   if member.bars and member.bars[-1] is not None], eligible=current_count,
                  freshness=freshness_category, reason="ONE_OR_MORE_MEMBERS_NOT_CURRENT" if freshness_category != "current" else None)
        unknown_count = sum(item.category in ("unknown", "insufficient") for item in dimensions)
        noncurrent_count = sum(item.freshness_state != "current" for item in loaded.values())
        dimension("uncertainty", "elevated" if unknown_count or missing_symbols or noncurrent_count else "bounded",
                  {"unknown_dimensions": unknown_count, "missing_members": len(missing_symbols),
                   "noncurrent_members": noncurrent_count},
                  [item.evidence_refs[0] for item in dimensions if item.category == "unknown" and item.evidence_refs],
                  eligible=total - len(missing_symbols),
                  reason="UNKNOWN_DIMENSIONS_OR_MEMBERS" if unknown_count or missing_symbols else
                  "NONCURRENT_MEMBER" if noncurrent_count else None)

        regime = classify_regime(dimensions)
        identity = {"request": request.model_dump(mode="json"), "manifest": str(pinned),
                    "members": {name: str(item.instrument.instrument_id) for name, item in loaded.items()},
                    "dimensions": [item.model_dump(mode="json") for item in dimensions],
                    "regime": regime.model_dump(mode="json"), "breadth_id": breadth.snapshot_id if breadth else None}
        return MarketStateSnapshot(snapshot_id=_digest(identity), request=request,
                                   source_manifest_id=pinned, calculated_at=datetime.now(timezone.utc),
                                   elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                                   universe_members={name: item.instrument.instrument_id for name, item in loaded.items()},
                                   missing_members=missing_symbols, dimensions=dimensions,
                                   regime=regime, breadth=breadth)
