"""Range-based technical indicators ported from the teammate `stocky` branch.

Pure functions over completed OHLC rows. An indicator is omitted, never
defaulted to a neutral value, when its inputs are missing or too short.
"""
import math

PERIOD = 14


def _wilder_smooth(values, period):
    """Wilder's running sum: S_t = S_{t-1} - S_{t-1}/period + v_t."""
    if len(values) < period:
        return []
    out = [sum(values[:period])]
    for v in values[period:]:
        out.append(out[-1] - out[-1] / period + v)
    return out


def _true_ranges(highs, lows, closes):
    return [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]


def atr(highs, lows, closes, period=PERIOD):
    smoothed = _wilder_smooth(_true_ranges(highs, lows, closes), period)
    return smoothed[-1] / period if smoothed else None


def adx(highs, lows, closes, period=PERIOD):
    """Return (ADX, +DI, -DI) using Wilder's directional-movement method."""
    if len(closes) < 2 * period + 1:
        return None
    plus_dm, minus_dm = [], []
    for i in range(1, len(closes)):
        up, down = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    s_tr = _wilder_smooth(_true_ranges(highs, lows, closes), period)
    s_plus, s_minus = _wilder_smooth(plus_dm, period), _wilder_smooth(minus_dm, period)
    plus_di = [100 * p / t if t else 0.0 for p, t in zip(s_plus, s_tr)]
    minus_di = [100 * m / t if t else 0.0 for m, t in zip(s_minus, s_tr)]
    dx = [100 * abs(p - m) / (p + m) if p + m else 0.0 for p, m in zip(plus_di, minus_di)]
    smoothed = _wilder_smooth(dx, period)
    if not smoothed:
        return None
    return smoothed[-1] / period, plus_di[-1], minus_di[-1]


def stochastic(highs, lows, closes, k_period=PERIOD, d_period=3):
    """Return (%K, %D). A flat window has no defined position, so it is skipped."""
    ks = []
    for i in range(k_period - 1, len(closes)):
        hh, ll = max(highs[i - k_period + 1 : i + 1]), min(lows[i - k_period + 1 : i + 1])
        if hh != ll:
            ks.append(100 * (closes[i] - ll) / (hh - ll))
    if len(ks) < d_period:
        return None
    return ks[-1], sum(ks[-d_period:]) / d_period


def _series(rows, key):
    values = [r.get(key) for r in rows]
    if any(v is None or not math.isfinite(float(v)) for v in values):
        return None
    return [float(v) for v in values]


def range_indicators(rows, text_key):
    """Indicator items for completed candles; `text_key` matches each caller's schema."""
    highs, lows, closes = _series(rows, "high"), _series(rows, "low"), _series(rows, "close")
    if not (highs and lows and closes):
        return []
    items = []

    def add(name, value, text):
        items.append({"name": name, "value": round(float(value), 2), text_key: text})

    a = atr(highs, lows, closes)
    if a is not None:
        add("ATR (14 bars)", a, "Average true range: typical bar-to-bar movement in price units, including gaps.")
    d = adx(highs, lows, closes)
    if d is not None:
        add("ADX (14 bars)", d[0], "Trend strength regardless of direction. Above 25 is commonly read as trending; it does not say which way.")
        add("+DI (14 bars)", d[1], "Upward directional movement. Compare with -DI for the dominant direction.")
        add("-DI (14 bars)", d[2], "Downward directional movement. Compare with +DI for the dominant direction.")
    s = stochastic(highs, lows, closes)
    if s is not None:
        add("Stochastic %K (14 bars)", s[0], "Latest close within the 14-bar high-low range (0 = low, 100 = high).")
        add("Stochastic %D (3 bars)", s[1], "Three-bar average of %K, a smoothed version for comparison.")
    return items
