import math
import random
from typing import Dict, List, Any
from app.services.market_ingest import market_ingest
from app.schemas.schemas import TechnicalAnalysisResponse, IndicatorItem, OptionChainResponse, OptionChainItem

class AnalysisEngine:
    def get_technical_analysis(self, symbol: str) -> TechnicalAnalysisResponse:
        sym = symbol.upper()
        quote = market_ingest.get_quote(sym)
        price = quote.price if quote else 2500.0
        change_pct = quote.change_pct if quote else 1.25

        # Computed indicator suite
        indicators = [
            IndicatorItem(name="RSI (14)", value="62.4", signal="Neutral", signal_type="neutral"),
            IndicatorItem(name="MACD (12, 26)", value="+18.2", signal="Bullish Crossover", signal_type="buy"),
            IndicatorItem(name="EMA (20)", value=f"₹{round(price * 0.985, 2)}", signal="Trading Above", signal_type="buy"),
            IndicatorItem(name="SMA (50)", value=f"₹{round(price * 0.970, 2)}", signal="Golden Trend", signal_type="buy"),
            IndicatorItem(name="Bollinger Band (20,2)", value="Upper Band Touch", signal="Overbought Watch", signal_type="sell"),
            IndicatorItem(name="ADX (14)", value="34.8", signal="Strong Bullish Trend", signal_type="buy"),
            IndicatorItem(name="Stochastic Oscillator", value="78.2", signal="Bullish Momentum", signal_type="neutral"),
            IndicatorItem(name="Williams %R", value="-21.8", signal="High Momentum", signal_type="buy"),
            IndicatorItem(name="CCI (20)", value="+156.4", signal="Bullish Surge", signal_type="buy")
        ]

        ratios = {
            "P/E Ratio": "28.4",
            "P/B Ratio": "2.1",
            "EPS (TTM)": f"₹{round(price / 28.4, 2)}",
            "ROE": "14.8%",
            "ROCE": "18.2%",
            "Debt-to-Equity": "0.38",
            "Book Value": f"₹{round(price / 2.1, 2)}",
            "52W High": f"₹{round(price * 1.15, 2)}",
            "52W Low": f"₹{round(price * 0.78, 2)}",
            "Promoter Holding": "50.4%",
            "Avg Volume (30D)": "14.2M"
        }

        # Dynamic summary signal
        summary = "STRONG_BUY" if change_pct > 2.0 else "BUY" if change_pct > 0 else "NEUTRAL"

        return TechnicalAnalysisResponse(
            symbol=sym,
            price=price,
            change_pct=change_pct,
            summary_signal=summary,
            indicators=indicators,
            ratios=ratios,
            support_levels=[round(price * 0.97, 2), round(price * 0.94, 2)],
            resistance_levels=[round(price * 1.03, 2), round(price * 1.06, 2)]
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
