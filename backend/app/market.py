"""Observed historical data and explicitly fresh provider observations."""

import json, os, threading, io
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/history"


def catalog():
    path = DATA / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else []


def meta(symbol):
    found = next((x for x in catalog() if x["symbol"] == symbol), None)
    if not found:
        raise HTTPException(404, "Unsupported instrument")
    return found


def history(symbol, version=None):
    from app.datasets import read

    return pd.read_csv(io.BytesIO(read(symbol, version))).to_dict("records")


def latest(symbol):
    m = meta(symbol)
    rows = history(symbol)
    last = rows[-1]
    prev = rows[-2]
    return {
        **m,
        **last,
        "price": last["close"],
        "change_pct": round((last["close"] / prev["close"] - 1) * 100, 2),
        "observed_at": last["date"],
        "status": "historical",
        "market_status": "Historical snapshot",
        "tradable": False,
        "sparkline": [x["close"] for x in rows[-30:]],
    }


_quotes = {}
_guard = threading.Lock()


def live_quote(symbol, owner="system", db=None):
    meta(symbol)
    from app.store import DB, Observation
    from sqlalchemy import select

    with _guard:
        q = _quotes.get(symbol) if owner == "system" else None
    if not q:
        from contextlib import nullcontext

        with nullcontext(db) if db is not None else DB() as reader:
            r = reader.scalar(
                select(Observation).where(
                    Observation.owner == owner, Observation.symbol == symbol
                )
            )
            q = r.data if r else None
            if q is None and meta(symbol).get("segment") == "crypto":
                public = reader.scalar(
                    select(Observation).where(
                        Observation.owner == "public", Observation.symbol == symbol
                    )
                )
                q = public.data if public else None
    if not q:
        return None
    age = (
        datetime.now(timezone.utc) - datetime.fromisoformat(q["observed_at"])
    ).total_seconds()
    return (
        {**latest(symbol), **q, "market_status": "Fresh authenticated observation"}
        if 0 <= age <= 90 and q["price"] > 0
        else None
    )


def refresh_quotes():
    """Only an authenticated Kite feed can authorize current-market fills."""
    import httpx

    key = os.getenv("KITE_API_KEY")
    token = os.getenv("KITE_ACCESS_TOKEN")
    if not key or not token:
        return {
            "status": "unavailable",
            "reason": "No active Kite credentials. Use historical replay.",
        }
    symbols = [
        x["symbol"] for x in catalog() if x.get("segment", "equities") == "equities"
    ]
    res = httpx.get(
        "https://api.kite.trade/quote",
        params=[("i", "NSE:" + s) for s in symbols],
        headers={"Authorization": f"token {key}:{token}", "X-Kite-Version": "3"},
        timeout=15,
    )
    res.raise_for_status()
    from zoneinfo import ZoneInfo

    for k, v in res.json()["data"].items():
        stamp = v.get("last_trade_time")
        if not stamp:
            continue
        dt = datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        dt = dt.astimezone(timezone.utc)
        q = {
            "symbol": k.split(":")[1],
            "price": float(v["last_price"]),
            "source": "Zerodha Kite",
            "observed_at": dt.isoformat(),
            "status": "live",
            "tradable": True,
            "currency": "INR",
            "change_pct": round(
                (float(v["last_price"]) / float(v["ohlc"]["close"]) - 1) * 100, 2
            )
            if v.get("ohlc", {}).get("close")
            else None,
        }
        with _guard:
            _quotes[q["symbol"]] = q
    persist_quotes("system", _quotes)
    return {"status": "updated"}


def indicators(symbol, cutoff=None, version=None):
    rows = history(symbol, version)
    if cutoff:
        rows = [x for x in rows if x["date"] <= cutoff]
    if len(rows) < 30:
        raise HTTPException(422, "At least 30 historical sessions required")
    c = pd.Series([r["close"] for r in rows], dtype=float)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (
        100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1])
        if loss.iloc[-1] > 0
        else (100 if gain.iloc[-1] > 0 else 50)
    )
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    sma = c.rolling(20).mean().iloc[-1]
    std = c.rolling(20).std(ddof=0).iloc[-1]
    items = [
        {
            "name": "RSI · 14",
            "value": round(float(rsi), 2),
            "explanation": "Recent upward versus downward momentum. Above 70 is elevated; below 30 is depressed.",
        },
        {
            "name": "MACD",
            "value": round(float(macd.iloc[-1]), 2),
            "explanation": "Difference between 12- and 26-session exponential averages.",
        },
        {
            "name": "MACD signal",
            "value": round(float(signal.iloc[-1]), 2),
            "explanation": "Nine-session average of MACD, for comparison with momentum.",
        },
        {
            "name": "20-session average",
            "value": round(float(sma), 2),
            "explanation": "Average closing price across the latest 20 observed sessions.",
        },
        {
            "name": "Upper volatility band",
            "value": round(float(sma + 2 * std), 2),
            "explanation": "20-session average plus two standard deviations.",
        },
        {
            "name": "Lower volatility band",
            "value": round(float(sma - 2 * std), 2),
            "explanation": "20-session average minus two standard deviations.",
        },
    ]
    return {
        "symbol": symbol,
        "as_of": rows[-1]["date"],
        "source": meta(symbol)["source"],
        "indicators": items,
        "fundamentals": None,
        "fundamentals_status": "Unavailable from this historical provider; no estimated company ratios are shown.",
    }


def persist_quotes(owner, quotes):
    from app.store import DB, Observation
    from sqlalchemy import select
    from uuid import uuid4

    with DB.begin() as db:
        for symbol, q in quotes.items():
            r = db.scalar(
                select(Observation).where(
                    Observation.owner == owner, Observation.symbol == symbol
                )
            )
            if r:
                r.data = q
            else:
                db.add(Observation(id=uuid4().hex, owner=owner, symbol=symbol, data=q))


def refresh_public_crypto():
    """Unauthenticated exchange observations are public data, never private broker data."""
    if os.getenv("EYE_DISABLE_NETWORK") == "1":
        return {"status": "disabled_for_tests"}
    import httpx

    pairs = [
        m["provider_ids"]["binance"]
        for m in catalog()
        if m.get("provider_ids", {}).get("binance")
    ]
    if not pairs:
        return {"status": "no_supported_pairs"}
    response = httpx.get(
        "https://data-api.binance.vision/api/v3/ticker/24hr",
        params={"symbols": json.dumps(sorted(set(pairs)), separators=(",", ":"))},
        timeout=15,
    )
    response.raise_for_status()
    quotes = {}
    for item in response.json():
        sym = item["symbol"]
        observed = datetime.fromtimestamp(
            int(item["closeTime"]) / 1000, timezone.utc
        ).isoformat()
        quotes[sym] = {
            "symbol": sym,
            "price": float(item["lastPrice"]),
            "change_pct": float(item["priceChangePercent"]),
            "observed_at": observed,
            "source": "Binance public 24-hour ticker",
            "status": "live",
            "tradable": False,
            "execution_note": "Public market observation. Use native-currency replay; the INR paper wallet cannot execute USDT trades.",
        }
    persist_quotes("public", quotes)
    return {"status": "updated", "symbols": list(quotes)}
