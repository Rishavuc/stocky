"""Download observed OHLCV data, never synthesize missing prices.
Yahoo Finance chart feed is an unofficial personal/research data source.
No redistribution rights are implied; review terms before public distribution.
"""

import json, urllib.request, csv, hashlib, io, sys

sys.path.insert(
    0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "backend")
)
from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = {
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank",
    "INFY": "Infosys",
    "ICICIBANK": "ICICI Bank",
    "ITC": "ITC Limited",
}


def fetch(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?range=5y&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        result = json.load(res)["chart"]["result"][0]
    quotes = result["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(result["timestamp"]):
        vals = [quotes[k][i] for k in ("open", "high", "low", "close", "volume")]
        if any(v is None for v in vals):
            continue
        session_date = (
            datetime.fromtimestamp(ts, timezone.utc)
            .astimezone(ZoneInfo("Asia/Kolkata"))
            .date()
        )
        local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        if session_date > local_now.date() or (
            session_date == local_now.date() and local_now.time() < time(16, 15)
        ):
            continue  # Never train or replay on a still-forming daily bar.
        if (
            not (
                0 < vals[2] <= min(vals[0], vals[3]) <= max(vals[0], vals[3]) <= vals[1]
            )
            or vals[4] < 0
        ):
            continue
        rows.append([session_date.isoformat(), *[round(v, 4) for v in vals]])
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow(["date", "open", "high", "low", "close", "volume"])
    w.writerows(rows)
    content = f.getvalue().encode()
    return {
        "symbol": symbol,
        "name": SYMBOLS[symbol],
        "currency": "INR",
        "exchange": "NSE",
        "source": "Yahoo Finance chart feed (unofficial)",
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "start": rows[0][0],
        "end": rows[-1][0],
        "sha256": hashlib.sha256(content).hexdigest(),
        "adjustment": "Provider OHLC prices; not a total-return series. Corporate actions can create discontinuities.",
    }, content


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from app.store import init
    from app.datasets import publish

    init()
    manifest = []
    for symbol in SYMBOLS:
        try:
            manifest.append(fetch(symbol))
            print(symbol, manifest[-1][0]["rows"])
        except Exception as e:
            print(symbol, type(e).__name__, str(e))
    if not manifest:
        raise SystemExit("No data retrieved")
    publish(manifest)
