"""Hand-calculated golden cases, missingness, and indicator invariants."""

from __future__ import annotations

import math
import json
from pathlib import Path

import numpy as np
import pytest

from market_cortex.calendar import SessionCalendar
from market_cortex.contracts import Venue
from market_cortex.alignment import ALIGNMENT_CODE_HASH, ALIGNMENT_VERSION
from market_cortex.breadth import BREADTH_CODE_HASH
from market_cortex.features import (CALCULATION_CODE_HASH, CALCULATION_VERSION,
                                    FEATURE_VERSION, REGISTRY, resolve_parameters)
from market_cortex.indicators import calculate
from market_cortex.market_state import REGIME_RULE_VERSION, STATE_CODE_HASH, STATE_RULE_VERSION


def columns(closes, *, volumes=None, highs=None, lows=None, opens=None):
    close = np.array(closes, dtype=float)
    return {"close": close, "open": np.array(opens if opens is not None else close, dtype=float),
            "high": np.array(highs if highs is not None else close + 1, dtype=float),
            "low": np.array(lows if lows is not None else close - 1, dtype=float),
            "volume": np.array(volumes if volumes is not None else np.ones(len(close)), dtype=float)}


def values(name, closes, params=None, **extra):
    return calculate(name, columns(closes, **extra), params or {})


def test_hand_calculated_returns_and_moving_averages():
    close = [100, 110, 121, 133.1]
    np.testing.assert_allclose(values("arithmetic_return", close)[1:], [0.1] * 3)
    np.testing.assert_allclose(values("log_return", close)[1:], [math.log(1.1)] * 3)
    np.testing.assert_allclose(values("cumulative_return", close), [0, .1, .21, .331])
    assert values("rolling_return", close, {"period": 2})[-1] == pytest.approx(.21)
    assert values("roc", close, {"period": 2})[-1] == pytest.approx(21)
    assert values("gap_return", [100, 110], opens=[100, 105])[-1] == pytest.approx(.05)
    sma = values("sma", [1, 2, 3, 4, 5], {"period": 3})
    ema = values("ema", [1, 2, 3, 4, 5], {"period": 3})
    assert np.isnan(sma[:2]).all() and np.isnan(ema[:2]).all()
    np.testing.assert_allclose(sma[2:], [2, 3, 4])
    np.testing.assert_allclose(ema[2:], [2, 3, 4])


def test_hand_calculated_rsi_and_macd():
    rsi = values("rsi", [100, 110, 120, 110, 100], {"period": 2})
    assert np.isnan(rsi[:2]).all()
    np.testing.assert_allclose(rsi[2:], [100, 50, 25])
    assert values("rsi", [5] * 6, {"period": 2})[-1] == 50
    params = {"fast": 2, "slow": 3, "signal": 2}
    line = values("macd", [1, 2, 3, 4, 5, 6], params)
    signal = values("macd_signal", [1, 2, 3, 4, 5, 6], params)
    histogram = values("macd_histogram", [1, 2, 3, 4, 5, 6], params)
    np.testing.assert_allclose(line[2:], [.5] * 4)
    assert np.isnan(signal[:3]).all()
    np.testing.assert_allclose(signal[3:], [.5] * 3)
    np.testing.assert_allclose(histogram[3:], [0] * 3)


def test_hand_calculated_true_range_atr_bollinger_volatility_and_volume():
    series = columns([10, 11, 12], highs=[11, 12, 13], lows=[9, 10, 11], volumes=[10, 20, 30])
    np.testing.assert_allclose(calculate("true_range", series, {}), [2, 2, 2])
    atr = calculate("atr", series, {"period": 2})
    assert np.isnan(atr[0])
    np.testing.assert_allclose(atr[1:], [2, 2])
    bb = columns([1, 2, 3])
    params = {"period": 3, "deviations": 2.0}
    sigma = math.sqrt(2 / 3)
    assert calculate("bollinger_middle", bb, params)[-1] == 2
    assert calculate("bollinger_upper", bb, params)[-1] == pytest.approx(2 + 2 * sigma)
    assert calculate("bollinger_lower", bb, params)[-1] == pytest.approx(2 - 2 * sigma)
    assert calculate("bollinger_bandwidth", bb, params)[-1] == pytest.approx(2 * sigma * 2 / 2 * 100)
    assert calculate("relative_volume", series, {"period": 3})[-1] == pytest.approx(1.5)
    assert calculate("volume_zscore", series, {"period": 3})[-1] == pytest.approx(1)
    log_delta = math.log(1.1)
    log_other = math.log(100 / 110)
    expected = np.std([log_delta, log_other], ddof=1) * math.sqrt(365)
    assert values("annualized_volatility", [100, 110, 100],
                  {"period": 2, "annualization": 365})[-1] == pytest.approx(expected)


def test_drawdown_golden_and_invariants():
    close = [100, 120, 90, 120, 130]
    np.testing.assert_allclose(values("running_peak", close), [100, 120, 120, 120, 130])
    np.testing.assert_allclose(values("drawdown", close), [0, 0, -.25, 0, 0])
    np.testing.assert_allclose(values("maximum_drawdown", close), [0, 0, -.25, -.25, -.25])
    np.testing.assert_allclose(values("drawdown_duration", close), [0, 0, 1, 0, 0])
    np.testing.assert_allclose(values("recovery_state", close), [1, 1, 0, 1, 1])
    rng = np.random.default_rng(42)
    random_prices = np.exp(rng.normal(size=300).cumsum())
    assert np.nanmax(values("drawdown", random_prices)) <= 0
    assert np.nanmax(values("maximum_drawdown", random_prices)) <= 0
    upper = values("bollinger_upper", random_prices, {"period": 20, "deviations": 2})
    middle = values("bollinger_middle", random_prices, {"period": 20, "deviations": 2})
    lower = values("bollinger_lower", random_prices, {"period": 20, "deviations": 2})
    assert np.all(upper[19:] >= middle[19:]) and np.all(middle[19:] >= lower[19:])
    np.testing.assert_allclose(values("sma", [9] * 30, {"period": 20})[19:], [9] * 11)
    assert values("volatility_percentile", [9] * 30,
                  {"period": 5, "rank_window": 5, "annualization": 365})[-1] == 50


def test_missing_gap_breaks_windows_and_volume_never_invented():
    close = [1, 2, math.nan, 4, 5, 6]
    assert np.isnan(values("arithmetic_return", close)[3])
    assert np.isnan(values("sma", close, {"period": 3})[4])
    assert values("sma", close, {"period": 3})[5] == 5
    assert np.isnan(values("ema", close, {"period": 3})[4])
    assert values("ema", close, {"period": 3})[5] == 5
    assert np.isnan(values("relative_volume", [1, 2, 3], {"period": 2},
                        volumes=[10, math.nan, 30])[-1])
    assert np.isnan(values("arithmetic_return", [100])[0])
    assert np.isnan(values("volume_zscore", [1, 2, 3], {"period": 3}, volumes=[4, 4, 4])[-1])
    assert np.isnan(values("arithmetic_return", [0, 10])[-1])
    volatile = values("log_return", [100, 1, 1000, 2])
    assert np.isfinite(volatile[1:]).all()


def test_registry_metadata_parameter_validation_and_annualization():
    assert len(REGISTRY) >= 35
    crypto = SessionCalendar(Venue(venue_id="BINANCE_SPOT", timezone="UTC", session_kind="24x7"), "utc", "v1")
    equity = SessionCalendar(Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular"), "nyse", "v1")
    assert resolve_parameters("annualized_volatility", {}, crypto)["annualization"] == 365
    assert resolve_parameters("annualized_volatility", {}, equity)["annualization"] == 252
    assert all(item.version and item.calculation_version and item.unit and item.min_history and item.supported_intervals
               for item in REGISTRY.values())
    for name, params in (("rsi", {"period": 1}), ("sma", {"period": 0}),
                         ("macd", {"fast": 30, "slow": 20}),
                         ("bollinger_upper", {"deviations": -1}),
                         ("sma", {"arbitrary_python": 1}),
                         ("sma", {"period": True})):
        with pytest.raises(ValueError):
            resolve_parameters(name, params, crypto)


def test_phase2_version_lock_requires_review_for_code_changes():
    lock = json.loads((Path(__file__).resolve().parents[1] / "docs" / "analytics" /
                       "VERSION_LOCKS_2026-10-03.json").read_text(encoding="utf-8"))
    assert lock == {"feature_version": FEATURE_VERSION, "calculation_version": CALCULATION_VERSION,
                    "feature_code_sha256": CALCULATION_CODE_HASH,
                    "alignment_version": ALIGNMENT_VERSION,
                    "alignment_code_sha256": ALIGNMENT_CODE_HASH,
                    "breadth_version": "breadth_v1", "breadth_code_sha256": BREADTH_CODE_HASH,
                    "state_version": STATE_RULE_VERSION, "regime_version": REGIME_RULE_VERSION,
                    "state_code_sha256": STATE_CODE_HASH}
