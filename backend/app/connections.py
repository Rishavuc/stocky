"""Encrypted user-owned read-only broker connections; no broker order endpoint."""

import os, json, secrets, hashlib
from pathlib import Path
from datetime import datetime, timezone
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from app import trading, ledger
from app.store import now


def cipher():
    key = os.getenv("EYE_ENCRYPTION_KEY")
    if not key:
        path = Path(__file__).resolve().parents[2] / "runtime/encryption.key"
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(Fernet.generate_key())
            except FileExistsError:
                pass
        key = path.read_bytes()
    return Fernet(key)


def seal(data):
    return cipher().encrypt(json.dumps(data).encode()).decode()


def unseal(value):
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except InvalidToken:
        raise HTTPException(
            503, "Credential encryption key is unavailable; restore it or reconnect"
        )


def credentials(data):
    value=unseal(data["secret"])
    if data.get("credential_mode")=="hosted":
        return {**value,"api_key":os.getenv("KITE_API_KEY", ""),"api_secret":os.getenv("KITE_API_SECRET", "")}
    return value


def save(db, owner, provider, credentials):
    if provider not in ("kite", "upstox"):
        raise HTTPException(422, "Supported brokers: kite, upstox")
    old = trading.get(db, owner, "connection", provider)
    data = {
        **(old.data if old else {}),
        "provider": provider,
        "secret": seal(credentials),
        "connected_at": now(),
        "status": "configured",
        "last_sync": None,
        "error": None,
    }
    trading.put(db, owner, "connection", provider, data)
    return public(data)


def public(d):
    return {k: v for k, v in d.items() if k != "secret"}


def provider_timestamp(value):
    from zoneinfo import ZoneInfo

    if isinstance(value, (int, float)) or str(value).isdigit():
        number = float(value)
        return datetime.fromtimestamp(
            number / 1000 if number > 1e11 else number, timezone.utc
        ).isoformat()
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return stamp.astimezone(timezone.utc).isoformat()


def sync(db, owner, provider):
    record = trading.get(db, owner, "connection", provider)
    if not record:
        raise HTTPException(404, "Connect this broker first")
    c = credentials(record.data)
    token = c.get("access_token")
    if not token:
        raise HTTPException(409, "Complete broker authorization first")
    try:
        with httpx.Client(timeout=20) as client:
            if provider == "kite":
                headers = {
                    "Authorization": f"token {c['api_key']}:{token}",
                    "X-Kite-Version": "3",
                }

                def read(path):
                    r = client.get("https://api.kite.trade" + path, headers=headers)
                    r.raise_for_status()
                    return r.json()["data"]

                trades = read("/trades")
                holdings = read("/portfolio/holdings")
                rows = [
                    {
                        "external_id": str(t["trade_id"]),
                        "symbol": t["tradingsymbol"],
                        "side": t["transaction_type"],
                        "qty": str(t["quantity"]),
                        "price": str(t["average_price"]),
                        "fees": "",
                        "currency": "INR",
                        "executed_at": provider_timestamp(t["fill_timestamp"]),
                    }
                    for t in trades
                ]
                reported = [
                    {
                        "symbol": h["tradingsymbol"],
                        "qty": h.get("quantity", 0) + h.get("t1_quantity", 0),
                        "average_price":h.get("average_price"),
                        "last_price":h.get("last_price"),
                        "exchange":h.get("exchange"),"currency":"INR",
                        "isin":h.get("isin"),"provider_pnl":h.get("pnl"),
                    }
                    for h in holdings
                ]
            else:
                headers = {
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                }

                def read(path):
                    r = client.get("https://api.upstox.com/v2" + path, headers=headers)
                    r.raise_for_status()
                    return r.json()["data"]

                trades = read("/order/trades/get-trades-for-day")
                holdings = read("/portfolio/long-term-holdings")
                rows = [
                    {
                        "external_id": str(t["trade_id"]),
                        "symbol": t.get("trading_symbol", t.get("tradingsymbol", "")),
                        "side": t["transaction_type"],
                        "qty": str(t["quantity"]),
                        "price": str(t["average_price"]),
                        "fees": "",
                        "currency": "INR",
                        "executed_at": provider_timestamp(t["exchange_timestamp"]),
                    }
                    for t in trades
                ]
                reported = [
                    {
                        "symbol": h.get("trading_symbol", h.get("tradingsymbol", "")),
                        "qty": h["quantity"],
                        "average_price":h.get("average_price"),
                        "last_price":h.get("last_price"),
                        "exchange":h.get("exchange"),"currency":"INR",
                        "isin":h.get("isin"),"provider_pnl":h.get("pnl"),
                    }
                    for h in holdings
                ]
        buffer = __import__("io").StringIO()
        writer = __import__("csv").DictWriter(buffer, fieldnames=ledger.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        parsed = ledger.parse_csv(buffer.getvalue())
        if parsed["errors"]:
            raise HTTPException(
                502, "Broker returned invalid trade fields; nothing imported"
            )
        result = ledger.import_rows(db, owner, provider, parsed["rows"])
        trading.put(
            db,
            owner,
            "broker_holdings",
            provider,
            {"rows": reported, "retrieved_at": now(), "source": provider+" portfolio holdings", "price_time_note":"Provider snapshot; individual price observation times are not supplied by this holdings endpoint."},
        )
        record.data = {
            **record.data,
            "status": "connected",
            "last_sync": now(),
            "error": None,
            "fee_note": "Daily trade endpoints do not include final contract-note fees. Import fee-complete CSV for net figures.",
        }
        return {**result, "connection": public(record.data)}
    except (httpx.HTTPError, KeyError, ValueError) as e:
        record.data = {
            **record.data,
            "status": "error",
            "error": "Broker sync failed. Check token expiry and broker access.",
            "last_attempt": now(),
        }
        return {"connection": public(record.data), "error": record.data["error"]}


def refresh_user_quotes(owner, credentials, provider):
    """Only the connected user's observations are stored under their owner ID."""
    from app import market
    from zoneinfo import ZoneInfo

    if provider != "kite" or not credentials.get("access_token"):
        return
    symbols = [
        m["symbol"]
        for m in market.catalog()
        if m.get("segment", "equities") == "equities"
    ]
    response = httpx.get(
        "https://api.kite.trade/quote",
        params=[("i", "NSE:" + s) for s in symbols],
        headers={
            "X-Kite-Version": "3",
            "Authorization": f"token {credentials['api_key']}:{credentials['access_token']}",
        },
        timeout=20,
    )
    response.raise_for_status()
    quotes = {}
    for key, v in response.json()["data"].items():
        stamp = v.get("last_trade_time")
        if not stamp:
            continue
        dt = datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        sym = key.split(":", 1)[1]
        quotes[sym] = {
            "symbol": sym,
            "price": float(v["last_price"]),
            "observed_at": dt.astimezone(timezone.utc).isoformat(),
            "status": "live",
            "source": "Your Zerodha Kite connection",
            "tradable": True,
        }
    market.persist_quotes(owner, quotes)


def options(db, owner, underlying, expiry=None):
    instruments = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank"}
    if underlying not in instruments:
        raise HTTPException(422, "Supported underlyings: NIFTY, BANKNIFTY")
    r = trading.get(db, owner, "connection", "upstox")
    if not r:
        raise HTTPException(
            409, "Connect Upstox to retrieve actual option contracts and quotes"
        )
    c = credentials(r.data)
    headers = {
        "Authorization": "Bearer " + c.get("access_token", ""),
        "Accept": "application/json",
    }
    key = instruments[underlying]
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(
                "https://api.upstox.com/v2/option/contract",
                params={"instrument_key": key},
                headers=headers,
            )
            response.raise_for_status()
            contracts = response.json()["data"]
            expiries = sorted({x["expiry"] for x in contracts})
            if not expiry:
                return {
                    "underlying": underlying,
                    "expiries": expiries,
                    "contracts": contracts,
                    "source": "Your Upstox connection",
                    "retrieved_at": now(),
                }
            if expiry not in expiries:
                raise HTTPException(422, "Choose an available expiry")
            response = client.get(
                "https://api.upstox.com/v2/option/chain",
                params={"instrument_key": key, "expiry_date": expiry},
                headers=headers,
            )
            response.raise_for_status()
            chain = response.json()["data"]
            call = sum(
                float(x.get("call_options", {}).get("market_data", {}).get("oi", 0))
                for x in chain
            )
            put = sum(
                float(x.get("put_options", {}).get("market_data", {}).get("oi", 0))
                for x in chain
            )
        from app.workbench import option_summary
        snapshot = {
            "analytics":option_summary(chain),
            "underlying": underlying,
            "expiry": expiry,
            "expiries": expiries,
            "rows": chain,
            "put_call_ratio": put / call if call else None,
            "source": "Your Upstox connection",
            "retrieved_at": now(),
            "greeks_note": "Provider-supplied option sensitivities are model-derived estimates, distinct from observed premiums and open interest.",
        }
        trading.put(db, owner, "option_snapshot", underlying, snapshot)
        return snapshot
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(
            502,
            "Option provider unavailable or token expired; no synthetic chain is substituted",
        )


def authorize(db, owner, provider):
    from urllib.parse import urlencode
    from datetime import timedelta

    r = trading.get(db, owner, "connection", provider)
    if not r:
        raise HTTPException(409, "Save the broker application credentials first")
    c = credentials(r.data)
    state = secrets.token_urlsafe(32)
    trading.put(
        db,
        owner,
        "oauth_state",
        hashlib.sha256(state.encode()).hexdigest(),
        {
            "provider": provider,
            "expires": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        },
    )
    base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    if provider == "kite":
        if not c.get("api_key") or not c.get("api_secret"):
            raise HTTPException(
                422, "Kite API key and secret are required for authorization"
            )
        return {
            "url": "https://kite.zerodha.com/connect/login?"
            + urlencode(
                {
                    "v": "3",
                    "api_key": c["api_key"],
                    "redirect_params": urlencode({"state": state}),
                }
            ),
            "callback": base + "/v1/connections/kite/callback",
        }
    if not c.get("client_id") or not c.get("client_secret"):
        raise HTTPException(
            422, "Upstox client ID and secret are required for authorization"
        )
    return {
        "url": "https://api.upstox.com/v2/login/authorization/dialog?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": c["client_id"],
                "redirect_uri": base + "/v1/connections/upstox/callback",
                "state": state,
            }
        ),
        "callback": base + "/v1/connections/upstox/callback",
    }


def callback(db, provider, state, code):
    from app.store import Record
    from sqlalchemy import select

    r = db.scalar(
        select(Record)
        .where(
            Record.kind == "oauth_state",
            Record.key == hashlib.sha256(state.encode()).hexdigest(),
        )
        .with_for_update()
    )
    if not r or r.data["expires"] < now() or r.data["provider"] != provider:
        raise HTTPException(422, "Authorization state invalid or expired")
    connection = trading.get(db, r.owner, "connection", provider)
    if not connection:raise HTTPException(409,"Broker connection was removed; restart login")
    c = credentials(connection.data)
    try:
        with httpx.Client(timeout=20) as client:
            if provider == "kite":
                checksum = hashlib.sha256(
                    (c["api_key"] + code + c["api_secret"]).encode()
                ).hexdigest()
                res = client.post(
                    "https://api.kite.trade/session/token",
                    data={
                        "api_key": c["api_key"],
                        "request_token": code,
                        "checksum": checksum,
                    },
                    headers={"X-Kite-Version": "3"},
                )
            else:
                res = client.post(
                    "https://api.upstox.com/v2/login/authorization/token",
                    data={
                        "code": code,
                        "client_id": c["client_id"],
                        "client_secret": c["client_secret"],
                        "redirect_uri": os.getenv(
                            "PUBLIC_BASE_URL", "http://127.0.0.1:8000"
                        ).rstrip("/")
                        + "/v1/connections/upstox/callback",
                        "grant_type": "authorization_code",
                    },
                )
            try:
                res.raise_for_status()
                j = res.json()
                token = (
                    j["data"]["access_token"] if provider == "kite" else j["access_token"]
                )
            except (httpx.HTTPError, KeyError, ValueError):
                raise HTTPException(
                    502, "Broker authorization failed; restart the connection flow"
                )
    except httpx.HTTPError:
        raise HTTPException(502,"Zerodha authorization could not reach the provider. Restart login; no token was saved.")
    connection.data = {
        **connection.data,
        "secret": seal({"access_token":token} if connection.data.get("credential_mode")=="hosted" else {**c,"access_token":token}),
        "status": "authorized",
        "authorized_at": now(),
    }
    db.delete(r)
    return {"provider": provider, "status": "authorized"}
