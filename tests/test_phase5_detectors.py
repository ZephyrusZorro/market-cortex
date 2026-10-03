"""Golden synthetic detector cases, independent of live market direction."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from market_cortex.opportunity import Metric, OpportunityService
from market_cortex.opportunity_detectors import DETECTORS, UNSUPPORTED
from market_cortex.opportunity_store import VALID_TRANSITIONS


CUTOFF = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def series(*, count=120, freshness="current"):
    dates = [date(2026, 6, 1) + timedelta(days=index) for index in range(count)]
    bars = [SimpleNamespace(envelope=SimpleNamespace(observation_id=uuid4(), quality_state="valid"))
            for _ in dates]
    return SimpleNamespace(dates=dates, bars=bars, freshness_state=freshness,
        manifest_id=uuid4(), instrument=SimpleNamespace(instrument_id=uuid4()))


VALUES = {
    "momentum": {"return20": .10, "rsi14": 65, "macd_histogram": .2, "ma_alignment": 1},
    "breakout": {"close": 110, "prior_high20": 100, "relative_volume": 1.5, "ma_alignment": 1},
    "pullback": {"ma_alignment": 1, "return5": -.03, "price_vs_ma50": .02,
                 "rsi14": 50, "return20": .05},
    "trend_continuation": {"ma_alignment": 1, "price_vs_ma20": .02,
                           "ma_slope20": .01, "macd_histogram": .2},
    "relative_strength": {"relative_strength_btc20": .06, "return20": .08},
    "volatility_expansion": {"volatility_percentile": 85,
                             "bollinger_bandwidth": .15, "relative_volume": 1.5},
    "mean_reversion": {"price_vs_ma20": -.10, "rsi14": 30,
                       "volatility_percentile": 70, "ma_alignment": 1},
    "swing_trend": {"return20": .1, "ma_alignment": 1,
                    "annualized_volatility": .5, "drawdown": -.1},
}


def evaluate(detector_id, values=None, *, loaded=None, cutoff=CUTOFF):
    loaded = loaded or series()
    metrics = {name: Metric(value, "fixture_unit", f"fixture:{name}", "fixture_v1", {}, coverage=1)
               for name, value in (values or VALUES[detector_id]).items()}
    return OpportunityService._candidate(None, detector=DETECTORS[detector_id],
        symbol="SOLUSDT", loaded=loaded, metrics=metrics,
        regime="uptrend_other", state_id="fixture_state", cutoff=cutoff)


@pytest.mark.parametrize("detector_id", list(DETECTORS))
def test_all_eight_golden_qualifying_conditions(detector_id):
    item = evaluate(detector_id)
    assert item.outcome == "candidate"
    assert item.status == "VALID"
    assert item.detector_strength == "strong"
    assert all(condition.met is True for condition in item.trigger_conditions + item.confirmation_conditions)
    assert all(condition.met is False for condition in item.rejection_conditions)
    assert item.supporting_evidence_ids
    assert item.invalidation_conditions
    assert item.source_manifest_id


def test_rejection_weak_breakout_volume_and_false_breakout():
    weak_volume = evaluate("breakout", {**VALUES["breakout"], "relative_volume": .7})
    assert weak_volume.outcome == "rejected"
    assert weak_volume.status == "AVOID"
    assert any("false-breakout" in reason for reason in weak_volume.contradictions)
    failed_level = evaluate("breakout", {**VALUES["breakout"], "close": 95})
    assert failed_level.outcome == "rejected" and failed_level.status == "NO_EDGE"


def test_breakout_without_prior_high_is_insufficient_data():
    unavailable = evaluate("breakout", {**VALUES["breakout"], "prior_high20": None})
    assert unavailable.outcome == "insufficient_data"
    assert unavailable.status == "WATCHING"
    assert unavailable.trigger_conditions[0].met is None
    assert "PRIOR_20_HIGH_UNAVAILABLE" in unavailable.rejection_reasons


def test_no_edge_and_missing_feature_are_distinct():
    no_edge = evaluate("momentum", {**VALUES["momentum"], "return20": -.02})
    missing = evaluate("momentum", {"return20": .10, "ma_alignment": 1,
                                    "macd_histogram": .2})
    assert no_edge.outcome == "rejected" and no_edge.status == "NO_EDGE"
    assert missing.outcome == "insufficient_data" and missing.status == "WATCHING"
    assert next(item for item in missing.evidence if item.metric == "rsi14").reason == "METRIC_UNAVAILABLE"


def test_history_freshness_and_contradiction_gate_strength():
    short = evaluate("volatility_expansion", loaded=series(count=50))
    stale = evaluate("momentum", loaded=series(freshness="stale"))
    downtrend = evaluate("mean_reversion", {**VALUES["mean_reversion"], "ma_alignment": -1})
    assert short.outcome == "insufficient_data"
    assert stale.status == "WATCHING" and stale.detector_strength == "weak"
    assert downtrend.status == "AVOID" and downtrend.contradictions


def test_candidate_identity_dedupes_same_evidence_across_cutoffs():
    loaded = series()
    first = evaluate("momentum", loaded=loaded)
    later = evaluate("momentum", loaded=loaded, cutoff=CUTOFF + timedelta(minutes=5))
    assert first.candidate_id == later.candidate_id
    assert first.evidence_hash != later.evidence_hash


def test_transition_registry_and_unsupported_scope():
    assert "INVALIDATED" in VALID_TRANSITIONS["VALID"]
    assert "VALID" not in VALID_TRANSITIONS["INVALIDATED"]
    assert set(UNSUPPORTED) == {"liquidity_sweep", "event_driven", "accumulation_proxy"}
