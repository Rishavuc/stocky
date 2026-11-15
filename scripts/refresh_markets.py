"""Refresh real multi-segment observations. Failed providers retain last good history."""

import sys, io, csv, json, urllib.request, urllib.parse, hashlib
from pathlib import Path
from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from app.datasets import publish
from app.store import init

STOCKS = {
    "RELIANCE": ("RELIANCE.NS", "Reliance Industries", "Energy"),
    "TCS": ("TCS.NS", "Tata Consultancy Services", "Technology"),
    "HDFCBANK": ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    "INFY": ("INFY.NS", "Infosys", "Technology"),
    "ICICIBANK": ("ICICIBANK.NS", "ICICI Bank", "Banking"),
    "ITC": ("ITC.NS", "ITC Limited", "Consumer"),
    "SBIN": ("SBIN.NS", "State Bank of India", "Banking"),
    "LT": ("LT.NS", "Larsen & Toubro", "Industrial"),
    "BHARTIARTL": ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
    "TATASTEEL": ("TATASTEEL.NS", "Tata Steel", "Metals"),
    "SUNPHARMA": ("SUNPHARMA.NS", "Sun Pharma", "Healthcare"),
    "MARUTI": ("MARUTI.NS", "Maruti Suzuki", "Automobile"),
}
INDICES = {
    "NIFTY50": ("^NSEI", "Nifty 50", "Index"),
    "BANKNIFTY": ("^NSEBANK", "Nifty Bank", "Index"),
    "SENSEX": ("^BSESN", "BSE Sensex", "Index"),
}
CRYPTO = {
    "BTCUSD": ("BTC-USD", "Bitcoin", "Crypto"),
    "ETHUSD": ("ETH-USD", "Ethereum", "Crypto"),
    "SOLUSD": ("SOL-USD", "Solana", "Crypto"),
}


def request(url):
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30
    ) as r:
        return json.load(r)


def csv_bytes(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "open", "high", "low", "close", "volume"])
    w.writerows(rows)
    return out.getvalue().encode()


def yahoo(symbol, details, segment, timeframe="1d"):
    ticker, name, sector = details
    interval = "5m" if timeframe == "5m" else "1d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range={'60d' if interval == '5m' else '5y'}&interval={interval}"
    result = request(url)["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    rows = []
    now = datetime.now(timezone.utc)
    for i, ts in enumerate(result.get("timestamp", [])):
        values = [q[k][i] for k in ("open", "high", "low", "close", "volume")]
        if any(v is None for v in values) or min(values[:4]) <= 0:
            continue
        dt = datetime.fromtimestamp(ts, timezone.utc)
        if interval == "5m":
            if (now - dt).total_seconds() < 300:
                continue
            label = dt.isoformat()
        else:
            local = now.astimezone(ZoneInfo("Asia/Kolkata"))
            if dt.date() == now.date() and (
                segment == "crypto" or local.time() < time(16, 15)
            ):
                continue
            label = dt.strftime("%Y-%m-%d")
        rows.append([label, *values])
    sid = symbol if interval == "1d" else symbol + "_5m"
    content = csv_bytes(rows)
    return {
        "symbol": sid,
        "base_symbol": symbol,
        "name": name + (" · 5 minute" if interval == "5m" else ""),
        "segment": "intraday" if interval == "5m" else segment,
        "timeframe": interval,
        "exchange": "Reference" if segment == "crypto" else "NSE",
        "currency": "USD" if segment == "crypto" else "INR",
        "sector": sector,
        "lot_size": 1,
        "expiry": None,
        "provider_ids": {"yahoo": ticker},
        "source": "Yahoo Finance chart feed (unofficial)",
        "source_url": url,
        "retrieved_at": now.isoformat(),
        "adjustment": "Provider OHLC; not total return; corporate actions require reconciliation.",
    }, content


def amfi_current():
    url = "https://portal.amfiindia.com/spages/NAVAll.txt"
    with urllib.request.urlopen(url, timeout=30) as r:
        text = r.read().decode()
    result = {}
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        if len(row) < 6 or not row[0].isdigit():
            continue
        try:
            result[row[0]] = {
                "nav": float(row[-2]),
                "date": datetime.strptime(row[-1].strip(), "%d-%b-%Y").strftime(
                    "%Y-%m-%d"
                ),
            }
        except (ValueError, IndexError):
            continue
    return result


def binance(pair,interval="1d"):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={pair}&interval={interval}&limit=1000"
    rows = []
    now = datetime.now(timezone.utc)
    for x in request(url):
        if float(x[6]) / 1000 > now.timestamp():
            continue
        rows.append(
            [
                datetime.fromtimestamp(x[0] / 1000, timezone.utc).strftime("%Y-%m-%d" if interval=="1d" else "%Y-%m-%dT%H:%M:%S+00:00"),
                *[float(x[i]) for i in (1, 2, 3, 4, 5)],
            ]
        )
    return {
        "symbol": pair if interval=="1d" else pair+"_1h",
        "base_symbol":pair,
        "name": pair + " · Binance spot",
        "segment": "crypto",
        "timeframe": interval,
        "currency": "USDT",
        "exchange": "Binance",
        "lot_size": 1,
        "expiry": None,
        "provider_ids": {"binance": pair},
        "source": "Binance public market data",
        "source_url": url,
        "retrieved_at": now.isoformat(),
        "adjustment": "Observed spot OHLCV, native quote currency.",
    }, csv_bytes(rows)


def fund(code, official=None):
    # AMFI supplies current NAV publication; this history endpoint is separately attributed.
    url = "https://api.mfapi.in/mf/" + code
    j = request(url)
    rows = []
    for item in reversed(j["data"]):
        nav = float(item["nav"])
        stamp = datetime.strptime(item["date"], "%d-%m-%Y").strftime("%Y-%m-%d")
        if nav > 0:
            rows.append([stamp, nav, nav, nav, nav, 0])
    rows = rows[-1500:]
    current = (official or {}).get(code)
    if current and current["date"] > rows[-1][0]:
        v = current["nav"]
        rows.append([current["date"], v, v, v, v, 0])
    return {
        "symbol": "MF" + code,
        "name": j["meta"]["scheme_name"],
        "segment": "funds",
        "timeframe": "1d",
        "currency": "INR",
        "exchange": "AMFI scheme",
        "sector": j["meta"].get("scheme_category"),
        "lot_size": 1,
        "expiry": None,
        "provider_ids": {"amfi": code},
        "source": "MFapi historical NAV; AMFI latest publication"
        if current
        else "MFapi NAV history (third party, AMFI scheme identifiers)",
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "adjustment": "Published scheme NAV, not an intraday exchange quote.",
    }, csv_bytes(rows)


def run():
    init()
    updates = []
    jobs = (
        [(s, d, "equities") for s, d in STOCKS.items()]
        + [(s, d, "indices") for s, d in INDICES.items()]
        + [(s, d, "crypto") for s, d in CRYPTO.items()]
    )
    for s, d, segment in jobs:
        try:
            updates.append(yahoo(s, d, segment))
            print(s, "observed", flush=True)
        except Exception as e:
            print(s, "retaining previous data:", type(e).__name__, flush=True)
    for s in ("RELIANCE", "TCS"):
        try:
            updates.append(yahoo(s, STOCKS[s], "equities", "5m"))
            print(s, "intraday observed", flush=True)
        except Exception as e:
            print(s, "intraday unavailable:", type(e).__name__, flush=True)
    try:
        official = amfi_current()
        print("AMFI latest NAV publication retrieved", flush=True)
    except Exception:
        official = {}
        print("AMFI unavailable; retain attributed historical source", flush=True)
    for pair in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        try:
            updates.append(binance(pair))
            print(pair, "Binance observations retrieved", flush=True)
        except Exception as e:
            print(pair, "Binance unavailable:", type(e).__name__, flush=True)
    for code in ("120716", "119598", "120503"):
        try:
            updates.append(fund(code, official))
            print("Fund", code, "observed", flush=True)
        except Exception as e:
            print("Fund", code, "unavailable:", type(e).__name__, flush=True)
    if updates:
        publish(updates)
    print("Published", len(updates), "datasets; failed sources retained.")


if __name__ == "__main__":
    import urllib.parse

    run()
