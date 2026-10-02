"""Versioned feature registry and manifest-pinned deterministic daily series."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .calendar import CalendarMissing, SessionCalendar
from . import indicators
from .contracts import Bar, Instrument, utc
from .indicators import calculate
from .quality import freshness
from .storage import PostgresCatalog


FEATURE_VERSION = "1.0.0"
CALCULATION_VERSION = "daily_float64_v1"
CALCULATION_CODE_HASH = hashlib.sha256(
    Path(__file__).read_bytes() + Path(indicators.__file__).read_bytes()).hexdigest()


class FeatureDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str = FEATURE_VERSION
    calculation_version: str = CALCULATION_VERSION
    calculation_code_hash: str = CALCULATION_CODE_HASH
    description: str
    required_inputs: tuple[str, ...]
    parameter_defaults: dict[str, int | float]
    min_history: str
    default_min_history: int
    output_type: str = "nullable_float64"
    unit: str
    supported_intervals: tuple[str, ...] = ("P1D",)


_SPECS: dict[str, tuple[str, str, tuple[str, ...], dict[str, int | float], str]] = {
    "arithmetic_return": ("Adjacent session close-to-close return", "fraction", ("close",), {}, "2 bars"),
    "log_return": ("Adjacent session natural-log close return", "log_fraction", ("close",), {}, "2 bars"),
    "cumulative_return": ("Return since first uninterrupted visible close in window", "fraction", ("close",), {}, "1 bar"),
    "rolling_return": ("Close return over period complete session steps", "fraction", ("close",), {"period": 20}, "period + 1 bars"),
    "gap_return": ("Current open versus previous session close", "fraction", ("open", "close"), {}, "2 bars"),
    "sma": ("Simple moving average of closes", "quote_price", ("close",), {"period": 20}, "period bars"),
    "ema": ("EMA seeded by first complete simple average", "quote_price", ("close",), {"period": 20}, "period bars"),
    "price_vs_ma": ("Close divided by SMA minus one", "percent", ("close",), {"period": 20}, "period bars"),
    "ma_slope": ("SMA percentage change over slope_period sessions", "percent", ("close",), {"period": 20, "slope_period": 5}, "period + slope_period bars"),
    "ma_alignment": ("Sign of fast SMA minus slow SMA", "direction", ("close",), {"fast": 20, "slow": 50}, "slow bars"),
    "higher_high_lower_low": ("Compare adjacent nonoverlapping rolling high/low windows", "direction", ("high", "low"), {"period": 10}, "2 * period bars"),
    "trend_persistence": ("Positive minus negative return share over period", "fraction", ("close",), {"period": 20}, "period + 1 bars"),
    "trend_strength": ("Fast-minus-slow SMA divided by Wilder ATR14", "atr_multiple", ("close", "high", "low"), {"fast": 20, "slow": 50}, "max(slow,14) bars"),
    "rsi": ("Wilder RSI; flat run is 50", "index_0_100", ("close",), {"period": 14}, "period + 1 bars"),
    "roc": ("Rate of change over period, percentage", "percent", ("close",), {"period": 20}, "period + 1 bars"),
    "macd": ("Fast EMA minus slow EMA", "quote_price", ("close",), {"fast": 12, "slow": 26, "signal": 9}, "slow bars"),
    "macd_signal": ("EMA of MACD line", "quote_price", ("close",), {"fast": 12, "slow": 26, "signal": 9}, "slow + signal - 1 bars"),
    "macd_histogram": ("MACD minus signal", "quote_price", ("close",), {"fast": 12, "slow": 26, "signal": 9}, "slow + signal - 1 bars"),
    "rolling_std": ("Sample standard deviation of arithmetic returns", "fraction", ("close",), {"period": 20}, "period + 1 bars"),
    "annualized_volatility": ("Sample std of log returns times square root annualization", "annual_fraction", ("close",), {"period": 20}, "period + 1 bars"),
    "true_range": ("Maximum high-low and prior-close gaps", "quote_price", ("high", "low", "close"), {}, "1 bar"),
    "atr": ("Wilder smoothed true range", "quote_price", ("high", "low", "close"), {"period": 14}, "period bars"),
    "bollinger_middle": ("SMA of closes", "quote_price", ("close",), {"period": 20, "deviations": 2.0}, "period bars"),
    "bollinger_upper": ("SMA plus population standard deviations", "quote_price", ("close",), {"period": 20, "deviations": 2.0}, "period bars"),
    "bollinger_lower": ("SMA minus population standard deviations", "quote_price", ("close",), {"period": 20, "deviations": 2.0}, "period bars"),
    "bollinger_bandwidth": ("Upper minus lower divided by middle", "percent", ("close",), {"period": 20, "deviations": 2.0}, "period bars"),
    "rolling_high_low_range": ("Highest high minus lowest low divided by lowest low", "percent", ("high", "low"), {"period": 20}, "period bars"),
    "volatility_percentile": ("Inclusive empirical rank of annualized volatility", "percentile_0_100", ("close",), {"period": 20, "rank_window": 90}, "period + rank_window bars"),
    "average_volume": ("Simple average source volume", "source_volume", ("volume",), {"period": 20}, "period bars"),
    "relative_volume": ("Current source volume over rolling average", "ratio", ("volume",), {"period": 20}, "period bars"),
    "volume_change": ("Adjacent source volume ratio minus one", "fraction", ("volume",), {}, "2 bars"),
    "volume_zscore": ("Volume minus mean over sample standard deviation", "zscore", ("volume",), {"period": 20}, "period bars"),
    "price_volume_confirmation": ("Return sign multiplied by relative volume", "signed_ratio", ("close", "volume"), {"period": 20}, "period bars"),
    "running_peak": ("Highest close since uninterrupted window start", "quote_price", ("close",), {}, "1 bar"),
    "drawdown": ("Close divided by running peak minus one", "fraction", ("close",), {}, "1 bar"),
    "maximum_drawdown": ("Worst drawdown since uninterrupted window start", "fraction", ("close",), {}, "1 bar"),
    "drawdown_duration": ("Completed sessions since most recent close peak", "sessions", ("close",), {}, "1 bar"),
    "recovery_state": ("One at a new/equal close peak, else zero", "boolean_number", ("close",), {}, "1 bar"),
}

def required_history(name: str, params: dict[str, int | float]) -> int:
    period = int(params.get("period", 20))
    if name in ("arithmetic_return", "log_return", "gap_return", "volume_change"):
        return 2
    if name in ("rolling_return", "roc", "rsi", "trend_persistence", "rolling_std", "annualized_volatility"):
        return period + 1
    if name == "volatility_percentile":
        return period + int(params["rank_window"])
    if name == "ma_slope":
        return period + int(params["slope_period"])
    if name == "higher_high_lower_low":
        return 2 * period
    if name in ("macd_signal", "macd_histogram"):
        return int(params["slow"]) + int(params["signal"]) - 1
    if name == "macd":
        return int(params["slow"])
    if name in ("ma_alignment", "trend_strength"):
        return max(int(params["slow"]), 14 if name == "trend_strength" else 1)
    if name in ("cumulative_return", "true_range", "running_peak", "drawdown",
                "maximum_drawdown", "drawdown_duration", "recovery_state"):
        return 1
    return period


REGISTRY: dict[str, FeatureDefinition] = {
    name: FeatureDefinition(name=name, description=description, unit=unit,
                            required_inputs=inputs, parameter_defaults=params, min_history=history,
                            default_min_history=required_history(name, params))
    for name, (description, unit, inputs, params, history) in _SPECS.items()
}


def definitions() -> list[FeatureDefinition]:
    return list(REGISTRY.values())


def resolve_parameters(name: str, supplied: dict[str, int | float], calendar: SessionCalendar) -> dict[str, int | float]:
    if name not in REGISTRY:
        raise ValueError("UNKNOWN_FEATURE")
    params = dict(REGISTRY[name].parameter_defaults)
    allowed = set(params) | ({"annualization"} if name in ("annualized_volatility", "volatility_percentile") else set())
    if set(supplied) - allowed:
        raise ValueError("UNKNOWN_FEATURE_PARAMETER")
    params.update(supplied)
    if name in ("annualized_volatility", "volatility_percentile"):
        params.setdefault("annualization", 365 if calendar.venue.session_kind == "24x7" else 252)
    for key in ("period", "fast", "slow", "signal", "rank_window", "slope_period", "annualization"):
        if key in params:
            value = params[key]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
                raise ValueError("INVALID_FEATURE_PARAMETER")
    if "period" in params and name in ("rsi", "rolling_std", "annualized_volatility", "volatility_percentile", "volume_zscore", "bollinger_middle", "bollinger_upper", "bollinger_lower", "bollinger_bandwidth") and params["period"] < 2:
        raise ValueError("INVALID_FEATURE_PARAMETER")
    if "rank_window" in params and params["rank_window"] < 2:
        raise ValueError("INVALID_FEATURE_PARAMETER")
    if "fast" in params and params["fast"] >= params["slow"]:
        raise ValueError("INVALID_FEATURE_PARAMETER")
    if "deviations" in params:
        value = params["deviations"]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 < value <= 10:
            raise ValueError("INVALID_FEATURE_PARAMETER")
    return params


class FeatureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: UUID
    feature: str
    feature_version: str = FEATURE_VERSION
    start_date: date
    end_date: date
    as_of: datetime
    manifest_id: UUID | None = None
    provider_id: str | None = None
    adjustment_basis: str = "raw"
    interval: str = "P1D"
    parameters: dict[str, int | float] = Field(default_factory=dict)

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def validate_request(self) -> "FeatureRequest":
        if self.start_date > self.end_date or (self.end_date - self.start_date).days > 5000:
            raise ValueError("INVALID_FEATURE_WINDOW")
        if self.interval != "P1D" or self.feature_version != FEATURE_VERSION:
            raise ValueError("UNSUPPORTED_FEATURE_VERSION_OR_INTERVAL")
        if self.feature not in REGISTRY:
            raise ValueError("UNKNOWN_FEATURE")
        return self


class FeaturePoint(BaseModel):
    session_date: date
    value: float | None
    observation_id: UUID | None
    source_batch_id: UUID | None
    available_at: datetime | None
    input_quality: str | None
    reason: str | None = None


class FeatureSeries(BaseModel):
    feature_id: str
    definition: FeatureDefinition
    calculation_code_hash: str
    required_history: int
    request: FeatureRequest
    source_manifest_id: UUID | None
    provider_id: str | None
    calendar_id: str
    calendar_version: str
    venue_id: str
    currency: str
    resolved_parameters: dict[str, int | float]
    source_observation_ids: list[UUID]
    source_batch_ids: list[UUID]
    selection_policy: str = "single_provider_or_reject_v1"
    expected_sessions: int
    eligible_sessions: int
    observed_sessions: int
    computed_points: int
    missing_sessions: list[date]
    ineligible_sessions: list[date]
    freshness: str
    calculated_at: datetime
    elapsed_ms: float
    points: list[FeaturePoint]


@dataclass(frozen=True)
class AnalyticalSeries:
    instrument: Instrument
    calendar: SessionCalendar
    manifest_id: UUID | None
    as_of: datetime
    provider_id: str | None
    adjustment_basis: str
    dates: tuple[date, ...]
    bars: tuple[Bar | None, ...]
    columns: dict[str, np.ndarray]
    freshness_state: str

    @property
    def missing_dates(self) -> list[date]:
        return [day for day, bar in zip(self.dates, self.bars) if bar is None and self.eligible(day)]

    @property
    def ineligible_dates(self) -> list[date]:
        return [day for day in self.dates if not self.eligible(day)]

    def eligible(self, day: date) -> bool:
        session_open = self.calendar.session(day).open_at
        return (self.instrument.valid_from <= session_open and
                (self.instrument.valid_to is None or session_open < self.instrument.valid_to))


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class FeatureEngine:
    def __init__(self, catalog: PostgresCatalog):
        self.catalog = catalog

    def load(self, *, instrument_id: UUID, start_date: date, end_date: date,
             as_of: datetime, manifest_id: UUID | None = None, provider_id: str | None = None,
             adjustment_basis: str = "raw") -> AnalyticalSeries:
        if start_date > end_date or (end_date - start_date).days > 5000:
            raise ValueError("INVALID_FEATURE_WINDOW")
        as_of = utc(as_of)
        instruments, _ = self.catalog.load_identity()
        instrument = next((item for item in instruments if item.instrument_id == instrument_id), None)
        if instrument is None:
            raise LookupError("INSTRUMENT_NOT_FOUND")
        start = datetime.combine(start_date - timedelta(days=2), daytime.min, timezone.utc)
        end = datetime.combine(end_date + timedelta(days=2), daytime.min, timezone.utc)
        calendar = self.catalog.load_calendar(instrument.primary_venue_id, start, end)
        expected = tuple(calendar.expected_dates(start_date, end_date))
        pinned, records = self.catalog.bars(instrument_id=instrument_id, start=start, end=end, as_of=as_of,
                                            manifest_id=manifest_id, provider_id=provider_id,
                                            adjustment_basis=adjustment_basis)
        if pinned is None:
            raise LookupError("DATASET_EMPTY")
        records = [bar for bar in records if bar.interval == "P1D" and
                   start_date <= bar.session_date <= end_date]
        providers = {bar.envelope.provider_id for bar in records}
        if provider_id is None and len(providers) > 1:
            raise ValueError("PROVIDER_SELECTION_REQUIRED")
        selected_provider = provider_id or (next(iter(providers)) if providers else None)
        by_date: dict[date, Bar] = {}
        for bar in records:
            if bar.session_date in by_date:
                raise ValueError("CONFLICTING_VISIBLE_BAR")
            by_date[bar.session_date] = bar
        bars = tuple(by_date.get(day) if instrument.valid_from <= calendar.session(day).open_at and
                     (instrument.valid_to is None or calendar.session(day).open_at < instrument.valid_to)
                     else None for day in expected)
        columns = {field: np.array([float(getattr(bar, field)) if bar is not None and
                                    getattr(bar, field) is not None else np.nan for bar in bars], dtype=np.float64)
                   for field in ("open", "high", "low", "close", "volume")}
        latest = next((bar for bar in reversed(bars) if bar is not None), None)
        health = freshness(latest=latest, as_of=as_of, calendar=calendar)
        return AnalyticalSeries(instrument, calendar, pinned, as_of, selected_provider, adjustment_basis,
                                expected, bars, columns, health)

    def calculate(self, request: FeatureRequest, loaded: AnalyticalSeries | None = None) -> FeatureSeries:
        started = time.perf_counter()
        series = loaded or self.load(instrument_id=request.instrument_id, start_date=request.start_date,
                                     end_date=request.end_date, as_of=request.as_of,
                                     manifest_id=request.manifest_id, provider_id=request.provider_id,
                                     adjustment_basis=request.adjustment_basis)
        if (series.instrument.instrument_id != request.instrument_id or series.as_of != request.as_of or
            series.adjustment_basis != request.adjustment_basis or
            request.manifest_id is not None and series.manifest_id != request.manifest_id or
            request.provider_id is not None and series.provider_id != request.provider_id or
            series.dates != tuple(series.calendar.expected_dates(request.start_date, request.end_date))):
            raise ValueError("ANALYTICAL_SERIES_REQUEST_MISMATCH")
        params = resolve_parameters(request.feature, request.parameters, series.calendar)
        output = calculate(request.feature, series.columns, params)
        definition = REGISTRY[request.feature]
        points = []
        for day, bar, value in zip(series.dates, series.bars, output):
            valid = math.isfinite(float(value))
            if not series.eligible(day):
                reason = "INSTRUMENT_NOT_VALID"
                valid = False
            elif bar is None:
                reason = "NO_VISIBLE_VALID_BAR"
            elif not valid and any(getattr(bar, key) is None for key in definition.required_inputs):
                reason = "INPUT_UNAVAILABLE"
            elif not valid:
                reason = "INSUFFICIENT_HISTORY_OR_GAP"
            else:
                reason = None
            points.append(FeaturePoint(session_date=day, value=float(value) if valid else None,
                                       observation_id=bar.envelope.observation_id if bar else None,
                                       source_batch_id=bar.envelope.source_batch_id if bar else None,
                                       available_at=bar.envelope.available_at if bar else None,
                                       input_quality=bar.envelope.quality_state if bar else None, reason=reason))
        observation_ids = [bar.envelope.observation_id for bar in series.bars if bar is not None]
        batch_ids = list(dict.fromkeys(bar.envelope.source_batch_id for bar in series.bars if bar is not None))
        identity = {"instrument_id": str(request.instrument_id), "manifest_id": str(series.manifest_id),
                    "provider_id": series.provider_id, "adjustment_basis": request.adjustment_basis,
                    "interval": request.interval, "feature": request.feature, "feature_version": request.feature_version,
                    "calculation_version": CALCULATION_VERSION, "calculation_code_hash": CALCULATION_CODE_HASH,
                    "calendar_id": series.calendar.calendar_id,
                    "calendar_version": series.calendar.version,
                    "expected_dates": list(map(str, series.dates)), "parameters": params,
                    "start_date": str(request.start_date), "end_date": str(request.end_date),
                    "as_of": request.as_of.isoformat(), "observation_ids": list(map(str, observation_ids)),
                    "source_batch_ids": list(map(str, batch_ids)),
                    "values": [point.value for point in points]}
        return FeatureSeries(feature_id=_digest(identity), definition=definition,
                             calculation_code_hash=CALCULATION_CODE_HASH,
                             required_history=required_history(request.feature, params), request=request,
                             source_manifest_id=series.manifest_id, provider_id=series.provider_id,
                             calendar_id=series.calendar.calendar_id, calendar_version=series.calendar.version,
                             venue_id=series.calendar.venue.venue_id, currency=series.instrument.trading_currency,
                             resolved_parameters=params, source_observation_ids=observation_ids,
                             source_batch_ids=batch_ids,
                             expected_sessions=len(series.dates), observed_sessions=len(observation_ids),
                             eligible_sessions=len(series.dates) - len(series.ineligible_dates),
                             computed_points=sum(point.value is not None for point in points),
                             missing_sessions=series.missing_dates,
                             ineligible_sessions=series.ineligible_dates,
                             freshness=series.freshness_state,
                             calculated_at=datetime.now(timezone.utc),
                             elapsed_ms=round((time.perf_counter() - started) * 1000, 3), points=points)
