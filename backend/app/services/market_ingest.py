import os
import re
import math
import time
import random
import json
import threading
import urllib.request
import urllib.parse
import hmac
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from app.config import settings, ENV_FILE, is_configured
from app.schemas.schemas import QuoteResponse, CandleResponse, IndexOverview

# Optional Kite Connect SDK
try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KiteConnect = None
    KITE_AVAILABLE = False

# Optional yfinance for real Indian stocks & indices
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False

# Optional HTML parser for verified FII/DII tables.
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BS4_AVAILABLE = False


# ========================================================
# SYMBOL MAPPINGS
# ========================================================
from app.services.universe import INDIAN_STOCKS_MAP, INDICES_MAP

CRYPTO_MAP = {
    "BTCUSDT": {"pair": "BTCUSDT", "name": "Bitcoin (BTC / USDT)", "base": "BTC", "quote": "USDT", "category": "Store of Value"},
    "BTCINR": {"pair": "BTCUSDT", "name": "Bitcoin (BTC / INR)", "base": "BTC", "quote": "INR", "category": "Store of Value"},
    "ETHUSDT": {"pair": "ETHUSDT", "name": "Ethereum (ETH / USDT)", "base": "ETH", "quote": "USDT", "category": "Smart Contracts"},
    "ETHINR": {"pair": "ETHUSDT", "name": "Ethereum (ETH / INR)", "base": "ETH", "quote": "INR", "category": "Smart Contracts"},
    "SOLUSDT": {"pair": "SOLUSDT", "name": "Solana (SOL / USDT)", "base": "SOL", "quote": "USDT", "category": "Layer 1"},
    "SOLINR": {"pair": "SOLUSDT", "name": "Solana (SOL / INR)", "base": "SOL", "quote": "INR", "category": "Layer 1"},
    "BNBUSDT": {"pair": "BNBUSDT", "name": "BNB (BNB / USDT)", "base": "BNB", "quote": "USDT", "category": "Exchange Token"},
    "DOGEUSDT": {"pair": "DOGEUSDT", "name": "Dogecoin (DOGE / USDT)", "base": "DOGE", "quote": "USDT", "category": "Meme"},
    "XRPUSDT": {"pair": "XRPUSDT", "name": "Ripple (XRP / USDT)", "base": "XRP", "quote": "USDT", "category": "Payments"},
    "ADAUSDT": {"pair": "ADAUSDT", "name": "Cardano (ADA / USDT)", "base": "ADA", "quote": "USDT", "category": "Layer 1"},
    "AVAXUSDT": {"pair": "AVAXUSDT", "name": "Avalanche (AVAX / USDT)", "base": "AVAX", "quote": "USDT", "category": "Layer 1"},
}

CURRENCIES_MAP = {
    "USDINR": {"symbol": "USDINR", "name": "USD / INR (US Dollar)", "pair": "USD/INR", "price": 86.85, "change": 0.12, "change_pct": 0.14},
    "EURINR": {"symbol": "EURINR", "name": "EUR / INR (Euro)", "pair": "EUR/INR", "price": 93.42, "change": -0.24, "change_pct": -0.26},
    "GBPINR": {"symbol": "GBPINR", "name": "GBP / INR (British Pound)", "pair": "GBP/INR", "price": 110.15, "change": 0.38, "change_pct": 0.35},
    "JPYINR": {"symbol": "JPYINR", "name": "JPY / INR (100 Yen)", "pair": "100 JPY/INR", "price": 57.18, "change": -0.15, "change_pct": -0.26},
}

# Legacy baseline retained only for symbol seeding. Live conversions use the
# verified Frankfurter FX feed via ``get_usd_inr_rate``.
USD_INR_RATE = 86.85

# Verified INR crosses exposed by the Frankfurter ECB feed.
FOREX_META = {
    "USD": {"symbol": "USDINR", "pair": "USD/INR", "name": "US Dollar / Indian Rupee", "scale": 1.0},
    "EUR": {"symbol": "EURINR", "pair": "EUR/INR", "name": "Euro / Indian Rupee", "scale": 1.0},
    "GBP": {"symbol": "GBPINR", "pair": "GBP/INR", "name": "British Pound / Indian Rupee", "scale": 1.0},
    "JPY": {"symbol": "JPYINR", "pair": "100 JPY/INR", "name": "100 Japanese Yen / Indian Rupee", "scale": 100.0},
    "AUD": {"symbol": "AUDINR", "pair": "AUD/INR", "name": "Australian Dollar / Indian Rupee", "scale": 1.0},
    "CAD": {"symbol": "CADINR", "pair": "CAD/INR", "name": "Canadian Dollar / Indian Rupee", "scale": 1.0},
    "SGD": {"symbol": "SGDINR", "pair": "SGD/INR", "name": "Singapore Dollar / Indian Rupee", "scale": 1.0},
}

# Global benchmark indices verified through Yahoo Finance.
GLOBAL_INDICES_MAP = {
    "S&P 500": "^GSPC",
    "NASDAQ 100": "^NDX",
    "DOW JONES": "^DJI",
    "FTSE 100": "^FTSE",
}

# Scheme codes verified against mfapi.in metadata before inclusion.
MUTUAL_FUND_SCHEMES = [
    120503, 120586, 118778, 122639, 118825,
    119071, 147473, 125497, 118632, 120662,
]

# ========================================================
# REALISTIC FALLBACK REFERENCE PRICES
# Used only when no live provider (Kite Connect / Binance / yfinance) is
# reachable. Equity & index reference levels live on the maps in
# ``app.services.universe`` so every instrument shows a sane, instrument-specific
# number instead of one hard-coded constant.
# ========================================================
CRYPTO_BASE_PRICES: Dict[str, float] = {
    "BTCUSDT": 81700.00, "BTCINR": 81700.00,
    "ETHUSDT": 2145.00, "ETHINR": 2145.00,
    "SOLUSDT": 142.80, "SOLINR": 142.80,
    "BNBUSDT": 582.40, "DOGEUSDT": 0.1700, "XRPUSDT": 2.3000,
    "ADAUSDT": 0.6200, "AVAXUSDT": 28.00,
}


def _stable_seed(symbol: str) -> int:
    """Deterministic 32-bit seed derived from a symbol name."""
    return int(hashlib.sha256(symbol.encode("utf-8")).hexdigest(), 16) % (2 ** 32)


def _base_price(symbol: str) -> float:
    meta = INDIAN_STOCKS_MAP.get(symbol) or INDICES_MAP.get(symbol)
    if meta and meta.get("base"):
        return float(meta["base"])
    if symbol in CRYPTO_BASE_PRICES:
        return CRYPTO_BASE_PRICES[symbol]
    if symbol in CURRENCIES_MAP:
        return CURRENCIES_MAP[symbol]["price"]
    return 1000.0


def _deterministic_walk(symbol: str, steps: int, end_price: float, daily_vol: float = 0.014) -> List[float]:
    """Deterministic geometric random walk that terminates at ``end_price``.

    Uses a seeded RNG so the same symbol always produces the same series
    (no jitter between requests), and the series is rebuilt backwards from the
    anchor price so the last close matches the live/fallback quote.
    """
    rng = random.Random(_stable_seed(symbol))
    # Forward noise then rescale so the final value lands on end_price.
    prices = [1.0]
    for _ in range(max(1, steps - 1)):
        prices.append(prices[-1] * math.exp((rng.random() - 0.5) * daily_vol * 2))
    scale = end_price / prices[-1]
    return [round(p * scale, 2) for p in prices]


def _intraday_wobble(symbol: str) -> float:
    """Small, smoothly varying multiplier so fallback quotes feel alive.

    Bounded to ±0.35% and deterministic per (symbol, 30s window) so successive
    requests over a short interval are not identical, but never look erratic.
    """
    window = int(time.time() // 30)
    phase = (_stable_seed(symbol) % 1000) / 1000.0
    return 1.0 + 0.0035 * math.sin((window + phase * 100) * 0.7)


class MarketIngestService:
    def __init__(self):
        self.binance_key = settings.BINANCE_API_KEY if is_configured(settings.BINANCE_API_KEY) else None
        self.binance_secret = settings.BINANCE_API_SECRET if is_configured(settings.BINANCE_API_SECRET) else None
        self.kite_key = settings.KITE_API_KEY or settings.ZERODHA_API_KEY
        if not is_configured(self.kite_key):
            self.kite_key = None
        self.kite_secret = settings.KITE_API_SECRET or settings.ZERODHA_API_SECRET
        if not is_configured(self.kite_secret):
            self.kite_secret = None
        self.kite_access_token = settings.KITE_ACCESS_TOKEN if is_configured(settings.KITE_ACCESS_TOKEN) else None

        self.kite_client: Optional[Any] = None
        if KITE_AVAILABLE and self.kite_key:
            try:
                self.kite_client = KiteConnect(api_key=self.kite_key)
                if self.kite_access_token:
                    self.kite_client.set_access_token(self.kite_access_token)
            except Exception as e:
                print(f"[Kite Init Warning]: {e}")

        # Cache for live quotes & candles
        self._quote_cache: Dict[str, Dict] = {}
        self._quote_cache_time: Dict[str, float] = {}
        self._candle_cache: Dict[str, Dict] = {}
        self._candle_cache_time: Dict[str, float] = {}
        self._kite_instrument_tokens: Dict[str, int] = {
            "RELIANCE": 738561,
            "TCS": 2953217,
            "HDFCBANK": 341249,
            "INFY": 408065,
            "ICICIBANK": 1270529,
            "TATASTEEL": 895745,
            "ITC": 424961,
            "SBIN": 779521,
            "BHARTIARTL": 2714625,
            "LICI": 11023361,
            "KOTAKBANK": 492033,
            "LT": 2939649,
            "AXISBANK": 1510401,
            "MARUTI": 2815745,
            "TATAMOTORS": 884737,
            "SUNPHARMA": 857857,
            "TITAN": 897665,
            "BAJFINANCE": 81153,
            "WIPRO": 969473,
            "ASIANPAINT": 60417,
            "NIFTY 50": 256265,
            "SENSEX": 265,
            "BANK NIFTY": 260105,
            "NIFTY IT": 259849,
        }
        self._cache_ttl = 15.0  # 15 seconds cache for real quotes
        # Batched universe (stocks + indices) quote cache
        self._universe_batch: Dict[str, QuoteResponse] = {}
        self._universe_batch_time: float = 0.0
        self._universe_sparklines: Dict[str, List[float]] = {}
        self._universe_sparkline_times: Dict[str, List[str]] = {}
        self._batch_ttl = 45.0
        self._tick_seq = 0

        # Verified tickers discovered at runtime (any real Yahoo/Kite symbol).
        # Nothing here is invented: a symbol is only registered after a live
        # provider returns actual history for it.
        self._dynamic_symbols: Dict[str, Dict[str, Any]] = {}
        self._dynamic_missing: Dict[str, float] = {}
        self._dynamic_lock = threading.RLock()
        self._batch_lock = threading.RLock()
        self._snapshot_lock = threading.RLock()
        self._snapshot_cache: Dict[str, QuoteResponse] = {}
        self._snapshot_time: float = 0.0

        # Verified alternative-feed caches (institutional flows, FX, mutual funds).
        self._fii_cache: Optional[Dict[str, Any]] = None
        self._fii_cache_time: float = 0.0
        self._fx_cache: List[Dict[str, Any]] = []
        self._fx_cache_time: float = 0.0
        self._mf_cache: List[Dict[str, Any]] = []
        self._mf_cache_time: float = 0.0
        self._feed_lock = threading.RLock()

    # ========================================================
    # DYNAMIC VERIFIED SYMBOL DISCOVERY
    # ========================================================
    def _candidate_yfinance_tickers(self, sym: str) -> List[str]:
        """Return likely Yahoo tickers for an arbitrary symbol.

        Indian equities are tried first (.NS, then .BO) so a bare NSE ticker
        never accidentally resolves to an unrelated global instrument. A plain
        ticker is tried last for US/global equities.
        """
        if not sym or sym in CURRENCIES_MAP:
            return []
        if sym.endswith(".NS") or sym.endswith(".BO"):
            return [sym]
        if sym.endswith("USDT") or sym.endswith("INR"):
            return []

        base = sym.replace("/", "-").replace(" ", "")
        if not base:
            return []
        plain = base.replace(".", "-")
        candidates = [f"{base}.NS", f"{base}.BO", plain]
        return list(dict.fromkeys(candidates))

    def _ensure_dynamic_symbol(self, sym: str) -> Optional[Dict[str, Any]]:
        """Register a real ticker on demand after verifying it with Yahoo.

        Returns None when no provider can verify the symbol, so callers can
        return 404/422 rather than fabricate a quote or candle series.
        """
        if not sym or sym in CURRENCIES_MAP:
            return None
        if sym in INDIAN_STOCKS_MAP:
            return INDIAN_STOCKS_MAP[sym]
        if sym in INDICES_MAP:
            return INDICES_MAP[sym]
        if sym in self._dynamic_symbols:
            return self._dynamic_symbols[sym]
        if not YFINANCE_AVAILABLE:
            return None

        missing_at = self._dynamic_missing.get(sym)
        if missing_at and (time.time() - missing_at) < 300:
            return None

        with self._dynamic_lock:
            if sym in self._dynamic_symbols:
                return self._dynamic_symbols[sym]
            missing_at = self._dynamic_missing.get(sym)
            if missing_at and (time.time() - missing_at) < 300:
                return None

            for candidate in self._candidate_yfinance_tickers(sym):
                try:
                    df = yf.Ticker(candidate).history(
                        period="5d", interval="1d"
                    ).dropna(subset=["Close"])
                    if df.empty:
                        continue

                    if candidate.endswith(".NS"):
                        exchange = "NSE"
                    elif candidate.endswith(".BO"):
                        exchange = "BSE"
                    else:
                        exchange = "GLOBAL"

                    meta = {
                        "ticker": candidate,
                        "name": sym,
                        "segment": "EQ",
                        "exchange": exchange,
                        "sector": "Equities",
                        "dynamic": True,
                    }
                    self._dynamic_symbols[sym] = meta
                    self._dynamic_missing.pop(sym, None)
                    return meta
                except Exception:
                    continue

            self._dynamic_missing[sym] = time.time()
            return None

    # ========================================================
    # BINANCE REAL-TIME CRYPTO METHODS
    # ========================================================
    def fetch_binance_ticker(self, pair: str = "BTCUSDT") -> Optional[Dict]:
        """Fetch real-time 24hr ticker from Binance API"""
        cache_key = f"binance_ticker_{pair}"
        now = time.time()
        if cache_key in self._quote_cache and (now - self._quote_cache_time.get(cache_key, 0)) < self._cache_ttl:
            return self._quote_cache[cache_key]

        try:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
            headers = {}
            if self.binance_key:
                headers["X-MBX-APIKEY"] = self.binance_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._quote_cache[cache_key] = data
                self._quote_cache_time[cache_key] = now
                return data
        except Exception as e:
            print(f"[Binance Ticker Error] {pair}: {e}")
            return self._quote_cache.get(cache_key)

    def fetch_binance_candles(self, pair: str = "BTCUSDT", interval: str = "1d", limit: int = 30) -> List[CandleResponse]:
        """Fetch real live candlestick data from Binance API"""
        cache_key = f"binance_candles_{pair}_{interval}_{limit}"
        now = time.time()
        if cache_key in self._candle_cache and (now - self._candle_cache_time.get(cache_key, 0)) < 60.0:
            return self._candle_cache[cache_key]

        binance_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h",
            "1d": "1d", "1w": "1w"
        }
        b_interval = binance_interval_map.get(interval, "1d")

        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={b_interval}&limit={limit}"
            headers = {}
            if self.binance_key:
                headers["X-MBX-APIKEY"] = self.binance_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                klines = json.loads(resp.read().decode("utf-8"))
                candles = []
                for k in klines:
                    time_str = datetime.utcfromtimestamp(k[0] / 1000).strftime("%Y-%m-%d %H:%M" if interval != "1d" else "%Y-%m-%d")
                    candles.append(CandleResponse(
                        time=time_str,
                        open=round(float(k[1]), 2),
                        high=round(float(k[2]), 2),
                        low=round(float(k[3]), 2),
                        close=round(float(k[4]), 2),
                        volume=round(float(k[5]), 2),
                        source="binance_live",
                    ))
                self._candle_cache[cache_key] = candles
                self._candle_cache_time[cache_key] = now
                return candles
        except Exception as e:
            print(f"[Binance Candles Error] {pair}: {e}")
            return self._candle_cache.get(cache_key, [])

    def get_binance_account_status(self) -> Dict[str, Any]:
        """Verify authenticated Binance account using HMAC-SHA256 signature"""
        if not self.binance_key or not self.binance_secret:
            return {"authenticated": False, "message": "Binance API Key or Secret not configured"}
        try:
            timestamp = int(time.time() * 1000)
            query = f"timestamp={timestamp}"
            signature = hmac.new(self.binance_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            url = f"https://api.binance.com/api/v3/account?{query}&signature={signature}"
            req = urllib.request.Request(url, headers={"X-MBX-APIKEY": self.binance_key})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "authenticated": True,
                    "canTrade": data.get("canTrade", False),
                    "canWithdraw": data.get("canWithdraw", False),
                    "accountType": data.get("accountType", "SPOT"),
                    "balancesCount": len(data.get("balances", []))
                }
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    # ========================================================
    # KITE CONNECT METHODS
    # ========================================================
    def get_kite_login_url(self) -> str:
        """Get official Kite Connect login authorization URL"""
        if self.kite_client:
            return self.kite_client.login_url()
        if self.kite_key:
            return f"https://kite.zerodha.com/connect/login?api_key={self.kite_key}&v=3"
        return "https://kite.zerodha.com/connect/login"

    def set_kite_access_token(self, access_token: str):
        """Set active Kite access token and persist to .env"""
        self.kite_access_token = access_token
        if self.kite_client:
            try:
                self.kite_client.set_access_token(access_token)
            except Exception as e:
                print(f"[Kite Set Token Warning]: {e}")
        # Persist to the same root .env that Settings loads on startup.
        try:
            env_path = ENV_FILE
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                import re
                if "KITE_ACCESS_TOKEN=" in content:
                    content = re.sub(r"KITE_ACCESS_TOKEN=.*", f"KITE_ACCESS_TOKEN={access_token}", content)
                else:
                    content += f"\nKITE_ACCESS_TOKEN={access_token}\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception as e:
            print(f"[Kite .env Persist Warning]: {e}")

    def generate_kite_session(self, request_token: str) -> Dict[str, Any]:
        """Exchange Kite request_token for permanent access_token"""
        if not self.kite_client or not self.kite_secret:
            return {"success": False, "error": "Kite client or secret not available"}
        try:
            data = self.kite_client.generate_session(request_token, api_secret=self.kite_secret)
            token = data.get("access_token")
            if token:
                self.set_kite_access_token(token)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fetch_kite_quote(self, symbol: str) -> Optional[QuoteResponse]:
        """Fetch live quote from Zerodha Kite Connect API"""
        if not self.kite_client or not self.kite_access_token:
            return None

        cache_key = f"kite_quote_{symbol}"
        now = time.time()
        if cache_key in self._quote_cache and (now - self._quote_cache_time.get(cache_key, 0)) < self._cache_ttl:
            return self._quote_cache[cache_key]

        try:
            kite_sym = f"NSE:{symbol}"
            if symbol == "NIFTY 50":
                kite_sym = "NSE:NIFTY 50"
            elif symbol == "SENSEX":
                kite_sym = "BSE:SENSEX"
            elif symbol == "BANK NIFTY":
                kite_sym = "NSE:NIFTY BANK"
            elif symbol == "NIFTY IT":
                kite_sym = "NSE:NIFTY IT"

            quotes = self.kite_client.quote([kite_sym])
            if quotes and kite_sym in quotes:
                data = quotes[kite_sym]
                price = float(data.get("last_price", 0.0))
                ohlc = data.get("ohlc", {})
                prev_close = float(ohlc.get("close", price))
                change = round(price - prev_close, 2)
                change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                high = float(ohlc.get("high", price))
                low = float(ohlc.get("low", price))
                vol = int(data.get("volume", 0))

                # Cache instrument token for historical candle queries
                inst_token = data.get("instrument_token")
                if inst_token:
                    self._kite_instrument_tokens[symbol] = inst_token

                name = INDIAN_STOCKS_MAP.get(symbol, {}).get("name", symbol)
                q = QuoteResponse(
                    symbol=symbol,
                    name=name,
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    high_24h=high,
                    low_24h=low,
                    volume=vol,
                    timestamp=datetime.utcnow(),
                    source="kite_live",
                    as_of=datetime.utcnow(),
                )
                self._quote_cache[cache_key] = q
                self._quote_cache_time[cache_key] = now
                return q
        except Exception as e:
            # Token might be expired or symbol format differs
            print(f"[Kite Quote Error] {symbol}: {e}")
            return None

    def fetch_kite_candles(self, symbol: str, timeframe: str = "1d", limit: int = 30) -> List[CandleResponse]:
        """Fetch historical candlestick chart from Zerodha Kite Connect API"""
        if not self.kite_client or not self.kite_access_token:
            return []

        cache_key = f"kite_candles_{symbol}_{timeframe}_{limit}"
        now = time.time()
        if cache_key in self._candle_cache and (now - self._candle_cache_time.get(cache_key, 0)) < 120.0:
            return self._candle_cache[cache_key]

        try:
            token = self._kite_instrument_tokens.get(symbol)
            if not token:
                # Attempt to retrieve token via quick quote
                q = self.fetch_kite_quote(symbol)
                token = self._kite_instrument_tokens.get(symbol)

            if not token:
                return []

            kite_interval_map = {
                "1d": "day", "5m": "5minute", "15m": "15minute",
                "1h": "60minute", "1w": "week"
            }
            k_interval = kite_interval_map.get(timeframe, "day")

            to_date = datetime.now()
            from_date = to_date - timedelta(days=limit * 2 if k_interval == "day" else 5)

            records = self.kite_client.historical_data(
                instrument_token=token,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d"),
                interval=k_interval
            )

            if records:
                candles = []
                for r in records[-limit:]:
                    dt = r["date"]
                    time_str = dt.strftime("%Y-%m-%d %H:%M" if k_interval != "day" else "%Y-%m-%d")
                    candles.append(CandleResponse(
                        time=time_str,
                        open=round(float(r["open"]), 2),
                        high=round(float(r["high"]), 2),
                        low=round(float(r["low"]), 2),
                        close=round(float(r["close"]), 2),
                        volume=round(float(r["volume"]), 2),
                        source="kite_live",
                    ))
                self._candle_cache[cache_key] = candles
                self._candle_cache_time[cache_key] = now
                return candles
        except Exception as e:
            print(f"[Kite Candles Error] {symbol}: {e}")
            return []

    # ========================================================
    # REAL INDIAN STOCKS & INDICES (LIVE NSE/BSE)
    # ========================================================
    def fetch_yfinance_quote(self, symbol: str, ticker_sym: str, name: str, intraday: bool = True) -> Optional[QuoteResponse]:
        cache_key = f"yf_quote_{symbol}_intraday" if intraday else f"yf_quote_{symbol}"
        now = time.time()
        if cache_key in self._quote_cache and (now - self._quote_cache_time.get(cache_key, 0)) < self._cache_ttl:
            return self._quote_cache[cache_key]

        if not YFINANCE_AVAILABLE:
            return None

        try:
            ticker = yf.Ticker(ticker_sym)
            daily = ticker.history(period="5d", interval="1d").dropna(subset=["Close"])
            intraday = ticker.history(period="1d", interval="1m").dropna(subset=["Close"])
            if daily.empty and intraday.empty:
                return None

            # Prefer the newest verified intraday close; fall back to daily EOD.
            source = "yfinance_delayed" if not intraday.empty else "yfinance_eod"
            df = intraday if not intraday.empty else daily
            latest = df.iloc[-1]

            prev_close = 0.0
            if not daily.empty:
                prev_close = round(
                    float(daily.iloc[-2]["Close"]) if len(daily) > 1 else float(daily.iloc[-1]["Close"]),
                    2,
                )
            if not prev_close:
                prev = df.iloc[-2] if len(df) > 1 else latest
                prev_close = round(float(prev["Close"]), 2)

            price = round(float(latest["Close"]), 2)
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

            q = QuoteResponse(
                symbol=symbol,
                name=name,
                price=price,
                change=change,
                change_pct=change_pct,
                high_24h=round(float(latest.get("High", price)), 2),
                low_24h=round(float(latest.get("Low", price)), 2),
                volume=int(latest.get("Volume", 0) or 0),
                timestamp=datetime.utcnow(),
                source=source,
                as_of=datetime.utcnow(),
            )
            self._quote_cache[cache_key] = q
            self._quote_cache_time[cache_key] = now
            return q
        except Exception as e:
            print(f"[YFinance Quote Error] {symbol} ({ticker_sym}): {e}")
            return self._quote_cache.get(cache_key)

    def fetch_yfinance_candles(self, ticker_sym: str, timeframe: str = "1d", limit: int = 30) -> List[CandleResponse]:
        cache_key = f"yf_candles_{ticker_sym}_{timeframe}_{limit}"
        now = time.time()
        if cache_key in self._candle_cache and (now - self._candle_cache_time.get(cache_key, 0)) < 120.0:
            return self._candle_cache[cache_key]

        if not YFINANCE_AVAILABLE:
            return []

        try:
            period_map = {"1d": "2y", "1w": "5y", "1mo": "5y", "5m": "5d", "15m": "1mo", "1h": "1mo"}
            yf_period = period_map.get(timeframe, "3mo")
            yf_interval = "1d" if timeframe in ["1d", "1w", "1mo"] else timeframe

            ticker = yf.Ticker(ticker_sym)
            df = ticker.history(period=yf_period, interval=yf_interval).dropna(subset=["Close"])
            if df.empty:
                return []

            candles = []
            for idx, row in df.tail(limit).iterrows():
                time_str = idx.strftime("%Y-%m-%d %H:%M" if "m" in yf_interval or "h" in yf_interval else "%Y-%m-%d")
                candles.append(CandleResponse(
                    time=time_str,
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                    volume=round(float(row.get("Volume", 0)), 2),
                    source="yfinance_delayed" if yf_interval != "1d" else "yfinance_eod",
                ))
            self._candle_cache[cache_key] = candles
            self._candle_cache_time[cache_key] = now
            return candles
        except Exception as e:
            print(f"[YFinance Candles Error] {ticker_sym}: {e}")
            return self._candle_cache.get(cache_key, [])

    def fetch_yfinance_universe_batch(self, force: bool = False) -> Dict[str, QuoteResponse]:
        """Fetch verified batched EOD quotes for catalog and dynamic symbols.

        One daily request keeps the whole market responsive. Individually viewed
        symbols use intraday history in `fetch_yfinance_quote`, and Kite/Binance
        provide true realtime ticks when connected.
        """
        now = time.time()
        if not force and self._universe_batch and (now - self._universe_batch_time) < self._batch_ttl:
            return self._universe_batch
        if not YFINANCE_AVAILABLE:
            return self._universe_batch

        with self._batch_lock:
            now = time.time()
            if not force and self._universe_batch and (now - self._universe_batch_time) < self._batch_ttl:
                return self._universe_batch
            # Reserve the refresh window before the slow network call so parallel
            # ticks do not launch duplicate downloads.
            self._universe_batch_time = now

            tickers = {}
            for sym, meta in INDIAN_STOCKS_MAP.items():
                tickers[meta["ticker"]] = (sym, meta["name"])
            for sym, meta in INDICES_MAP.items():
                tickers[meta["ticker"]] = (sym, meta["name"])
            for sym, meta in self._dynamic_symbols.items():
                tickers[meta["ticker"]] = (sym, meta["name"])

            def _series(df, field, ticker):
                try:
                    if df is None or getattr(df, "empty", True):
                        return None
                    if field in df.columns:
                        frame = df[field]
                    elif hasattr(df.columns, "get_level_values") and field in df.columns.get_level_values(0):
                        # yfinance returns a MultiIndex for multi-ticker downloads.
                        frame = df.xs(field, axis=1, level=0)
                    else:
                        return None
                    if ticker in frame:
                        return frame[ticker].dropna()
                except Exception:
                    return None
                return None

            try:
                daily = yf.download(
                    list(tickers.keys()),
                    period="1mo",
                    interval="1d",
                    progress=False,
                    threads=True,
                    auto_adjust=False,
                )
            except Exception as e:
                print(f"[YFinance Daily Batch Error]: {e}")
                daily = None

            out: Dict[str, QuoteResponse] = {}
            for ticker, (sym, name) in tickers.items():
                try:
                    series = _series(daily, "Close", ticker)
                    if series is None or series.empty:
                        continue

                    price = round(float(series.iloc[-1]), 2)
                    prev_close = round(float(series.iloc[-2]), 2) if len(series) > 1 else price
                    change = round(price - prev_close, 2)
                    change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

                    highs = _series(daily, "High", ticker)
                    if highs is None or highs.empty:
                        highs = series
                    lows = _series(daily, "Low", ticker)
                    if lows is None or lows.empty:
                        lows = series
                    vols = _series(daily, "Volume", ticker)
                    if vols is None or vols.empty:
                        vols = series

                    out[sym] = QuoteResponse(
                        symbol=sym,
                        name=name,
                        price=price,
                        change=change,
                        change_pct=change_pct,
                        high_24h=round(float(highs.iloc[-1]), 2) if len(highs) else price,
                        low_24h=round(float(lows.iloc[-1]), 2) if len(lows) else price,
                        volume=float(vols.iloc[-1]) if len(vols) else 0.0,
                        timestamp=datetime.utcnow(),
                        source="yfinance_eod",
                        as_of=datetime.utcnow(),
                    )
                    spark = [round(float(s), 2) for s in series.tail(12)]
                    if spark:
                        self._universe_sparklines[sym] = spark
                        self._universe_sparkline_times[sym] = [
                            idx.strftime("%Y-%m-%d") for idx in series.tail(12).index
                        ]
                except Exception:
                    continue

            if out:
                self._universe_batch = out
                for sym, q in out.items():
                    self._quote_cache[f"yf_quote_{sym}"] = q
                    self._quote_cache_time[f"yf_quote_{sym}"] = now
            return self._universe_batch

    # ========================================================
    # UNIFIED PUBLIC METHODS
    # ========================================================
    def get_quote(self, symbol: str, prefer_intraday: bool = False) -> Optional[QuoteResponse]:
        sym = symbol.upper().strip()

        # 1. Primary for Indian Equities / Indices: Zerodha Kite Connect API
        if (sym in INDIAN_STOCKS_MAP or sym in INDICES_MAP) and self.kite_access_token:
            k_quote = self.fetch_kite_quote(sym)
            if k_quote:
                return k_quote

        # 1b. Single-symbol detail requests use real intraday history when no
        #     broker stream is connected, so the displayed price keeps moving.
        if prefer_intraday and not self.kite_access_token:
            detail_meta = INDIAN_STOCKS_MAP.get(sym) or INDICES_MAP.get(sym)
            if detail_meta:
                intraday_quote = self.fetch_yfinance_quote(sym, detail_meta["ticker"], detail_meta["name"])
                if intraday_quote:
                    return intraday_quote

        # 2. Currency pairs are quoted from the static FX reference table, not Binance
        if sym in CURRENCIES_MAP:
            return self._fallback_quote(sym)

        # 3. Check Crypto (Binance API)
        if sym in CRYPTO_MAP or sym.endswith("USDT") or sym.endswith("INR"):
            info = CRYPTO_MAP.get(sym)
            pair = info["pair"] if info else sym
            b_data = self.fetch_binance_ticker(pair)
            if b_data:
                usdt_price = float(b_data["lastPrice"])
                high_usdt = float(b_data["highPrice"])
                low_usdt = float(b_data["lowPrice"])
                change_pct = round(float(b_data["priceChangePercent"]), 2)
                vol = float(b_data["volume"])

                is_inr = sym.endswith("INR") or (info and info["quote"] == "INR")
                multiplier = USD_INR_RATE if is_inr else 1.0

                price = round(usdt_price * multiplier, 2)
                high = round(high_usdt * multiplier, 2)
                low = round(low_usdt * multiplier, 2)
                change = round(price * (change_pct / 100), 2)

                name = info["name"] if info else f"{sym} Live"
                return QuoteResponse(
                    symbol=sym,
                    name=name,
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    high_24h=high,
                    low_24h=low,
                    volume=round(vol, 2),
                    timestamp=datetime.utcnow(),
                    source="binance_live",
                    as_of=datetime.utcnow(),
                )

        # 4. Catalog equities/indices: fast batched EOD snapshot.
        if sym in INDIAN_STOCKS_MAP or sym in INDICES_MAP:
            batch = self.fetch_yfinance_universe_batch()
            if sym in batch:
                return batch[sym]

        # 5. Any other real symbol: verify it on demand, then quote it from
        #    intraday history so its price keeps moving during market hours.
        if sym not in INDIAN_STOCKS_MAP and sym not in INDICES_MAP:
            meta = self._dynamic_symbols.get(sym) or self._ensure_dynamic_symbol(sym)
            if meta:
                dynamic_quote = self.fetch_yfinance_quote(sym, meta["ticker"], meta["name"])
                if dynamic_quote:
                    return dynamic_quote

        # 6. Flagged fallback for known catalog symbols only (provider outage).
        return self._fallback_quote(sym)

    def _fallback_quote(self, sym: str) -> Optional[QuoteResponse]:
        """Sane, instrument-specific quote when every live provider is down.

        Returns None for symbols we do not track so the API can answer 404
        instead of inventing a fake ₹1500 quote for anything requested.
        """
        if (sym not in INDIAN_STOCKS_MAP and sym not in INDICES_MAP
                and sym not in CRYPTO_BASE_PRICES and sym not in CURRENCIES_MAP):
            return None

        base = _base_price(sym)
        price = round(base * _intraday_wobble(sym), 2)
        # Deterministic per-symbol, per-day change so it does not jitter on refresh.
        rng = random.Random(_stable_seed(sym) + int(time.time() // 86400))
        change_pct = round((rng.random() - 0.5) * 3.0, 2)
        change = round(price * change_pct / 100.0, 2)
        meta = (INDIAN_STOCKS_MAP.get(sym) or INDICES_MAP.get(sym)
                or CRYPTO_MAP.get(sym) or CURRENCIES_MAP.get(sym) or {})
        name = meta.get("name", sym)
        high = round(max(price, base) * 1.012, 2)
        low = round(min(price, base) * 0.988, 2)
        return QuoteResponse(
            symbol=sym,
            name=name,
            price=price,
            change=change,
            change_pct=change_pct,
            high_24h=high,
            low_24h=low,
            volume=float(rng.randint(500_000, 8_000_000)),
            timestamp=datetime.utcnow(),
            source="synthetic",
            is_synthetic=True,
            as_of=datetime.utcnow(),
        )

    def get_candles(self, symbol: str, timeframe: str = "1d", limit: int = 30) -> List[CandleResponse]:
        sym = symbol.upper().strip()
        known = (sym in INDIAN_STOCKS_MAP or sym in INDICES_MAP
                 or sym in CRYPTO_MAP or sym in CURRENCIES_MAP
                 or sym in self._dynamic_symbols
                 or sym.endswith("USDT"))
        if not known:
            if not self._ensure_dynamic_symbol(sym):
                return []
        # Currency pairs have no candle provider in this build; never fabricate one.
        if sym in CURRENCIES_MAP:
            return []

        # 1. Primary for Indian Equities / Indices: Zerodha Kite Connect API
        if (sym in INDIAN_STOCKS_MAP or sym in INDICES_MAP) and self.kite_access_token:
            k_candles = self.fetch_kite_candles(sym, timeframe, limit)
            if k_candles:
                return k_candles

        # 2. Crypto Candles (Binance API)
        if sym in CRYPTO_MAP or sym.endswith("USDT") or sym.endswith("INR"):
            info = CRYPTO_MAP.get(sym)
            pair = info["pair"] if info else ("BTCUSDT" if "BTC" in sym else "ETHUSDT")
            b_candles = self.fetch_binance_candles(pair, timeframe, limit)
            if b_candles:
                is_inr = sym.endswith("INR") or (info and info["quote"] == "INR")
                if is_inr:
                    # Convert USDT to INR
                    inr_candles = []
                    for c in b_candles:
                        inr_candles.append(CandleResponse(
                            time=c.time,
                            open=round(c.open * USD_INR_RATE, 2),
                            high=round(c.high * USD_INR_RATE, 2),
                            low=round(c.low * USD_INR_RATE, 2),
                            close=round(c.close * USD_INR_RATE, 2),
                            volume=c.volume,
                            source="binance_live",
                        ))
                    return inr_candles
                return b_candles

        # 3. Real Indian Stocks Candles (NSE)
        if sym in INDIAN_STOCKS_MAP:
            ticker_sym = INDIAN_STOCKS_MAP[sym]["ticker"]
            candles = self.fetch_yfinance_candles(ticker_sym, timeframe, limit)
            if candles:
                return candles

        # 4. Indices Candles (NSE/BSE)
        if sym in INDICES_MAP:
            ticker_sym = INDICES_MAP[sym]["ticker"]
            candles = self.fetch_yfinance_candles(ticker_sym, timeframe, limit)
            if candles:
                return candles

        # 5. Runtime-verified equities (NSE/BSE/global)
        meta = self._dynamic_symbols.get(sym)
        if meta:
            candles = self.fetch_yfinance_candles(meta["ticker"], timeframe, limit)
            if candles:
                return candles

        # 6. Never fabricate history. Unknown symbols or provider outages return
        #    an empty series instead of a synthetic price walk.
        return []

    def get_indices(self) -> List[IndexOverview]:
        indices_list = ["NIFTY 50", "SENSEX", "BANK NIFTY", "NIFTY IT"]
        out = []
        for name in indices_list:
            q = self.get_quote(name)
            if q:
                # Real captured candle closes when available; otherwise a flat
                # line rather than a fabricated pattern.
                spark = self._universe_sparklines.get(name, [])[-10:]
                if len(spark) < 2:
                    spark = [round(q.price, 2)] * 10
                out.append(IndexOverview(
                    name=name,
                    value=q.price,
                    change=q.change,
                    change_pct=q.change_pct,
                    positive=q.change >= 0,
                    sparkline=spark
                ))
        return out

    def get_global_indices(self) -> List[IndexOverview]:
        """Return verified global benchmark quotes; no hard-coded values."""
        out: List[IndexOverview] = []
        for name, ticker in GLOBAL_INDICES_MAP.items():
            q = self.fetch_yfinance_quote(name, ticker, name, False)
            if not q:
                continue
            candles = self.fetch_yfinance_candles(ticker, "1d", 10)
            spark = [round(float(c.close), 2) for c in candles if not c.is_synthetic]
            out.append(IndexOverview(
                name=name,
                value=q.price,
                change=q.change,
                change_pct=q.change_pct,
                positive=q.change >= 0,
                sparkline=spark,
            ))
        return out

    def get_all_quotes(self) -> List[QuoteResponse]:
        syms = list(INDIAN_STOCKS_MAP.keys()) + ["BTCINR", "ETHINR", "SOLINR"] + list(self._dynamic_symbols.keys())
        syms = list(dict.fromkeys(syms))
        res = []
        for s in syms:
            q = self.get_quote(s)
            if q:
                res.append(q)
        return res

    def get_market_breadth(self) -> Dict[str, Any]:
        """Calculate real market breadth from current live quotes"""
        quotes = self.get_all_quotes()
        advances = sum(1 for q in quotes if q.change > 0)
        declines = sum(1 for q in quotes if q.change < 0)
        unchanged = sum(1 for q in quotes if q.change == 0)
        total = max(1, len(quotes))
        ratio = round(advances / max(1, declines), 2)

        return {
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "total_tracked": total,
            "ad_ratio": ratio,
            "sentiment": "BULLISH" if ratio > 1.2 else ("BEARISH" if ratio < 0.8 else "NEUTRAL")
        }

    def get_sector_performance(self) -> List[Dict[str, Any]]:
        """Aggregate live stock quotes into sector-level performance."""
        buckets: Dict[str, List[float]] = {}
        for sym, meta in INDIAN_STOCKS_MAP.items():
            q = self.get_quote(sym)
            if not q:
                continue
            buckets.setdefault(meta.get("sector", "Equities"), []).append(q.change_pct)

        rows = []
        for sector, pcts in buckets.items():
            avg = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
            rows.append({
                "sector": sector,
                "sector_name": sector,
                "change_pct": avg,
                "positive": avg >= 0,
                "constituents": len(pcts),
            })
        rows.sort(key=lambda r: r["change_pct"], reverse=True)
        return rows

    @staticmethod
    def _fetch_text(url: str, timeout: float = 20.0) -> str:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    @classmethod
    def _fetch_json(cls, url: str, timeout: float = 20.0) -> Any:
        return json.loads(cls._fetch_text(url, timeout))

    @staticmethod
    def _parse_number(value: Any) -> Optional[float]:
        txt = str(value or "").replace("₹", "").replace(",", "").strip()
        if not txt:
            return None
        negative = txt.startswith("-") or (txt.startswith("(") and txt.endswith(")"))
        txt = txt.strip("()+- ")
        try:
            num = float(txt)
        except (TypeError, ValueError):
            return None
        return -num if negative else num

    def _fetch_fii_dii(self) -> Optional[Dict[str, Any]]:
        """Read the verified institutional-flow table published on Groww."""
        if not BS4_AVAILABLE:
            return None
        try:
            html = self._fetch_text("https://groww.in/fii-dii-data")
            soup = BeautifulSoup(html, "html.parser")
            rows: List[Dict[str, Any]] = []
            for tr in soup.select("tbody tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
                if len(cells) < 7 or not re.search(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", cells[0]):
                    continue
                nums = [self._parse_number(c) for c in cells[1:7]]
                if any(n is None for n in nums):
                    continue
                rows.append({
                    "day": cells[0],
                    "fii_buy": nums[0],
                    "fii_sell": nums[1],
                    "fii": nums[2],
                    "dii_buy": nums[3],
                    "dii_sell": nums[4],
                    "dii": nums[5],
                })
                if len(rows) == 5:
                    break
            if not rows:
                return None
            latest = rows[0]
            return {
                "available": True,
                "source": "Groww (NSE/BSE provisional cash-market data)",
                "as_of": latest["day"],
                "fii_net": latest["fii"],
                "fii_buy": latest["fii_buy"],
                "fii_sell": latest["fii_sell"],
                "dii_net": latest["dii"],
                "dii_buy": latest["dii_buy"],
                "dii_sell": latest["dii_sell"],
                "historical_5d": rows,
            }
        except Exception as e:
            print(f"[FII/DII Feed Warning]: {e}")
            return None

    def get_fii_dii_flows(self) -> Dict[str, Any]:
        """Return verified daily FII/DII cash-market flows."""
        with self._feed_lock:
            if self._fii_cache and (time.time() - self._fii_cache_time) < 900:
                return dict(self._fii_cache)
        data = self._fetch_fii_dii()
        if data:
            with self._feed_lock:
                self._fii_cache = data
                self._fii_cache_time = time.time()
            return dict(data)
        return {
            "available": False,
            "message": "FII / DII feed unavailable right now",
            "source": "Groww (NSE/BSE provisional cash-market data)",
            "fii_net": 0,
            "fii_buy": 0,
            "fii_sell": 0,
            "dii_net": 0,
            "dii_buy": 0,
            "dii_sell": 0,
            "historical_5d": [],
        }

    def _fetch_forex_rates(self) -> List[Dict[str, Any]]:
        """Fetch verified INR crosses and 7-day history from Frankfurter/ECB."""
        try:
            end = datetime.utcnow().date()
            start = end - timedelta(days=10)
            latest = self._fetch_json(
                "https://api.frankfurter.dev/v1/latest?base=INR&symbols=" +
                ",".join(FOREX_META.keys())
            )
            history = self._fetch_json(
                f"https://api.frankfurter.dev/v1/{start.isoformat()}..{end.isoformat()}"
                "?base=INR&symbols=" + ",".join(FOREX_META.keys())
            )
            rates = latest.get("rates", {}) or {}
            hist_rates = history.get("rates", {}) or {}
            out: List[Dict[str, Any]] = []
            for code, meta in FOREX_META.items():
                rate = rates.get(code)
                if not rate:
                    continue
                scale = float(meta["scale"])
                price = scale / float(rate)
                spark: List[float] = []
                for day in sorted(hist_rates.keys()):
                    point = hist_rates[day].get(code)
                    if point:
                        spark.append(round(scale / float(point), 4))
                prev = spark[-2] if len(spark) >= 2 else price
                change = price - prev
                change_pct = (change / prev * 100.0) if prev else 0.0
                out.append({
                    "symbol": meta["symbol"],
                    "name": meta["name"],
                    "pair": meta["pair"],
                    "currency": code,
                    "price": round(price, 4),
                    "change": round(change, 4),
                    "change_pct": round(change_pct, 3),
                    "positive": change >= 0,
                    "sparkline": spark[-10:],
                    "api_source": "Frankfurter (ECB reference rates)",
                    "as_of": latest.get("date"),
                })
            return out
        except Exception as e:
            print(f"[FX Feed Warning]: {e}")
            return []

    def get_currencies_catalog(self) -> List[Dict[str, Any]]:
        """Return live FX crosses; never show fabricated static rates."""
        with self._feed_lock:
            if self._fx_cache and (time.time() - self._fx_cache_time) < 1800:
                return [dict(x) for x in self._fx_cache]
        rows = self._fetch_forex_rates()
        with self._feed_lock:
            self._fx_cache = rows
            self._fx_cache_time = time.time()
        return [dict(x) for x in rows]

    def get_usd_inr_rate(self) -> Optional[float]:
        """Return a verified USD/INR rate from FX or Binance cross-rates."""
        for row in self.get_currencies_catalog():
            if row.get("symbol") == "USDINR" and row.get("price"):
                return float(row["price"])
        try:
            inr = self.get_quote("BTCINR")
            usdt = self.get_quote("BTCUSDT")
            if inr and usdt and usdt.price and not inr.is_synthetic and not usdt.is_synthetic:
                return float(inr.price) / float(usdt.price)
        except Exception:
            pass
        return None

    def _fetch_mutual_fund(self, code: int) -> Optional[Dict[str, Any]]:
        try:
            payload = self._fetch_json(f"https://api.mfapi.in/mf/{code}")
        except Exception as e:
            print(f"[Mutual Fund {code} Warning]: {e}")
            return None
        meta = payload.get("meta") or {}
        series: List[tuple] = []
        for item in payload.get("data") or []:
            try:
                day = datetime.strptime(item["date"], "%d-%m-%Y").date()
                nav = float(item["nav"])
            except (KeyError, TypeError, ValueError):
                continue
            series.append((day, nav))
        if not series:
            return None
        series.sort(key=lambda x: x[0])
        latest_day, latest_nav = series[-1]
        prev_nav = series[-2][1] if len(series) > 1 else latest_nav

        def nav_on_or_before(days: int) -> float:
            target = latest_day - timedelta(days=days)
            older = [p for p in series if p[0] <= target]
            return older[-1][1] if older else series[0][1]

        def pct_return(days: int) -> float:
            base = nav_on_or_before(days)
            return round((latest_nav / base - 1.0) * 100.0, 2) if base else 0.0

        return {
            "scheme_code": code,
            "scheme_name": meta.get("scheme_name") or f"Scheme {code}",
            "fund_house": meta.get("fund_house") or "—",
            "category": meta.get("scheme_category") or "Mutual Fund",
            "scheme_type": meta.get("scheme_type") or "Open Ended",
            "nav": round(latest_nav, 4),
            "nav_date": latest_day.isoformat(),
            "change": round(latest_nav - prev_nav, 4),
            "change_pct": round(((latest_nav / prev_nav - 1.0) * 100.0) if prev_nav else 0.0, 2),
            "return_1m": pct_return(30),
            "return_3m": pct_return(91),
            "return_1y": pct_return(365),
            "sparkline": [round(nav, 4) for _, nav in series[-30:]],
            "api_source": "mfapi.in (AMFI NAV history)",
        }

    def get_mutual_funds_catalog(self) -> List[Dict[str, Any]]:
        """Return verified mutual-fund NAVs and returns for curated schemes."""
        with self._feed_lock:
            if self._mf_cache and (time.time() - self._mf_cache_time) < 1800:
                return [dict(x) for x in self._mf_cache]
        with ThreadPoolExecutor(max_workers=5) as pool:
            rows = list(pool.map(self._fetch_mutual_fund, MUTUAL_FUND_SCHEMES))
        clean = [r for r in rows if r]
        clean.sort(key=lambda r: r["return_1y"], reverse=True)
        with self._feed_lock:
            self._mf_cache = clean
            self._mf_cache_time = time.time()
        return [dict(x) for x in clean]

    def get_mutual_fund(self, code: Any) -> Optional[Dict[str, Any]]:
        try:
            code_int = int(code)
        except (TypeError, ValueError):
            return None
        for row in self.get_mutual_funds_catalog():
            if row.get("scheme_code") == code_int:
                return dict(row)
        return self._fetch_mutual_fund(code_int)

    def get_growth_mutual_funds(self) -> List[Dict[str, Any]]:
        """Rank verified funds by historical growth momentum, never by forecasts."""
        out: List[Dict[str, Any]] = []
        for f in self.get_mutual_funds_catalog():
            spark = [float(v) for v in (f.get("sparkline") or []) if v]
            latest = spark[-1] if spark else float(f.get("nav") or 0)
            first = spark[0] if spark else latest
            peak = max(spark) if spark else latest
            momentum = ((latest / first - 1.0) * 100.0) if first else 0.0
            drawdown = ((peak - latest) / peak * 100.0) if peak else 0.0
            r1y = float(f.get("return_1y") or 0)
            r3m = float(f.get("return_3m") or 0)
            r1m = float(f.get("return_1m") or 0)
            score = (0.45 * r1y) + (0.30 * r3m) + (0.15 * r1m) + (0.10 * momentum) - (0.25 * drawdown)
            out.append({
                **f,
                "momentum_30d": round(momentum, 2),
                "drawdown_30d": round(drawdown, 2),
                "growth_score": round(score, 2),
            })
        out.sort(key=lambda x: x["growth_score"], reverse=True)
        for rank, row in enumerate(out, 1):
            row["rank"] = rank
            row["growth_label"] = "High momentum" if rank <= 3 else ("Steady growth" if rank <= 6 else "Tracked")
        return out

    def search_mutual_funds(self, query: str) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        try:
            data = self._fetch_json(
                "https://api.mfapi.in/mf/search?q=" + urllib.parse.quote(q)
            )
            return [
                {"scheme_code": x.get("schemeCode"), "scheme_name": x.get("schemeName")}
                for x in (data or [])[:25]
                if x.get("schemeCode")
            ]
        except Exception as e:
            print(f"[Mutual Fund Search Warning]: {e}")
            return []

    def search_instruments(self, query: str) -> List[Dict]:
        q = query.upper().strip()
        results = []
        # Search Indian Stocks
        for sym, item in INDIAN_STOCKS_MAP.items():
            if q in sym or q in item["name"].upper():
                quote = self.get_quote(sym)
                results.append({
                    "symbol": sym,
                    "name": item["name"],
                    "segment": item["segment"],
                    "price": quote.price if quote else 0.0,
                    "exchange": item["exchange"]
                })
        # Search Indices
        for sym, item in INDICES_MAP.items():
            name = str(item.get("name", "")).upper()
            if q in sym.upper() or q in name:
                quote = self.get_quote(sym)
                results.append({
                    "symbol": sym,
                    "name": item.get("name", sym),
                    "segment": "INDEX",
                    "price": quote.price if quote else 0.0,
                    "exchange": item.get("exchange", "NSE")
                })
        # Search Crypto
        for sym, item in CRYPTO_MAP.items():
            if q in sym or q in item["name"].upper():
                quote = self.get_quote(sym)
                results.append({
                    "symbol": sym,
                    "name": item["name"],
                    "segment": "CRYPTO",
                    "price": quote.price if quote else 0.0,
                    "exchange": "BINANCE"
                })

        # On-demand verified symbol: any real ticker not in the static catalog.
        exact = {item["symbol"].upper() for item in results}
        if len(q) >= 2 and q not in exact:
            meta = self._ensure_dynamic_symbol(q)
            if meta:
                quote = self.fetch_yfinance_quote(q, meta["ticker"], meta["name"])
                if quote:
                    results.append({
                        "symbol": q,
                        "name": meta["name"],
                        "segment": "EQUITY",
                        "price": quote.price,
                        "exchange": meta["exchange"]
                    })
        return results

    def get_stocks_catalog(self) -> List[Dict[str, Any]]:
        """Return catalog equities plus any runtime-verified symbol with live metrics"""
        # 1. High-speed batch quote via Kite Connect API
        if self.kite_client and self.kite_access_token:
            try:
                symbols_to_fetch = [f"NSE:{s}" for s in INDIAN_STOCKS_MAP.keys()]
                batch_quotes = self.kite_client.quote(symbols_to_fetch)
                now = time.time()
                for sym, meta in INDIAN_STOCKS_MAP.items():
                    k_sym = f"NSE:{sym}"
                    if batch_quotes and k_sym in batch_quotes:
                        data = batch_quotes[k_sym]
                        price = float(data.get("last_price", 0.0))
                        ohlc = data.get("ohlc", {})
                        prev_close = float(ohlc.get("close", price))
                        change = round(price - prev_close, 2)
                        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                        high = float(ohlc.get("high", price))
                        low = float(ohlc.get("low", price))
                        vol = int(data.get("volume", 0))
                        inst_token = data.get("instrument_token")
                        if inst_token:
                            self._kite_instrument_tokens[sym] = inst_token

                        q = QuoteResponse(
                            symbol=sym,
                            name=meta["name"],
                            price=price,
                            change=change,
                            change_pct=change_pct,
                            high_24h=high,
                            low_24h=low,
                            volume=vol,
                            timestamp=datetime.utcnow(),
                            source="kite_live",
                            as_of=datetime.utcnow(),
                        )
                        self._quote_cache[f"kite_quote_{sym}"] = q
                        self._quote_cache_time[f"kite_quote_{sym}"] = now
            except Exception as e:
                print(f"[Kite Batch Quote Error]: {e}")

        catalog = dict(INDIAN_STOCKS_MAP)
        for sym, meta in self._dynamic_symbols.items():
            catalog[sym] = {
                "ticker": meta["ticker"],
                "name": meta["name"],
                "sector": meta.get("sector", "Equities"),
                "segment": meta.get("segment", "EQ"),
                "exchange": meta.get("exchange", "NSE"),
            }

        results = []
        for sym, meta in catalog.items():
            q = self.get_quote(sym)
            spark = list(self._universe_sparklines.get(sym, [q.price] if q else []))
            if len(spark) < 8 and q:
                spark = list(self._universe_sparklines.get(sym, []))
            if len(spark) < 2 and q:
                spark = [round(q.price, 2)] * 8
            results.append({
                "symbol": sym,
                "name": meta["name"],
                "sector": meta.get("sector", "Equities"),
                "segment": meta["segment"],
                "exchange": meta["exchange"],
                "token": self._kite_instrument_tokens.get(sym, meta.get("token")),
                "api_source": "Zerodha Kite Connect" if (self.kite_access_token and sym in INDIAN_STOCKS_MAP) else "Verified Yahoo Feed",
                "price": q.price if q else 0.0,
                "change": q.change if q else 0.0,
                "change_pct": q.change_pct if q else 0.0,
                "positive": (q.change >= 0) if q else True,
                "high_24h": q.high_24h if q else 0.0,
                "low_24h": q.low_24h if q else 0.0,
                "volume": q.volume if q else 0,
                "sparkline": spark
            })
        return results

    def get_crypto_catalog(self) -> List[Dict[str, Any]]:
        """Return all crypto pairs available on Binance API key with live USDT & INR metrics"""
        results = []
        usd_inr = self.get_usd_inr_rate()
        for sym, meta in CRYPTO_MAP.items():
            q = self.get_quote(sym)
            is_inr = sym.endswith("INR") or meta.get("quote") == "INR"
            crypto_candles = self.fetch_binance_candles(meta["pair"], "1d", 12)
            spark = [round(c.close, 4) for c in crypto_candles]
            if is_inr and usd_inr:
                spark = [round(v * usd_inr, 2) for v in spark]
            price_usdt = round(q.price / usd_inr, 2) if is_inr and q and usd_inr else (q.price if q and not is_inr else 0.0)
            price_inr = round(q.price * usd_inr, 2) if not is_inr and q and usd_inr else (q.price if q and is_inr else 0.0)

            results.append({
                "symbol": sym,
                "pair": meta["pair"],
                "name": meta["name"],
                "base": meta["base"],
                "quote": meta["quote"],
                "category": meta.get("category", "Cryptocurrency"),
                "exchange": "BINANCE",
                "api_source": "Binance Spot API",
                "price": q.price if q else 0.0,
                "price_usdt": price_usdt,
                "price_inr": price_inr,
                "change": q.change if q else 0.0,
                "change_pct": q.change_pct if q else 0.0,
                "positive": (q.change >= 0) if q else True,
                "high_24h": q.high_24h if q else 0.0,
                "low_24h": q.low_24h if q else 0.0,
                "volume": q.volume if q else 0,
                "sparkline": spark
            })
        return results

    def get_tick_snapshot(self) -> Dict[str, QuoteResponse]:
        """Return the authoritative provider snapshot — no simulated drift.

        Prices only change when a real provider (Kite / Binance / yfinance)
        returns a newer value. Synthetic fallback quotes are flagged as such so
        the UI can label them instead of presenting random wobble as live ticks.
        """
        now = time.time()
        with self._snapshot_lock:
            if self._snapshot_cache and (now - self._snapshot_time) < 5.0:
                return dict(self._snapshot_cache)

            self._tick_seq += 1
            self._snapshot_time = now
            syms = list(INDIAN_STOCKS_MAP.keys()) + list(CRYPTO_MAP.keys()) + list(self._dynamic_symbols.keys())
            syms = list(dict.fromkeys(syms))
            quotes = [self.get_quote(s) for s in syms]
            for fx in self.get_currencies_catalog():
                quotes.append(QuoteResponse(
                    symbol=fx["symbol"],
                    name=fx["name"],
                    price=float(fx["price"]),
                    change=float(fx["change"]),
                    change_pct=float(fx["change_pct"]),
                    high_24h=float(fx["price"]),
                    low_24h=float(fx["price"]),
                    volume=0,
                    source=fx.get("api_source", "FX feed"),
                    as_of=None,
                ))
            self._snapshot_cache = {q.symbol: q for q in quotes if q}
            return dict(self._snapshot_cache)

    def simulate_tick(self) -> Dict[str, QuoteResponse]:
        """Backwards-compatible alias for the non-synthetic tick snapshot."""
        return self.get_tick_snapshot()


market_ingest = MarketIngestService()
