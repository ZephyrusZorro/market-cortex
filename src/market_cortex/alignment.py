"""Explicit daily-series alignment for relative strength and correlation."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .contracts import utc
from .features import AnalyticalSeries, _digest


ALIGNMENT_VERSION = "aligned_daily_v1"
ALIGNMENT_CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class FxPoint:
    rate: float
    available_at: datetime
    source_ref: str


@dataclass(frozen=True)
class FxConversion:
    from_currency: str
    to_currency: str
    source_manifest_id: UUID
    points: dict[date, FxPoint]


class ComparisonPoint(BaseModel):
    session_date: date
    value: float | None
    observation_count: int
    expected_count: int
    coverage: float
    missingness: float
    stability: float | None = None
    target_observation_id: UUID | None = None
    reference_observation_id: UUID | None = None
    reference_session_date: date | None = None
    unknown_reason: str | None = None


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_id: str
    calculation_version: str = ALIGNMENT_VERSION
    calculation_code_hash: str = ALIGNMENT_CODE_HASH
    kind: str
    target_instrument_id: UUID
    reference_instrument_id: UUID
    source_manifest_id: UUID
    as_of: datetime
    adjustment_basis: str
    provider_ids: tuple[str | None, str | None]
    alignment_policy: str
    max_reference_age_hours: float
    cutoff_lag_hours: float
    currency: str
    fx_manifest_id: UUID | None = None
    window: int
    method: str
    points: list[ComparisonPoint]


@dataclass(frozen=True)
class Aligned:
    dates: tuple[date, ...]
    target: np.ndarray
    reference: np.ndarray
    target_ids: tuple[UUID | None, ...]
    reference_ids: tuple[UUID | None, ...]
    reference_dates: tuple[date | None, ...]
    currency: str
    fx_manifest_id: UUID | None
    policy: str


def align(target: AnalyticalSeries, reference: AnalyticalSeries, *, policy: str = "same_session",
          fx: FxConversion | None = None, max_reference_age: timedelta = timedelta(days=3),
          cutoff_lag: timedelta = timedelta(0)) -> Aligned:
    if target.manifest_id is None or target.manifest_id != reference.manifest_id or target.as_of != reference.as_of:
        raise ValueError("MANIFEST_OR_AS_OF_MISMATCH")
    if target.adjustment_basis != reference.adjustment_basis:
        raise ValueError("ADJUSTMENT_MISMATCH")
    if target.instrument.trading_currency != reference.instrument.trading_currency:
        if (fx is None or fx.from_currency != target.instrument.trading_currency or
            fx.to_currency != reference.instrument.trading_currency):
            raise ValueError("FX_CONVERSION_REQUIRED")
    elif fx is not None:
        raise ValueError("UNNECESSARY_FX_CONVERSION")
    if max_reference_age < timedelta(0) or cutoff_lag < timedelta(0):
        raise ValueError("INVALID_ALIGNMENT_AGE")
    if policy == "same_session":
        if (target.calendar.venue.venue_id != reference.calendar.venue.venue_id or
            target.calendar.calendar_id != reference.calendar.calendar_id or
            target.calendar.version != reference.calendar.version):
            raise ValueError("CALENDAR_ALIGNMENT_REQUIRED")
        lookup = {day: bar for day, bar in zip(reference.dates, reference.bars)}
        paired = [(day, bar, lookup.get(day)) for day, bar in zip(target.dates, target.bars)]
    elif policy == "completed_at_utc_cutoff":
        # A reference bar must have closed and been available at the target's
        # explicit UTC decision cutoff. Never borrow a future or stale close.
        candidates = sorted((bar for bar in reference.bars if bar is not None),
                            key=lambda bar: bar.end_at, reverse=True)
        paired = []
        for day, bar in zip(target.dates, target.bars):
            if bar is None:
                paired.append((day, None, None))
                continue
            cutoff = bar.end_at + cutoff_lag
            if bar.envelope.available_at is None or bar.envelope.available_at > cutoff:
                paired.append((day, None, None))
                continue
            valid = (candidate for candidate in candidates if candidate.end_at <= cutoff and
                     candidate.envelope.available_at is not None and candidate.envelope.available_at <= cutoff and
                     cutoff - candidate.end_at <= max_reference_age)
            paired.append((day, bar, next(valid, None)))
    else:
        raise ValueError("UNKNOWN_ALIGNMENT_POLICY")
    target_values, reference_values, target_ids, reference_ids, reference_dates = [], [], [], [], []
    for day, left, right in paired:
        rate = 1.0
        if fx is not None:
            point = fx.points.get(day)
            if point is None or utc(point.available_at) > target.as_of or not point.source_ref or not math.isfinite(point.rate) or point.rate <= 0:
                left = right = None
            else:
                rate = point.rate
        target_values.append(float(left.close) * rate if left else math.nan)
        reference_values.append(float(right.close) if right else math.nan)
        target_ids.append(left.envelope.observation_id if left else None)
        reference_ids.append(right.envelope.observation_id if right else None)
        reference_dates.append(right.session_date if right else None)
    return Aligned(tuple(day for day, _, _ in paired), np.array(target_values, dtype=float),
                   np.array(reference_values, dtype=float), tuple(target_ids), tuple(reference_ids),
                   tuple(reference_dates), reference.instrument.trading_currency,
                   fx.source_manifest_id if fx else None, policy)


def compare(target: AnalyticalSeries, reference: AnalyticalSeries, *, kind: str, window: int,
            policy: str = "same_session", fx: FxConversion | None = None,
            max_reference_age: timedelta = timedelta(days=3), cutoff_lag: timedelta = timedelta(0)) -> ComparisonResult:
    if kind not in ("relative_strength", "correlation") or isinstance(window, bool) or not 2 <= window <= 1000 or kind == "correlation" and window < 3:
        raise ValueError("INVALID_COMPARISON_REQUEST")
    aligned = align(target, reference, policy=policy, fx=fx,
                    max_reference_age=max_reference_age, cutoff_lag=cutoff_lag)
    points = []
    previous_correlation = None
    for index, day in enumerate(aligned.dates):
        first = index - window
        value = stability = None
        count = 0
        required = window if kind == "correlation" else window + 1
        if first >= 0:
            target_window = aligned.target[first:index + 1]
            reference_window = aligned.reference[first:index + 1]
            paired = np.isfinite(target_window) & np.isfinite(reference_window)
            count = int((paired[1:] & paired[:-1]).sum()) if kind == "correlation" else int(paired.sum())
            if count == required and np.all(target_window > 0) and np.all(reference_window > 0):
                if kind == "relative_strength":
                    value = float((target_window[-1] / target_window[0]) /
                                  (reference_window[-1] / reference_window[0]) - 1)
                else:
                    left = np.diff(np.log(target_window))
                    right = np.diff(np.log(reference_window))
                    if len(left) >= 3 and np.std(left) > 0 and np.std(right) > 0:
                        value = float(np.corrcoef(left, right)[0, 1])
                        value = max(-1.0, min(1.0, value))
                        if previous_correlation is not None:
                            stability = abs(value - previous_correlation)
                        previous_correlation = value
        else:
            paired = np.isfinite(aligned.target[:index + 1]) & np.isfinite(aligned.reference[:index + 1])
            count = int((paired[1:] & paired[:-1]).sum()) if kind == "correlation" else int(paired.sum())
        if kind == "correlation" and value is None:
            previous_correlation = None
        coverage = count / required
        points.append(ComparisonPoint(session_date=day, value=value, observation_count=count,
                                      expected_count=required, coverage=coverage, missingness=1 - coverage,
                                      stability=stability, target_observation_id=aligned.target_ids[index],
                                      reference_observation_id=aligned.reference_ids[index],
                                      reference_session_date=aligned.reference_dates[index],
                                      unknown_reason=None if value is not None else
                                      ("INSUFFICIENT_ALIGNED_HISTORY" if count < required else "ZERO_VARIANCE_OR_INVALID_PRICE")))
    identity = {"kind": kind, "calculation_version": ALIGNMENT_VERSION,
                "calculation_code_hash": ALIGNMENT_CODE_HASH,
                "target": str(target.instrument.instrument_id),
                "reference": str(reference.instrument.instrument_id), "manifest": str(target.manifest_id),
                "as_of": target.as_of.isoformat(), "window": window, "policy": policy,
                "max_reference_age_seconds": max_reference_age.total_seconds(),
                "cutoff_lag_seconds": cutoff_lag.total_seconds(),
                "fx_manifest": str(aligned.fx_manifest_id) if aligned.fx_manifest_id else None,
                "adjustment_basis": target.adjustment_basis,
                "paired_observations": [(str(left), str(right)) for left, right in zip(aligned.target_ids, aligned.reference_ids)],
                "values": [point.value for point in points]}
    return ComparisonResult(result_id=_digest(identity), kind=kind,
                            target_instrument_id=target.instrument.instrument_id,
                            reference_instrument_id=reference.instrument.instrument_id,
                            source_manifest_id=target.manifest_id, as_of=target.as_of,
                            adjustment_basis=target.adjustment_basis,
                            provider_ids=(target.provider_id, reference.provider_id),
                            alignment_policy=policy,
                            max_reference_age_hours=max_reference_age.total_seconds() / 3600,
                            cutoff_lag_hours=cutoff_lag.total_seconds() / 3600,
                            currency=aligned.currency,
                            fx_manifest_id=aligned.fx_manifest_id, window=window,
                            method="ratio_of_rolling_returns" if kind == "relative_strength" else "Pearson_log_returns",
                            points=points)
