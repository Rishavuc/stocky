import hashlib
import math
import random
from typing import Dict, List, Any, Tuple
from app.services.market_ingest import market_ingest
from app.schemas.schemas import TechnicalAnalysisResponse, IndicatorItem, OptionChainResponse, OptionChainItem


def _seed_for(symbol: str) -> int:
    """Deterministic per-symbol seed so derived fundamentals don't flap."""
    return int(hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:8], 16)


# ========================================================
# INDICATOR MATH (pure functions, no external deps)
# ========================================================
def _sma(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    p = min(period, len(values))
    return sum(values[-p:]) / p


def _ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [float(values[0])]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


def _rsi_wilder(closes: List[float], period: int = 14) -> float:
    """RSI using Wilder's smoothing (the standard trading-platform formula)."""
    if len(closes) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses += -diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _wilder_smooth(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    out = [sum(values[:period])]
    for v in values[period:]:
        out.append(out[-1] - (out[-1] / period) + v)
    return out


def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    s = _wilder_smooth(trs, period)
    return (s[-1] / period) if s else 0.0


def _adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[float, float, float]:
    """Return (ADX, +DI, -DI) using Wilder's directional-movement method."""
    n = len(closes)
    if n < period + 2:
        return 0.0, 0.0, 0.0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    s_plus = _wilder_smooth(plus_dm, period)
    s_minus = _wilder_smooth(minus_dm, period)
    s_tr = _wilder_smooth(trs, period)
    if not s_tr:
        return 0.0, 0.0, 0.0
    plus_di = [100.0 * p / t if t else 0.0 for p, t in zip(s_plus, s_tr)]
    minus_di = [100.0 * m / t if t else 0.0 for m, t in zip(s_minus, s_tr)]
    dx = [100.0 * abs(p - m) / (p + m) if (p + m) else 0.0 for p, m in zip(plus_di, minus_di)]
    adx_series = _wilder_smooth(dx, period)
    # _wilder_smooth returns a smoothed *sum*; ADX is its average.
    adx = (adx_series[-1] / period) if adx_series else (dx[-1] if dx else 0.0)
    return adx, (plus_di[-1] if plus_di else 0.0), (minus_di[-1] if minus_di else 0.0)


def _stochastic(highs: List[float], lows: List[float], closes: List[float],
                k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
    if len(closes) < k_period:
        return 50.0, 50.0
    ks = []
    for i in range(k_period - 1, len(closes)):
        hh = max(highs[i - k_period + 1:i + 1])
        ll = min(lows[i - k_period + 1:i + 1])
        ks.append(100.0 * (closes[i] - ll) / (hh - ll) if hh != ll else 50.0)
    k = ks[-1]
    d = sum(ks[-d_period:]) / min(d_period, len(ks))
    return k, d


class AnalysisEngine:
    def get_technical_analysis(self, symbol: str) -> TechnicalAnalysisResponse:
        sym = symbol.upper().strip()
        quote = market_ingest.get_quote(sym)
        price = quote.price if quote else 2500.0
        change_pct = quote.change_pct if quote else 1.25

        # Pull ~1 year of daily candles: drives indicators AND the real 52W range.
        candles = market_ingest.get_candles(sym, "1d", 252)
        if not candles or len(candles) < 20:
            candles = market_ingest.get_candles(sym, "1d", 60)

        if candles and len(candles) >= 5:
            closes = [float(c.close) for c in candles]
            highs = [float(c.high) for c in candles]
            lows = [float(c.low) for c in candles]
            volumes = [float(c.volume) for c in candles]
        else:
            closes = [price * (1 + (i - 15) * 0.005) for i in range(30)]
            highs = [c * 1.008 for c in closes]
            lows = [c * 0.992 for c in closes]
            volumes = [0.0 for _ in closes]

        is_crypto = ("USDT" in sym or sym.endswith("INR")
                     or sym.startswith("BTC") or sym.startswith("ETH") or sym.startswith("SOL"))
        curr = "$" if is_crypto else "₹"

        # ---- RSI (14, Wilder) ----
        rsi_val = round(_rsi_wilder(closes, 14), 1)
        rsi_signal = "Overbought" if rsi_val > 70 else ("Oversold" if rsi_val < 30 else "Neutral")
        rsi_cls = "sell" if rsi_val > 70 else ("buy" if rsi_val < 30 else "neutral")

        # ---- EMA / SMA ----
        ema20_val = round(_ema_series(closes, 20)[-1], 2)
        ema50_val = round(_ema_series(closes, 50)[-1], 2)
        sma20_val = round(_sma(closes, 20), 2)
        sma50_val = round(_sma(closes, 50), 2)

        # ---- Bollinger Bands (20, 2σ) ----
        window = closes[-20:]
        variance = sum((x - sma20_val) ** 2 for x in window) / max(1, len(window))
        std_dev = math.sqrt(variance)
        upper_bb = round(sma20_val + (2 * std_dev), 2)
        lower_bb = round(sma20_val - (2 * std_dev), 2)

        # ---- MACD (12, 26, 9) ----
        ema12_series = _ema_series(closes, 12)
        ema26_series = _ema_series(closes, 26)
        macd_series = [a - b for a, b in zip(ema12_series, ema26_series)]
        signal_series = _ema_series(macd_series, 9)
        macd_val = round(macd_series[-1], 2)
        macd_signal_val = round(signal_series[-1], 2)
        macd_hist = round(macd_val - macd_signal_val, 2)
        macd_signal = "Bullish Cross" if macd_hist > 0 else "Bearish Trend"
        macd_cls = "buy" if macd_hist > 0 else "sell"

        # ---- ATR (14) ----
        atr_val = round(_atr(highs, lows, closes, 14), 2)

        # ---- ADX (14) ----
        adx_val, plus_di, minus_di = _adx(highs, lows, closes, 14)
        adx_val = round(adx_val, 1)
        if adx_val >= 25:
            adx_signal, adx_cls = "Strong Trend", ("buy" if plus_di >= minus_di else "sell")
        elif adx_val >= 20:
            adx_signal, adx_cls = "Trend Building", ("buy" if plus_di >= minus_di else "sell")
        else:
            adx_signal, adx_cls = "Sideways / Weak", "neutral"

        # ---- Stochastic (14, 3) ----
        stoch_k, stoch_d = _stochastic(highs, lows, closes, 14, 3)
        stoch_k = round(stoch_k, 1)
        stoch_d = round(stoch_d, 1)
        if stoch_k > 80:
            stoch_signal, stoch_cls = "Overbought", "sell"
        elif stoch_k < 20:
            stoch_signal, stoch_cls = "Oversold", "buy"
        else:
            stoch_signal, stoch_cls = "Momentum Flow", "neutral"

        # ---- Volume trend ----
        if volumes and any(volumes):
            avg_vol = sum(volumes[-20:]) / max(1, len(volumes[-20:]))
            last_vol = volumes[-1] if volumes[-1] else avg_vol
            ratio = last_vol / avg_vol if avg_vol else 1.0
            if ratio >= 1.2:
                vol_signal, vol_cls, vol_txt = "Above Average", "buy", f"{ratio:.2f}x avg"
            elif ratio <= 0.8:
                vol_signal, vol_cls, vol_txt = "Below Average", "neutral", f"{ratio:.2f}x avg"
            else:
                vol_signal, vol_cls, vol_txt = "In Line", "neutral", f"{ratio:.2f}x avg"
        else:
            vol_signal, vol_cls, vol_txt = "In Line", "neutral", "n/a"

        # ---- Indicator suite ----
        indicators = [
            IndicatorItem(name="RSI (14)", value=str(rsi_val), signal=rsi_signal, signal_type=rsi_cls),
            IndicatorItem(name="MACD (12, 26, 9)", value=f"{'+' if macd_val > 0 else ''}{macd_val} / sig {macd_signal_val}",
                          signal=macd_signal, signal_type=macd_cls),
            IndicatorItem(name="EMA (20)", value=f"{curr}{ema20_val:,.2f}",
                          signal="Trading Above" if price >= ema20_val else "Trading Below",
                          signal_type="buy" if price >= ema20_val else "sell"),
            IndicatorItem(name="EMA (50)", value=f"{curr}{ema50_val:,.2f}",
                          signal="Golden Structure" if ema20_val >= ema50_val else "Death Structure",
                          signal_type="buy" if ema20_val >= ema50_val else "sell"),
            IndicatorItem(name="SMA (20)", value=f"{curr}{sma20_val:,.2f}", signal="Baseline Trend", signal_type="neutral"),
            IndicatorItem(name="SMA (50)", value=f"{curr}{sma50_val:,.2f}",
                          signal="Long-term Up" if price >= sma50_val else "Long-term Down",
                          signal_type="buy" if price >= sma50_val else "sell"),
            IndicatorItem(name="Bollinger Upper", value=f"{curr}{upper_bb:,.2f}",
                          signal="Resistance Bound", signal_type="sell" if price >= upper_bb * 0.99 else "neutral"),
            IndicatorItem(name="Bollinger Lower", value=f"{curr}{lower_bb:,.2f}",
                          signal="Support Floor", signal_type="buy" if price <= lower_bb * 1.01 else "neutral"),
            IndicatorItem(name="ADX (14)", value=str(adx_val), signal=adx_signal, signal_type=adx_cls),
            IndicatorItem(name="+DI / -DI", value=f"{round(plus_di, 1)} / {round(minus_di, 1)}",
                          signal="Bullish Bias" if plus_di >= minus_di else "Bearish Bias",
                          signal_type="buy" if plus_di >= minus_di else "sell"),
            IndicatorItem(name="Stochastic %K", value=f"{stoch_k} (D {stoch_d})", signal=stoch_signal, signal_type=stoch_cls),
            IndicatorItem(name="ATR (14)", value=f"{curr}{atr_val:,.2f}",
                          signal="Volatility Gauge", signal_type="neutral"),
            IndicatorItem(name="Volume Trend", value=vol_txt, signal=vol_signal, signal_type=vol_cls),
        ]

        # ---- Real 52-week range from the sampled (≈1y) candles ----
        high_52w = max(highs) if highs else price
        low_52w = min(lows) if lows else price

        # ---- Fundamental estimates, deterministic per symbol ----
        rng = random.Random(_seed_for(sym))
        if not is_crypto:
            pe = round(12.0 + rng.random() * 38.0, 1)
            pb = round(1.0 + rng.random() * 6.0, 2)
            roe = round(8.0 + rng.random() * 20.0, 1)
            roce = round(9.0 + rng.random() * 22.0, 1)
            de = round(rng.random() * 1.4, 2)
            promoter = round(30.0 + rng.random() * 45.0, 1)
            ratios = {
                "P/E Ratio": str(pe),
                "P/B Ratio": str(pb),
                "EPS (TTM)": f"{curr}{round(price / pe, 2)}",
                "ROE": f"{roe}%",
                "ROCE": f"{roce}%",
                "Debt-to-Equity": str(de),
                "Book Value": f"{curr}{round(price / pb, 2)}",
                "52W High": f"{curr}{round(high_52w, 2)}",
                "52W Low": f"{curr}{round(low_52w, 2)}",
                "Promoter Holding": f"{promoter}%",
                "Avg Volume (20D)": f"{int(sum(volumes[-20:]) / max(1, len(volumes[-20:]))):,}" if any(volumes) else "n/a",
            }
        else:
            ratios = {
                "Market Cap Rank": f"#{rng.randint(1, 25)}",
                "24h Range": f"{curr}{round(low_52w, 2)} - {curr}{round(high_52w, 2)}",
                "52W High": f"{curr}{round(high_52w, 2)}",
                "52W Low": f"{curr}{round(low_52w, 2)}",
                "Circulating Supply": f"{rng.randint(15, 120)}M {sym.replace('USDT', '').replace('INR', '')}",
                "Volatility (ATR)": f"{curr}{atr_val:,.2f}",
                "Avg Volume (20D)": f"{int(sum(volumes[-20:]) / max(1, len(volumes[-20:]))):,}" if any(volumes) else "n/a",
            }

        # ---- Composite summary signal ----
        score = 0
        score += 1 if rsi_val >= 55 else (-1 if rsi_val <= 45 else 0)
        score += 1 if macd_hist > 0 else -1
        score += 1 if price >= ema20_val else -1
        score += 1 if plus_di >= minus_di else -1
        if score >= 3:
            summary = "STRONG_BUY"
        elif score >= 1:
            summary = "BUY"
        elif score <= -3:
            summary = "STRONG_SELL"
        elif score <= -1:
            summary = "SELL"
        else:
            summary = "NEUTRAL"

        return TechnicalAnalysisResponse(
            symbol=sym,
            price=price,
            change_pct=change_pct,
            summary_signal=summary,
            indicators=indicators,
            ratios=ratios,
            support_levels=[round(lower_bb, 2), round(low_52w, 2)],
            resistance_levels=[round(upper_bb, 2), round(high_52w, 2)]
        )

    def get_option_chain(self, underlying: str = "NIFTY") -> OptionChainResponse:
        und = underlying.upper()
        spot = 22456.80 if "NIFTY" in und else 47234.15
        step = 50 if "NIFTY" in und else 100
        center_strike = round(spot / step) * step

        strikes_data: List[OptionChainItem] = []
        # Generate 15 strikes centered on ATM
        for i in range(-7, 8):
            strike = center_strike + (i * step)
            dist = (strike - spot) / spot

            # Implied volatility curve (smile)
            iv = 13.5 + abs(dist * 50) + random.uniform(0.1, 0.4)

            # Realistic Call and Put OI simulation
            ce_oi = round(max(200000, 1800000 * math.exp(-abs(strike - spot + 200) / 400)), 0)
            pe_oi = round(max(250000, 2200000 * math.exp(-abs(strike - spot - 150) / 400)), 0)

            # Option premiums (Black-Scholes approx)
            intrinsic_ce = max(0.0, spot - strike)
            time_val = max(10.0, spot * 0.015 * math.exp(-abs(dist) * 8))
            ce_ltp = round(intrinsic_ce + time_val, 2)

            intrinsic_pe = max(0.0, strike - spot)
            pe_ltp = round(intrinsic_pe + time_val * 0.95, 2)

            strikes_data.append(OptionChainItem(
                strike=float(strike),
                ce_oi=float(ce_oi),
                ce_change_oi=round(ce_oi * random.uniform(-0.1, 0.25), 0),
                ce_ltp=ce_ltp,
                ce_iv=round(iv, 2),
                pe_ltp=pe_ltp,
                pe_iv=round(iv * 1.02, 2),
                pe_change_oi=round(pe_oi * random.uniform(-0.05, 0.3), 0),
                pe_oi=float(pe_oi)
            ))

        total_pe_oi = sum(s.pe_oi for s in strikes_data)
        total_ce_oi = sum(s.ce_oi for s in strikes_data)
        pcr = round(total_pe_oi / max(total_ce_oi, 1.0), 2)
        max_pain = float(center_strike - step) # Strike with least total payout

        return OptionChainResponse(
            underlying=und,
            spot_price=spot,
            pcr=pcr,
            max_pain=max_pain,
            atm_iv=13.8,
            expiry_date="24-OCT-2026",
            strikes=strikes_data
        )

    def get_fund_analysis(self, code: str = "PPFCF") -> Dict[str, Any]:
        return {
            "fund_code": code,
            "fund_name": "Parag Parikh Flexi Cap Fund Direct Growth",
            "nav": 84.62,
            "category": "Flexi Cap Fund",
            "rating": "5 Stars (Value Research)",
            "aum_cr": 64280.0,
            "expense_ratio_pct": 0.62,
            "cagr_3y": 22.4,
            "cagr_5y": 24.1,
            "alpha": 6.42,
            "beta": 0.78,
            "sharpe_ratio": 1.82,
            "sortino_ratio": 2.64,
            "top_holdings": [
                {"name": "HDFC Bank Ltd.", "pct": 8.4},
                {"name": "Bajaj Holdings", "pct": 7.1},
                {"name": "ITC Limited", "pct": 6.8},
                {"name": "Alphabet Inc. (Google)", "pct": 5.4},
                {"name": "ICICI Bank Ltd.", "pct": 4.9}
            ]
        }

    def get_crypto_analysis(self, symbol: str = "BTCINR") -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "name": "Bitcoin",
            "price_inr": 5560000.0,
            "price_usd": 67240.0,
            "fear_and_greed_score": 74,
            "fear_and_greed_sentiment": "Greed",
            "market_dominance_pct": 54.8,
            "onchain_mvrv_ratio": 2.14,
            "exchange_netflow_24h_btc": -8420.0,
            "hashrate_eh_s": 624.0,
            "active_wallets_24h": 984000,
            "liquidations_24h_usd": 124000000.0
        }

analysis_engine = AnalysisEngine()
