"""Universe-scoped breadth with explicit denominators and missing members."""

from __future__ import annotations

import hashlib
import math
from datetime import date
from pathlib import Path
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict

from .features import AnalyticalSeries, FeatureEngine, FeatureRequest, _digest


BREADTH_CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class BreadthMetric(BaseModel):
    eligible: int
    positive: int
    percentage: float | None
    missing_members: list[str]


class BreadthSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str
    universe_id: str
    member_ids: dict[str, UUID]
    session_date: date
    source_manifest_id: UUID
    as_of: str
    calendar_id: str
    calendar_version: str
    observed_members: int
    total_members: int
    above_sma: BreadthMetric
    positive_lookback: BreadthMetric
    new_high: BreadthMetric
    new_low: BreadthMetric
    advancing: int
    declining: int
    unchanged: int
    advance_decline_eligible: int
    feature_refs: list[str]
    rule_version: str = "breadth_v1"
    rule_code_hash: str = BREADTH_CODE_HASH


def _metric(outcomes: dict[str, bool | None]) -> BreadthMetric:
    eligible = sum(value is not None for value in outcomes.values())
    positive = sum(value is True for value in outcomes.values())
    return BreadthMetric(eligible=eligible, positive=positive,
                         percentage=100 * positive / eligible if eligible else None,
                         missing_members=[name for name, value in outcomes.items() if value is None])


def calculate_breadth(engine: FeatureEngine, universe_id: str,
                      members: dict[str, AnalyticalSeries], session_date: date,
                      *, period: int = 20) -> BreadthSnapshot:
    if not universe_id or not members or isinstance(period, bool) or not 2 <= period <= 1000:
        raise ValueError("INVALID_BREADTH_REQUEST")
    first = next(iter(members.values()))
    if first.manifest_id is None:
        raise ValueError("DATASET_EMPTY")
    for member in members.values():
        if (member.manifest_id != first.manifest_id or member.as_of != first.as_of or
            member.calendar.venue.venue_id != first.calendar.venue.venue_id or
            member.calendar.calendar_id != first.calendar.calendar_id or
            member.calendar.version != first.calendar.version or
            member.adjustment_basis != first.adjustment_basis or member.dates != first.dates):
            raise ValueError("BREADTH_ALIGNMENT_REQUIRED")
    if session_date not in first.dates:
        raise ValueError("SESSION_NOT_IN_UNIVERSE_WINDOW")
    index = first.dates.index(session_date)
    above, positive, highs, lows = {}, {}, {}, {}
    advance = decline = unchanged = 0
    references = []
    for symbol, member in members.items():
        base = dict(instrument_id=member.instrument.instrument_id, start_date=member.dates[0],
                    end_date=member.dates[-1], as_of=member.as_of, manifest_id=member.manifest_id,
                    provider_id=member.provider_id, adjustment_basis=member.adjustment_basis)
        ma = engine.calculate(FeatureRequest(feature="sma", parameters={"period": period}, **base), member)
        ret = engine.calculate(FeatureRequest(feature="rolling_return", parameters={"period": period}, **base), member)
        references.extend((ma.feature_id, ret.feature_id))
        close = member.columns["close"]
        current = close[index]
        ma_value, return_value = ma.points[index].value, ret.points[index].value
        above[symbol] = bool(current > ma_value) if math.isfinite(current) and ma_value is not None else None
        positive[symbol] = bool(return_value > 0) if return_value is not None else None
        previous = member.columns["close"][index - 1] if index else math.nan
        if math.isfinite(current) and math.isfinite(previous):
            if current > previous: advance += 1
            elif current < previous: decline += 1
            else: unchanged += 1
        if index >= period:
            prior_high = member.columns["high"][index - period:index]
            prior_low = member.columns["low"][index - period:index]
            current_high, current_low = member.columns["high"][index], member.columns["low"][index]
            highs[symbol] = bool(current_high > np.max(prior_high)) if np.isfinite(prior_high).all() and math.isfinite(current_high) else None
            lows[symbol] = bool(current_low < np.min(prior_low)) if np.isfinite(prior_low).all() and math.isfinite(current_low) else None
        else:
            highs[symbol] = lows[symbol] = None
    payload = {"rule_version": "breadth_v1", "rule_code_hash": BREADTH_CODE_HASH,
               "universe": universe_id, "members": {name: str(item.instrument.instrument_id) for name, item in members.items()},
               "session_date": str(session_date), "manifest": str(first.manifest_id), "as_of": first.as_of.isoformat(),
               "calendar_id": first.calendar.calendar_id, "calendar_version": first.calendar.version,
               "period": period, "feature_refs": references,
               "above": above, "positive": positive, "highs": highs, "lows": lows}
    return BreadthSnapshot(snapshot_id=_digest(payload), universe_id=universe_id,
                           member_ids={name: item.instrument.instrument_id for name, item in members.items()},
                           session_date=session_date, source_manifest_id=first.manifest_id,
                           as_of=first.as_of.isoformat(), calendar_id=first.calendar.calendar_id,
                           calendar_version=first.calendar.version,
                           observed_members=sum(member.bars[index] is not None for member in members.values()),
                           total_members=len(members), above_sma=_metric(above), positive_lookback=_metric(positive),
                           new_high=_metric(highs), new_low=_metric(lows), advancing=advance, declining=decline,
                           unchanged=unchanged, advance_decline_eligible=advance + decline + unchanged,
                           feature_refs=references)
