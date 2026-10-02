"""Pure daily-bar indicator kernels. Missing sessions are NaN and break windows."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(numerator, denominator, out=np.full(len(numerator), np.nan),
                     where=np.isfinite(numerator) & np.isfinite(denominator) & (denominator != 0))


def _rolling(values: np.ndarray, period: int, operation: str, ddof: int = 0) -> np.ndarray:
    result = np.full(len(values), np.nan)
    if len(values) < period:
        return result
    windows = sliding_window_view(values, period)
    valid = np.isfinite(windows).all(axis=1)
    if operation == "mean":
        calculated = windows.mean(axis=1)
    elif operation == "std":
        calculated = windows.std(axis=1, ddof=ddof)
    elif operation == "max":
        calculated = windows.max(axis=1)
    elif operation == "min":
        calculated = windows.min(axis=1)
    else:
        raise ValueError("unknown rolling operation")
    result[period - 1:] = np.where(valid, calculated, np.nan)
    return result


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    alpha = 2.0 / (period + 1)
    run: list[float] = []
    previous = math.nan
    for index, value in enumerate(values):
        if not math.isfinite(value):
            run.clear()
            previous = math.nan
            continue
        if math.isnan(previous):
            run.append(float(value))
            if len(run) == period:
                previous = float(np.mean(run))
                result[index] = previous
                run.clear()
        else:
            previous = alpha * value + (1 - alpha) * previous
            result[index] = previous
    return result


def _return(values: np.ndarray, *, log: bool = False, lag: int = 1) -> np.ndarray:
    result = np.full(len(values), np.nan)
    if len(values) <= lag:
        return result
    valid = np.isfinite(values) & (values > 0)
    # A return never bridges an expected session with no visible observation.
    full = _rolling(valid.astype(float), lag + 1, "min") == 1
    indices = np.arange(lag, len(values))
    good = full[indices]
    ratios = np.divide(values[indices], values[indices - lag],
                       out=np.full(len(indices), np.nan), where=good)
    result[indices] = np.where(good, np.log(ratios) if log else ratios - 1, np.nan)
    return result


def _rsi(close: np.ndarray, period: int) -> np.ndarray:
    delta = np.diff(close, prepend=np.nan)
    result = np.full(len(close), np.nan)
    gains: list[float] = []
    losses: list[float] = []
    avg_gain = avg_loss = math.nan
    for index, change in enumerate(delta):
        if not math.isfinite(change):
            gains.clear()
            losses.clear()
            avg_gain = avg_loss = math.nan
            continue
        gain, loss = max(float(change), 0.0), max(-float(change), 0.0)
        if math.isnan(avg_gain):
            gains.append(gain)
            losses.append(loss)
            if len(gains) < period:
                continue
            avg_gain, avg_loss = float(np.mean(gains)), float(np.mean(losses))
            gains.clear()
            losses.clear()
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        result[index] = (50.0 if avg_gain == avg_loss == 0 else
                         100.0 if avg_loss == 0 else
                         100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    return result


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    result = np.full(len(close), np.nan)
    for index in range(len(close)):
        if not (math.isfinite(high[index]) and math.isfinite(low[index])):
            continue
        prior = close[index - 1] if index else math.nan
        result[index] = max(high[index] - low[index], abs(high[index] - prior),
                            abs(low[index] - prior)) if math.isfinite(prior) else high[index] - low[index]
    return result


def _wilder(values: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    run: list[float] = []
    previous = math.nan
    for index, value in enumerate(values):
        if not math.isfinite(value):
            run.clear()
            previous = math.nan
            continue
        if math.isnan(previous):
            run.append(float(value))
            if len(run) == period:
                previous = float(np.mean(run))
                result[index] = previous
                run.clear()
        else:
            previous = (previous * (period - 1) + value) / period
            result[index] = previous
    return result


def _drawdown(close: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    peak = np.full(len(close), np.nan)
    drawdown = np.full(len(close), np.nan)
    maximum = np.full(len(close), np.nan)
    duration = np.full(len(close), np.nan)
    recovery = np.full(len(close), np.nan)
    current_peak = math.nan
    worst = 0.0
    days = 0
    for index, value in enumerate(close):
        if not math.isfinite(value):
            current_peak = math.nan
            worst = 0.0
            days = 0
            continue
        if math.isnan(current_peak) or value >= current_peak:
            current_peak = float(value)
            days = 0
            recovery[index] = 1.0
        else:
            days += 1
            recovery[index] = 0.0
        peak[index] = current_peak
        drawdown[index] = value / current_peak - 1
        worst = min(worst, float(drawdown[index]))
        maximum[index] = worst
        duration[index] = days
    return peak, drawdown, maximum, duration, recovery


def calculate(name: str, columns: Mapping[str, np.ndarray], params: Mapping[str, int | float]) -> np.ndarray:
    """Return one float64 value per expected session; NaN means unavailable."""
    close, open_, high, low, volume = (columns[key] for key in ("close", "open", "high", "low", "volume"))
    period = int(params.get("period", 20))
    fast, slow = int(params.get("fast", 12)), int(params.get("slow", 26))
    if name == "arithmetic_return": return _return(close)
    if name == "log_return": return _return(close, log=True)
    if name == "cumulative_return":
        result = np.full(len(close), np.nan)
        base = math.nan
        for index, value in enumerate(close):
            if not math.isfinite(value):
                base = math.nan
            else:
                if math.isnan(base): base = float(value)
                result[index] = value / base - 1
        return result
    if name in ("rolling_return", "roc"): return _return(close, lag=period) * (100 if name == "roc" else 1)
    if name == "gap_return":
        prior = np.roll(close, 1)
        if len(prior): prior[0] = np.nan
        return _safe_divide(open_, prior) - 1
    if name == "sma": return _rolling(close, period, "mean")
    if name == "ema": return _ema(close, period)
    if name == "price_vs_ma": return (_safe_divide(close, _rolling(close, period, "mean")) - 1) * 100
    if name == "ma_slope":
        ma = _rolling(close, period, "mean")
        return _return(ma, lag=int(params["slope_period"])) * 100
    if name == "ma_alignment":
        difference = _rolling(close, fast, "mean") - _rolling(close, slow, "mean")
        return np.where(np.isfinite(difference), np.sign(difference), np.nan)
    if name == "higher_high_lower_low":
        highs, lows = _rolling(high, period, "max"), _rolling(low, period, "min")
        prior_high, prior_low = np.roll(highs, period), np.roll(lows, period)
        prior_high[:period], prior_low[:period] = np.nan, np.nan
        valid = np.isfinite(highs) & np.isfinite(lows) & np.isfinite(prior_high) & np.isfinite(prior_low)
        direction = np.where((highs > prior_high) & (lows > prior_low), 1,
                             np.where((highs < prior_high) & (lows < prior_low), -1, 0))
        return np.where(valid, direction, np.nan).astype(float)
    if name == "trend_persistence":
        returns = _return(close)
        positive = _rolling(np.where(np.isfinite(returns), (returns > 0).astype(float), np.nan), period, "mean")
        negative = _rolling(np.where(np.isfinite(returns), (returns < 0).astype(float), np.nan), period, "mean")
        return positive - negative
    if name == "trend_strength":
        tr = _true_range(high, low, close)
        return _safe_divide(_rolling(close, fast, "mean") - _rolling(close, slow, "mean"), _wilder(tr, 14))
    if name == "rsi": return _rsi(close, period)
    if name in ("macd", "macd_signal", "macd_histogram"):
        line = _ema(close, fast) - _ema(close, slow)
        if name == "macd": return line
        signal = _ema(line, int(params["signal"]))
        return signal if name == "macd_signal" else line - signal
    if name == "rolling_std": return _rolling(_return(close), period, "std", ddof=1)
    if name == "annualized_volatility":
        return _rolling(_return(close, log=True), period, "std", ddof=1) * math.sqrt(int(params["annualization"]))
    if name == "true_range": return _true_range(high, low, close)
    if name == "atr": return _wilder(_true_range(high, low, close), period)
    if name.startswith("bollinger_"):
        middle = _rolling(close, period, "mean")
        spread = float(params["deviations"]) * _rolling(close, period, "std", ddof=0)
        return {"bollinger_middle": middle, "bollinger_upper": middle + spread,
                "bollinger_lower": middle - spread,
                "bollinger_bandwidth": _safe_divide(2 * spread, middle) * 100}[name]
    if name == "rolling_high_low_range":
        lowest = _rolling(low, period, "min")
        return _safe_divide(_rolling(high, period, "max") - lowest, lowest) * 100
    if name == "volatility_percentile":
        volatility = _rolling(_return(close, log=True), period, "std", ddof=1) * math.sqrt(int(params["annualization"]))
        rank_window = int(params["rank_window"])
        result = np.full(len(close), np.nan)
        for index in range(rank_window - 1, len(close)):
            window = volatility[index - rank_window + 1:index + 1]
            if np.isfinite(window).all():
                below = np.count_nonzero(window < window[-1])
                equal = np.count_nonzero(window == window[-1])
                result[index] = float((below + equal / 2) / rank_window * 100)
        return result
    if name == "average_volume": return _rolling(volume, period, "mean")
    if name == "relative_volume": return _safe_divide(volume, _rolling(volume, period, "mean"))
    if name == "volume_change": return _return(volume)
    if name == "volume_zscore":
        std = _rolling(volume, period, "std", ddof=1)
        return _safe_divide(volume - _rolling(volume, period, "mean"), std)
    if name == "price_volume_confirmation": return np.sign(_return(close)) * _safe_divide(volume, _rolling(volume, period, "mean"))
    if name in ("running_peak", "drawdown", "maximum_drawdown", "drawdown_duration", "recovery_state"):
        return dict(zip(("running_peak", "drawdown", "maximum_drawdown", "drawdown_duration", "recovery_state"),
                        _drawdown(close)))[name]
    raise KeyError(name)
