"""Decimal cash ledger, user-owned orders, and deterministic historical replay."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from fastapi import HTTPException
from app.store import Record, now
from app.market import history, latest, meta
from app import market


def money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ident():
    return uuid.uuid4().hex


def records(db, owner, kind):
    return list(
        db.scalars(select(Record).where(Record.owner == owner, Record.kind == kind))
    )


def get(db, owner, kind, key):
    return db.scalar(
        select(Record).where(
            Record.owner == owner, Record.kind == kind, Record.key == key
        )
    )


def put(db, owner, kind, key, data):
    r = get(db, owner, kind, key)
    if r:
        r.data = data
    else:
        r = Record(id=ident(), owner=owner, kind=kind, key=key, data=data)
        db.add(r)
    db.flush()
    return r


def account(db, owner, scope="paper"):
    r = get(db, owner, "account", scope)
    if not r:
        r = put(
            db,
            owner,
            "account",
            scope,
            {
                "cash": "1000000.00",
                "realized": "0.00",
                "initial": "1000000.00",
                "positions": {},
                "reserved_cash": "0.00",
                "reserved_shares": {},
            },
        )
    return r


def execute(wallet, order, price):
    """Caller must hold the user's database lock. No negative balances/shorts."""
    a = {**wallet, "positions": {k: dict(v) for k, v in wallet["positions"].items()}}
    p = money(price)
    qty = order["qty"]
    total = p * qty
    fee = money(total * Decimal(str(a.get("fee_bps", 0))) / 10000)
    cash = money(a["cash"])
    sym = order["symbol"]
    pos = a["positions"].get(sym, {"qty": 0, "cost": "0.00"})
    if order["side"] == "BUY":
        if cash < total + fee:
            raise HTTPException(409, "Insufficient virtual cash")
        a["cash"] = str(cash - total - fee)
        a["positions"][sym] = {
            "qty": pos["qty"] + qty,
            "cost": str(money(pos["cost"]) + total + fee),
        }
    else:
        if pos["qty"] < qty:
            raise HTTPException(409, "Insufficient shares; short selling is disabled")
        cost = money(Decimal(pos["cost"]) * qty / pos["qty"])
        a["cash"] = str(cash + total - fee)
        a["realized"] = str(money(a["realized"]) + total - fee - cost)
        if pos["qty"] == qty:
            a["positions"].pop(sym, None)
        else:
            a["positions"][sym] = {
                "qty": pos["qty"] - qty,
                "cost": str(money(pos["cost"]) - cost),
            }
    return a


def reserve(a, o):
    a = {**a, "reserved_shares": dict(a.get("reserved_shares", {}))}
    if o["side"] == "BUY":
        required = money(o["price"]) * o["qty"]
        required += money(required * Decimal(str(a.get("fee_bps", 0))) / 10000)
        if money(a["cash"]) - money(a.get("reserved_cash", 0)) < required:
            raise HTTPException(409, "Insufficient unreserved cash")
        a["reserved_cash"] = str(money(a.get("reserved_cash", 0)) + required)
    else:
        held = a["positions"].get(o["symbol"], {}).get("qty", 0)
        used = a["reserved_shares"].get(o["symbol"], 0)
        if held - used < o["qty"]:
            raise HTTPException(409, "Insufficient unreserved shares")
        a["reserved_shares"][o["symbol"]] = used + o["qty"]
    return a


def release(a, o):
    a = {**a, "reserved_shares": dict(a.get("reserved_shares", {}))}
    if o["side"] == "BUY":
        a["reserved_cash"] = str(
            money(a.get("reserved_cash", 0))
            - money(o["price"]) * o["qty"]
            - money(
                money(o["price"]) * o["qty"] * Decimal(str(a.get("fee_bps", 0))) / 10000
            )
        )
    else:
        a["reserved_shares"][o["symbol"]] = (
            a["reserved_shares"].get(o["symbol"], 0) - o["qty"]
        )
    return a


def portfolio(db, owner, scope="paper", prices=None):
    a = account(db, owner, scope).data
    positions = []
    value = Decimal(0)
    unrealized = Decimal(0)
    for sym, p in a["positions"].items():
        q = (
            prices.get(sym)
            if prices is not None
            else (market.live_quote(sym, owner, db=db) or latest(sym))
        )
        price = money(q["price"]) if q else Decimal(0)
        val = price * p["qty"]
        cost = money(p["cost"])
        value += val
        unrealized += val - cost
        positions.append(
            {
                "symbol": sym,
                "qty": p["qty"],
                "avg_price": float(cost / p["qty"]),
                "price": float(price),
                "value": float(val),
                "pnl": float(val - cost),
                "source": q.get("source") if q else None,
                "observed_at": q.get("observed_at") if q else None,
                "status": q.get("status") if q else "unavailable",
            }
        )
    return {
        **{
            k: float(money(a[k]))
            for k in ["cash", "initial", "realized", "reserved_cash"]
        },
        "positions": positions,
        "total": float(money(a["cash"]) + value),
        "unrealized": float(unrealized),
        "scope": scope,
        "currency": a.get("currency", "INR"),
        "valuation_note": "Positions use the displayed observation dates. Historical marks are not executable current quotes.",
    }


def submit(db, owner, req, scope="paper", replay=None):
    existing = get(db, owner, "order", req["request_id"])
    signature = {
        k: req.get(k)
        for k in (
            "symbol",
            "side",
            "qty",
            "order_type",
            "price",
            "reason",
            "forecast_version",
        )
    }
    if existing:
        if existing.data["scope"] != scope or existing.data["request"] != signature:
            raise HTTPException(409, "Request ID already used for a different order")
        return existing.data
    meta(req["symbol"])
    forecast_snapshot = None
    if req.get("forecast_version"):
        if replay:
            raise HTTPException(
                422, "Research forecasts cannot be attached inside historical replay"
            )
        import json

        valid = False
        for horizon in (1, 5):
            path = market.ROOT / "models" / f"{req['symbol']}_{horizon}_report.json"
            if path.exists():
                report = json.loads(path.read_text())
                if (
                    report["version"] == req["forecast_version"]
                    and report["data_sha256"] == meta(req["symbol"])["sha256"]
                ):
                    valid = True
                    forecast_snapshot = {
                        k: report[k]
                        for k in (
                            "version",
                            "selected_model",
                            "as_of",
                            "predicted_target",
                            "horizon_sessions",
                            "test",
                            "data_sha256",
                        )
                    }
                    break
        if not valid:
            raise HTTPException(
                422, "Forecast version is unavailable or does not match this instrument"
            )
    q = None if replay else market.live_quote(req["symbol"], owner, db=db)
    if scope == "paper" and (
        not q or not q.get("tradable", True) or meta(req["symbol"])["currency"] != "INR"
    ):
        raise HTTPException(
            409,
            "No fresh executable quote. Open Market Replay to trade historical observations.",
        )
    if replay and req["symbol"] != replay["symbol"]:
        raise HTTPException(422, "Replay orders must use the session instrument")
    acc = account(db, owner, scope)
    o = {
        **req,
        "id": req["request_id"],
        "request": signature,
        "scope": scope,
        "dataset_version": replay.get("dataset_version")
        if replay
        else meta(req["symbol"])["sha256"],
        "created_at": now(),
        "status": "PENDING",
        "fill_price": None,
        "filled_at": None,
        "submitted_index": replay["index"] if replay else None,
    }
    reserve_price = (
        req.get("price")
        if req["order_type"] == "LIMIT"
        else (q["price"] if q else replay["current_price"])
    )
    o["price"] = str(money(reserve_price))
    acc.data = reserve(acc.data, o)
    if not replay and (
        req["order_type"] == "MARKET"
        or (req["side"] == "BUY" and q["price"] <= float(o["price"]))
        or (req["side"] == "SELL" and q["price"] >= float(o["price"]))
    ):
        acc.data = execute(release(acc.data, o), o, q["price"])
        o.update(
            status="FILLED",
            fill_price=float(money(q["price"])),
            filled_at=q["observed_at"],
            source=q["source"],
        )
    put(db, owner, "order", o["id"], o)
    if scope == "paper" and o["status"] == "FILLED":
        snapshot(db, owner)
    put(
        db,
        owner,
        "journal",
        o["id"],
        {
            "order_id": o["id"],
            "symbol": o["symbol"],
            "reason": req.get("reason", ""),
            "forecast_version": req.get("forecast_version"),
            "forecast_snapshot": forecast_snapshot,
            "observed_at": replay["date"] if replay else q["observed_at"],
            "observed_price": replay["current_price"] if replay else q["price"],
            "scope": scope,
            "created_at": now(),
            "outcome_status": o["status"],
        },
    )
    return o


def cancel(db, owner, order_id):
    r = get(db, owner, "order", order_id)
    if not r:
        raise HTTPException(404, "Order not found")
    if r.data["status"] != "PENDING":
        raise HTTPException(409, "Only pending orders can be cancelled")
    a = account(db, owner, r.data["scope"])
    a.data = release(a.data, r.data)
    r.data = {**r.data, "status": "CANCELLED"}
    return r.data


def replay_view(db, owner, r):
    d = r.data
    rows = history(d["symbol"], d.get("dataset_version"))
    visible = rows[: d["index"] + 1]
    price = visible[-1]["close"]
    start = rows[d["start_index"]]["close"]
    p = portfolio(
        db,
        owner,
        r.key,
        {
            d["symbol"]: {
                "price": price,
                "source": meta(d["symbol"])["source"],
                "observed_at": visible[-1]["date"],
                "status": "replay",
            }
        },
    )
    return {
        **d,
        "id": r.key,
        "currency": meta(d["symbol"])["currency"],
        "date": visible[-1]["date"],
        "current_price": price,
        "candles": visible[-150:],
        "portfolio": p,
        "benchmark_value": 1000000 * price / start,
        "benchmark_return_pct": (price / start - 1) * 100,
        "ended": d["index"] >= len(rows) - 1,
        "source": meta(d["symbol"])["source"],
        "mode": "Historical replay",
        "execution_rule": f"Simulation costs: {d.get('fee_bps', 0)} basis points per fill. Orders fill at the next session open. Limits fill at a better open or at the limit if the bar crosses it. Intraday ordering is unknown. Benchmark uses fractional buy-and-hold before costs.",
    }


def advance(db, owner, r, steps, on_observation=None):
    d = dict(r.data)
    rows = history(d["symbol"], d.get("dataset_version"))
    acc = account(db, owner, r.key)
    for idx in range(d["index"] + 1, min(d["index"] + steps, len(rows) - 1) + 1):
        bar = rows[idx]
        for rec in sorted(
            records(db, owner, "order"), key=lambda x: x.data["created_at"]
        ):
            o = dict(rec.data)
            if (
                o["scope"] != r.key
                or o["status"] != "PENDING"
                or o["submitted_index"] >= idx
            ):
                continue
            fill = None
            limit = float(o["price"])
            if o["order_type"] == "MARKET":
                fill = bar["open"]
            elif o["side"] == "BUY" and bar["low"] <= limit:
                fill = min(bar["open"], limit)
            elif o["side"] == "SELL" and bar["high"] >= limit:
                fill = max(bar["open"], limit)
            if fill is not None:
                released = release(acc.data, o)
                # Gap-up market buys may exceed the reserved estimate; never spend another order's reservation.
                available = money(released["cash"]) - money(
                    released.get("reserved_cash", 0)
                )
                if (
                    o["side"] == "BUY"
                    and money(fill) * o["qty"]
                    + money(
                        money(fill)
                        * o["qty"]
                        * Decimal(str(released.get("fee_bps", 0)))
                        / 10000
                    )
                    > available
                ):
                    acc.data = released
                    o.update(
                        status="REJECTED",
                        rejection="Next-bar price exceeded available unreserved cash",
                    )
                else:
                    acc.data = execute(released, o, fill)
                    o.update(
                        status="FILLED",
                        fill_price=float(money(fill)),
                        filled_at=bar["date"],
                        source=meta(d["symbol"])["source"],
                    )
                rec.data = o
        d["index"] = idx
        if on_observation:
            on_observation(d["symbol"], bar["close"], bar["date"])
        mark = portfolio(
            db,
            owner,
            r.key,
            {
                d["symbol"]: {
                    "price": bar["close"],
                    "source": meta(d["symbol"])["source"],
                    "observed_at": bar["date"],
                    "status": "replay",
                }
            },
        )
        d["equity"] = [
            *d.get("equity", []),
            {
                "date": bar["date"],
                "value": mark["total"],
                "benchmark": 1000000 * bar["close"] / rows[d["start_index"]]["close"],
            },
        ]
    r.data = d
    db.flush()
    return replay_view(db, owner, r)


def snapshot(db, owner):
    p = portfolio(db, owner)
    stamp = now()[:10]
    put(
        db,
        owner,
        "equity",
        "paper:" + stamp,
        {
            "date": stamp,
            "value": p["total"],
            "benchmark": p["initial"],
            "scope": "paper",
            "observation_note": p["valuation_note"],
        },
    )
