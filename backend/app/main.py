"""InvestorsEYE v2. Only this application is mounted; legacy demos are not served."""

import os, hashlib, secrets, json, time
from pathlib import Path
from datetime import datetime, timedelta, timezone, date
from contextlib import asynccontextmanager
from typing import Literal, Optional
from decimal import Decimal
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    Query,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.store import DB, User, Session, Record, init, now, URL
from app import market, trading

ROOT = Path(__file__).resolve().parents[2]
SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
ORIGINS = set(
    os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
)


@asynccontextmanager
async def lifespan(app):
    init()
    yield


app = FastAPI(title="InvestorsEYE", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def security(request: Request, call_next):
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and request.url.path != "/v1/webhooks/whatsapp"
    ):
        origin = request.headers.get("origin")
        extension = bool(
            origin
            and __import__("re").fullmatch(r"chrome-extension://[a-p]{32}", origin)
            and request.headers.get("authorization", "").startswith("Bearer ")
        )
        if origin and origin not in ORIGINS and not extension:
            return Response("Origin not allowed", 403)
        if request.headers.get("x-eye-client") != "workspace":
            return Response("Missing request protection header", 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws://localhost:8000 ws://127.0.0.1:8000; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def database():
    with DB() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def current(request: Request, db=Depends(database, scope="function")):
    token = request.headers.get("authorization", "").removeprefix(
        "Bearer "
    ) or request.cookies.get("eye_session", "")
    s = db.get(Session, hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not s or s.expires <= now():
        raise HTTPException(401, "Please sign in")
    user = db.scalar(select(User).where(User.id == s.owner).with_for_update())
    if not user:
        raise HTTPException(401, "Please sign in")
    return user


def public_user(u):
    return {"id": u.id, "name": u.name, "email": u.email}


def hash_password(p, salt=None):
    salt = salt or secrets.token_hex(16)
    return (
        salt
        + ":"
        + hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 600000).hex()
    )


def set_session(db, u, response):
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    db.add(
        Session(
            digest=hashlib.sha256(token.encode()).hexdigest(),
            owner=u.id,
            expires=expires.isoformat(),
        )
    )
    response.set_cookie(
        "eye_session",
        token,
        httponly=True,
        secure=SECURE,
        samesite="strict",
        max_age=604800,
        path="/",
    )


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email")
        return v


class Register(Login):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_valid(cls, v):
        if not v.strip():
            raise ValueError("Name required")
        return v.strip()


class Order(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    symbol: str = Field(pattern=r"^[A-Z0-9]{1,20}$")
    side: Literal["BUY", "SELL"]
    qty: int = Field(gt=0, le=100000, strict=True)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=14, decimal_places=2
    )
    reason: str = Field(default="", max_length=2000)
    forecast_version: Optional[str] = Field(default=None, max_length=150)


class ReplayCreate(BaseModel):
    fee_bps: int = Field(default=0, ge=0, le=100)
    symbol: str
    start_date: date


class Step(BaseModel):
    steps: int = Field(default=1, ge=1, le=30)


class AlertCreate(BaseModel):
    kind: Literal[
        "price", "percent_move", "rsi", "nav_update", "portfolio_loss", "open_interest"
    ] = "price"
    window: int = Field(default=1, ge=1, le=252)
    symbol: str
    direction: Literal["above", "below"]
    target: Decimal = Field(max_digits=14, decimal_places=2)
    scope: str = "paper"


class Quiz(BaseModel):
    lesson_id: str
    answer: int = Field(ge=0, le=3)


LESSONS = [
    {
        "id": "risk",
        "title": "Risk before returns",
        "level": "Foundations",
        "minutes": 3,
        "body": "A forecast describes one possible outcome. Position size determines how much a wrong decision costs. In this workspace, money is virtual, but a concentrated position still makes its value sensitive to one company. Compare the portfolio with buy-and-hold and record your reasoning before trading.",
        "question": "Which action reduces exposure to one company?",
        "options": [
            "Increasing its position",
            "Spreading holdings across companies",
            "Ignoring losses",
            "Following the highest forecast",
        ],
        "correct": 1,
        "explanation": "Diversification spreads company-specific exposure. It cannot eliminate market-wide losses.",
    },
    {
        "id": "momentum",
        "title": "Read momentum, not promises",
        "level": "Analysis",
        "minutes": 4,
        "body": "RSI compares recent gains and losses. An elevated reading is evidence of recent strength, not a guarantee of an imminent fall. MACD compares exponential averages. Both indicators use past prices and can fail during changing market conditions. Inspect the chart and data date alongside them.",
        "question": "Does RSI above 70 guarantee a price fall?",
        "options": [
            "Yes, immediately",
            "Only on Mondays",
            "No, a strong trend can continue",
            "Yes, within five sessions",
        ],
        "correct": 2,
        "explanation": "Momentum can remain elevated. An indicator is evidence to interpret, not a guaranteed trade.",
    },
    {
        "id": "evaluation",
        "title": "Challenge the prediction",
        "level": "Model lab",
        "minutes": 4,
        "body": "A useful forecasting model must be tested on later observations it never saw during training. Compare it with predicting that the next price equals the current price. Training error is not independent evidence. A lower test error does not guarantee a profitable strategy once execution costs and risk are considered.",
        "question": "Which result is the strongest evidence here?",
        "options": [
            "A perfect training fit",
            "A high invented confidence score",
            "A chart that looks smooth",
            "Performance on untouched later data versus a baseline",
        ],
        "correct": 3,
        "explanation": "Chronological held-out testing compares the model with a simple alternative on unseen observations.",
    },
]


def rate_limit(db, request, email):
    # No raw IPs or passwords are stored. Each origin/email pair has a bounded window.
    key = hashlib.sha256(
        ((request.client.host if request.client else "local") + email).encode()
    ).hexdigest()
    r = trading.get(db, "system", "login_limit", key)
    ts = time.time()
    d = r.data if r else {"start": ts, "count": 0}
    if ts - d["start"] > 600:
        d = {"start": ts, "count": 0}
    if d["count"] >= 20:
        raise HTTPException(429, "Too many attempts. Try again in ten minutes.")
    trading.put(db, "system", "login_limit", key, {**d, "count": d["count"] + 1})
    db.commit()


@app.get("/health")
def health(db=Depends(database, scope="function")):
    db.execute(select(User.id).limit(1))
    return {
        "status": "healthy",
        "database": "postgresql" if URL.startswith("postgres") else "sqlite",
        "instruments": len(market.catalog()),
        "version": "2.0.0",
    }


@app.post("/v1/auth/register")
def register(
    req: Register,
    request: Request,
    response: Response,
    db=Depends(database, scope="function"),
):
    rate_limit(db, request, req.email)
    if len(req.password) < 10:
        raise HTTPException(422, "Use at least 10 characters for your password")
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(409, "This email is already registered")
    u = User(
        id=trading.ident(),
        email=req.email,
        name=req.name,
        password=hash_password(req.password),
    )
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "This email is already registered")
    trading.account(db, u.id)
    set_session(db, u, response)
    return public_user(u)


@app.post("/v1/auth/login")
def login(
    req: Login,
    request: Request,
    response: Response,
    db=Depends(database, scope="function"),
):
    rate_limit(db, request, req.email)
    u = db.scalar(select(User).where(User.email == req.email))
    # A dummy hash keeps unknown-account work comparable to wrong-password work.
    stored = u.password if u else "0" * 32 + ":" + "0" * 64
    if not secrets.compare_digest(
        hash_password(req.password, stored.split(":")[0]), stored
    ):
        raise HTTPException(401, "Email or password is incorrect")
    set_session(db, u, response)
    return public_user(u)


@app.get("/v1/auth/me")
def me(u=Depends(current)):
    return public_user(u)


@app.post("/v1/auth/logout")
def logout(
    request: Request, response: Response, db=Depends(database, scope="function")
):
    token = request.headers.get("authorization", "").removeprefix(
        "Bearer "
    ) or request.cookies.get("eye_session", "")
    db.execute(
        delete(Session).where(
            Session.digest == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    response.delete_cookie("eye_session")
    return {"success": True}


@app.get("/v1/instruments/search")
def instruments(q: str = "", segment: str | None = None):
    return [
        x
        for x in market.catalog()
        if q.lower() in (x["symbol"] + " " + x["name"]).lower()
        and (not segment or x.get("segment", "equities") == segment)
    ]


def optional_owner(request):
    if request is None:
        return "system"
    token = request.headers.get("authorization", "").removeprefix(
        "Bearer "
    ) or request.cookies.get("eye_session", "")
    if not token:
        return "system"
    with DB() as db:
        session = db.get(Session, hashlib.sha256(token.encode()).hexdigest())
        return session.owner if session and session.expires > now() else "system"


@app.get("/v1/quotes")
def quotes(request: Request):
    return [
        market.live_quote(x["symbol"], optional_owner(request))
        or market.latest(x["symbol"])
        for x in market.catalog()
    ]


@app.get("/v1/quotes/{symbol}")
def quote(symbol: str, request: Request):
    return market.live_quote(symbol, optional_owner(request)) or market.latest(symbol)


@app.get("/v1/candles/{symbol}")
def candles(symbol: str, limit: int = Query(default=180, ge=30, le=2000)):
    return market.history(symbol)[-limit:]


@app.get("/v1/analysis/technical/{symbol}")
def analysis(symbol: str):
    return market.indicators(symbol)


@app.get("/v1/watchlist")
def watchlist(u=Depends(current), db=Depends(database, scope="function")):
    return [r.key for r in trading.records(db, u.id, "watch")]


@app.post("/v1/watchlist/{symbol}")
def watch(symbol: str, u=Depends(current), db=Depends(database, scope="function")):
    market.meta(symbol)
    trading.put(db, u.id, "watch", symbol, {"created_at": now()})
    return {"symbol": symbol}


@app.delete("/v1/watchlist/{symbol}")
def unwatch(symbol: str, u=Depends(current), db=Depends(database, scope="function")):
    r = trading.get(db, u.id, "watch", symbol)
    if r:
        db.delete(r)
    return {"success": True}


@app.get("/v1/paper/portfolio")
def portfolio(u=Depends(current), db=Depends(database, scope="function")):
    return trading.portfolio(db, u.id)


@app.get("/v1/paper/performance")
def performance(u=Depends(current), db=Depends(database, scope="function")):
    return sorted(
        [
            r.data
            for r in trading.records(db, u.id, "equity")
            if r.data.get("scope") == "paper"
        ],
        key=lambda x: x["date"],
    )


@app.get("/v1/paper/orders")
def orders(
    scope: str = "paper", u=Depends(current), db=Depends(database, scope="function")
):
    return sorted(
        [
            r.data
            for r in trading.records(db, u.id, "order")
            if r.data["scope"] == scope
        ],
        key=lambda x: x["created_at"],
        reverse=True,
    )


@app.post("/v1/paper/orders")
def order(req: Order, u=Depends(current), db=Depends(database, scope="function")):
    if req.order_type == "LIMIT" and req.price is None:
        raise HTTPException(422, "Limit price required")
    d = req.model_dump(mode="json")
    return trading.submit(db, u.id, d)


@app.delete("/v1/paper/orders/{order_id}")
def cancel(order_id: str, u=Depends(current), db=Depends(database, scope="function")):
    return trading.cancel(db, u.id, order_id)


@app.post("/v1/replays")
def create_replay(
    req: ReplayCreate, u=Depends(current), db=Depends(database, scope="function")
):
    rows = market.history(req.symbol)
    idx = next(
        (i for i, x in enumerate(rows) if x["date"] >= req.start_date.isoformat()), None
    )
    if idx is None or idx < 60 or idx >= len(rows) - 2:
        raise HTTPException(
            422,
            "Choose a session with 60 earlier observations and at least two later sessions",
        )
    rid = trading.ident()
    r = trading.put(
        db,
        u.id,
        "replay",
        rid,
        {
            "symbol": req.symbol,
            "dataset_version": market.meta(req.symbol)["sha256"],
            "fee_bps": req.fee_bps,
            "index": idx,
            "start_index": idx,
            "created_at": now(),
            "equity": [
                {"date": rows[idx]["date"], "value": 1000000, "benchmark": 1000000}
            ],
        },
    )
    acc = trading.account(db, u.id, rid)
    acc.data = {
        **acc.data,
        "currency": market.meta(req.symbol)["currency"],
        "fee_bps": req.fee_bps,
    }
    return trading.replay_view(db, u.id, r)


@app.get("/v1/replays")
def replays(u=Depends(current), db=Depends(database, scope="function")):
    return [
        {
            "id": r.key,
            "symbol": r.data["symbol"],
            "created_at": r.data["created_at"],
            "date": market.history(r.data["symbol"], r.data.get("dataset_version"))[
                r.data["index"]
            ]["date"],
        }
        for r in trading.records(db, u.id, "replay")
    ]


def owned_replay(db, u, rid):
    r = trading.get(db, u.id, "replay", rid)
    if not r:
        raise HTTPException(404, "Replay not found")
    return r


@app.get("/v1/replays/{rid}")
def replay(rid: str, u=Depends(current), db=Depends(database, scope="function")):
    return trading.replay_view(db, u.id, owned_replay(db, u, rid))


@app.post("/v1/replays/{rid}/advance")
def advance(
    rid: str, req: Step, u=Depends(current), db=Depends(database, scope="function")
):
    r = owned_replay(db, u, rid)
    v = trading.advance(
        db,
        u.id,
        r,
        req.steps,
        lambda symbol, price, stamp: evaluate_alerts(
            db, u.id, rid, symbol, price, stamp
        ),
    )
    return v


@app.post("/v1/replays/{rid}/orders")
def replay_order(
    rid: str, req: Order, u=Depends(current), db=Depends(database, scope="function")
):
    r = owned_replay(db, u, rid)
    v = trading.replay_view(db, u.id, r)
    if v["ended"]:
        raise HTTPException(409, "Replay ended; create another session")
    if req.order_type == "LIMIT" and req.price is None:
        raise HTTPException(422, "Limit price required")
    return trading.submit(db, u.id, req.model_dump(mode="json"), rid, v)


@app.get("/v1/replays/{rid}/analysis")
def replay_analysis(
    rid: str, u=Depends(current), db=Depends(database, scope="function")
):
    v = trading.replay_view(db, u.id, owned_replay(db, u, rid))
    return market.indicators(v["symbol"], v["date"], v.get("dataset_version"))


@app.get("/v1/predictions/{symbol}")
def prediction(symbol: str, horizon: int | None = None):
    segment = market.meta(symbol).get("segment", "equities")
    allowed = (
        (21,)
        if segment == "funds"
        else (3,)
        if segment == "intraday"
        else (1, 24)
        if segment == "crypto"
        else (1, 5)
    )
    horizon = horizon or allowed[0]
    if horizon not in allowed:
        raise HTTPException(422, "Choose a supported horizon for this market segment")
    path = ROOT / "models" / f"{symbol}_{horizon}_report.json"
    if not path.exists():
        raise HTTPException(
            409, "No evaluated trained model is available for this instrument yet"
        )
    report = json.loads(path.read_text())
    if report.get("data_sha256") != market.meta(symbol)["sha256"]:
        raise HTTPException(
            409, "Dataset changed. Retrain this model before serving its report."
        )
    return report


def csv_response(rows, filename):
    import csv, io

    stream = io.StringIO()
    writer = csv.writer(stream)
    for row in rows:
        writer.writerow(
            [
                ("'" + str(v))
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                else v
                for v in row
            ]
        )
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/v1/predictions/{symbol}/export.csv")
def export_prediction(symbol: str, horizon: int = 1):
    report = prediction(symbol, horizon)
    rows = [
        [
            "symbol",
            "version",
            "model",
            "date",
            "actual_close",
            "predicted_close",
            "last_price_baseline",
        ]
    ]
    rows.extend(
        [
            [
                symbol,
                report["version"],
                report["selected_model"],
                p["date"],
                p["actual"],
                p["prediction"],
                p["baseline"],
            ]
            for p in report["test_points"]
        ]
    )
    return csv_response(rows, f"{symbol}-{horizon}-session-evaluation.csv")


@app.get("/v1/replays/{rid}/export.csv")
def export_replay(rid: str, u=Depends(current), db=Depends(database, scope="function")):
    r = owned_replay(db, u, rid)
    return csv_response(
        [["date", "portfolio_value", "buy_and_hold_value"]]
        + [[p["date"], p["value"], p["benchmark"]] for p in r.data["equity"]],
        f"replay-{rid}.csv",
    )


@app.get("/v1/predictions/{symbol}/backtest")
def backtest(symbol: str, horizon: int = 1):
    return prediction(symbol, horizon)


@app.get("/v1/journal")
def journal(u=Depends(current), db=Depends(database, scope="function")):
    result = []
    for r in trading.records(db, u.id, "journal"):
        o = trading.get(db, u.id, "order", r.key)
        price = o.data.get("fill_price") if o else None
        scope = r.data["scope"]
        symbol = r.data["symbol"]
        mark = None
        if scope == "paper":
            mark = (market.live_quote(symbol, u.id, db=db) or market.latest(symbol))[
                "price"
            ]
        else:
            replay_record = trading.get(db, u.id, "replay", scope)
            if replay_record:
                mark = market.history(
                    symbol, replay_record.data.get("dataset_version")
                )[replay_record.data["index"]]["close"]
        change = ((mark / price - 1) * 100) if mark and price else None
        result.append(
            {
                **r.data,
                "order": o.data if o else None,
                "fill_price": price,
                "marked_price": mark,
                "marked_change_pct": round(change, 2) if change is not None else None,
                "outcome_note": "Price change since this fill, not realized trade profit. Replay marks stop at the replay clock.",
            }
        )
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


# Alerts use actual crossing events; replay clocks and current quotes are isolated.
def evaluate_alerts(db, owner, scope, symbol, price, observed_at):
    for r in trading.records(db, owner, "alert"):
        a = dict(r.data)
        if a["scope"] != scope or a["symbol"] != symbol or not a["active"]:
            continue
        original_price = price
        kind = a.get("kind", "price")
        if kind == "open_interest":
            snapshot = trading.get(db, owner, "option_snapshot", symbol)
            if not snapshot:
                continue
            price = sum(
                float(x.get(side, {}).get("market_data", {}).get("oi", 0))
                for x in snapshot.data["rows"]
                for side in ("call_options", "put_options")
            )
        elif kind == "portfolio_loss":
            if scope == "paper":
                p = trading.portfolio(db, owner)
            else:
                p = trading.replay_view(
                    db, owner, trading.get(db, owner, "replay", scope)
                )["portfolio"]
            price = max(0, (p["initial"] - p["total"]) / p["initial"] * 100)
        elif kind in ("percent_move", "rsi"):
            replay_record = (
                trading.get(db, owner, "replay", scope) if scope != "paper" else None
            )
            version = (
                replay_record.data.get("dataset_version") if replay_record else None
            )
            rows = [
                x for x in market.history(symbol, version) if x["date"] <= observed_at
            ]
            if kind == "percent_move":
                n = a.get("window", 1)
                if len(rows) <= n:
                    continue
                price = (original_price / rows[-n - 1]["close"] - 1) * 100
            else:
                price = market.indicators(symbol, observed_at, version)["indicators"][
                    0
                ]["value"]
        prev = a.get("last_price")
        target = float(a["target"])
        crossed = prev is not None and (
            (prev < target <= price)
            if a["direction"] == "above"
            else (prev > target >= price)
        )
        if kind == "nav_update":
            crossed = bool(
                a.get("last_observed_at") and observed_at > a["last_observed_at"]
            )
        # Cooldown uses observation time so replay behavior is reproducible.
        stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00")).replace(
            tzinfo=timezone.utc
        )
        last = datetime.fromisoformat(a["last_fired"]) if a.get("last_fired") else None
        if crossed and (last is None or (stamp - last).total_seconds() >= 300):
            eid = trading.ident()
            trading.put(
                db,
                owner,
                "event",
                eid,
                {
                    "id": eid,
                    "alert_id": r.key,
                    "symbol": symbol,
                    "price": price,
                    "target": target,
                    "direction": a["direction"],
                    "observed_at": observed_at,
                    "scope": scope,
                },
            )
            from app.notifications import enqueue

            enqueue(
                db,
                owner,
                {
                    "id": eid,
                    "symbol": symbol,
                    "price": price,
                    "observed_at": observed_at,
                },
            )
            a["last_fired"] = stamp.isoformat()
        a["last_price"] = price
        a["last_observed_at"] = observed_at
        r.data = a
        price = original_price


@app.get("/v1/alerts")
def alerts(u=Depends(current), db=Depends(database, scope="function")):
    return [{"id": r.key, **r.data} for r in trading.records(db, u.id, "alert")]


@app.post("/v1/alerts")
def alert(req: AlertCreate, u=Depends(current), db=Depends(database, scope="function")):
    if req.kind == "open_interest":
        snapshot = trading.get(db, u.id, "option_snapshot", req.symbol)
        if not snapshot:
            raise HTTPException(
                409,
                "Retrieve the observed option chain before adding an open-interest alert",
            )
    else:
        market.meta(req.symbol)
    if (
        req.kind in ("price", "rsi", "portfolio_loss", "open_interest")
        and req.target <= 0
    ):
        raise HTTPException(422, "This condition requires a positive threshold")
    if req.kind == "rsi" and req.target > 100:
        raise HTTPException(422, "RSI thresholds are between 0 and 100")
    if req.scope != "paper":
        v = trading.replay_view(db, u.id, owned_replay(db, u, req.scope))
        if req.symbol != v["symbol"]:
            raise HTTPException(422, "Alert symbol must match replay")
        price = v["current_price"]
    else:
        q = (
            None
            if req.kind == "open_interest"
            else market.live_quote(req.symbol, u.id, db=db)
        )
        price = q["price"] if q else None
    key = trading.ident()
    r = trading.put(
        db,
        u.id,
        "alert",
        key,
        {
            **req.model_dump(mode="json"),
            "active": True,
            "last_price": price if req.kind == "price" else None,
            "last_fired": None,
            "created_at": now(),
        },
    )
    return {"id": key, **r.data}


@app.delete("/v1/alerts/{aid}")
def delete_alert(aid: str, u=Depends(current), db=Depends(database, scope="function")):
    r = trading.get(db, u.id, "alert", aid)
    if not r:
        raise HTTPException(404, "Alert not found")
    r.data = {**r.data, "active": False}
    return {"success": True}


@app.get("/v1/alerts/events")
def events(u=Depends(current), db=Depends(database, scope="function")):
    return sorted(
        [r.data for r in trading.records(db, u.id, "event")],
        key=lambda x: x["observed_at"],
        reverse=True,
    )


@app.get("/v1/learn/lessons")
def lessons(u=Depends(current), db=Depends(database, scope="function")):
    return [
        {
            **{k: v for k, v in x.items() if k != "correct"},
            "progress": (
                trading.get(db, u.id, "progress", x["id"]).data
                if trading.get(db, u.id, "progress", x["id"])
                else None
            ),
        }
        for x in LESSONS
    ]


@app.post("/v1/learn/quiz")
def quiz(req: Quiz, u=Depends(current), db=Depends(database, scope="function")):
    lesson = next((x for x in LESSONS if x["id"] == req.lesson_id), None)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    correct = req.answer == lesson["correct"]
    old = trading.get(db, u.id, "progress", lesson["id"])
    passed = correct or bool(old and old.data.get("passed"))
    trading.put(
        db, u.id, "progress", lesson["id"], {"passed": passed, "updated_at": now()}
    )
    return {"correct": correct, "explanation": lesson["explanation"], "passed": passed}


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    import asyncio

    if ws.headers.get("origin") not in ORIGINS:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            await ws.send_json(
                {
                    "type": "SNAPSHOT",
                    "data": [
                        market.live_quote(m["symbol"], optional_owner(ws))
                        or market.latest(m["symbol"])
                        for m in market.catalog()
                    ],
                    "sent_at": now(),
                }
            )
            await asyncio.sleep(15)
    except (WebSocketDisconnect, RuntimeError):
        pass


DIST = ROOT / "frontend/dist"
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/", include_in_schema=False)
@app.get("/explore", include_in_schema=False)
@app.get("/tradebook", include_in_schema=False)
@app.get("/connections", include_in_schema=False)
@app.get("/channels", include_in_schema=False)
@app.get("/operations", include_in_schema=False)
@app.get("/glossary", include_in_schema=False)
@app.get("/options", include_in_schema=False)
@app.get("/fundamentals", include_in_schema=False)
@app.get("/account", include_in_schema=False)
@app.get("/overview", include_in_schema=False)
@app.get("/research", include_in_schema=False)
@app.get("/models", include_in_schema=False)
@app.get("/journal", include_in_schema=False)
@app.get("/alerts", include_in_schema=False)
@app.get("/markets", include_in_schema=False)
@app.get("/portfolio", include_in_schema=False)
@app.get("/replay", include_in_schema=False)
@app.get("/learn", include_in_schema=False)
def frontend():
    if not (DIST / "index.html").exists():
        raise HTTPException(
            503, "Build the frontend first: npm --prefix frontend run build"
        )
    return FileResponse(DIST / "index.html")


# The platform routes share the existing session and transaction dependencies.
from app.curriculum import lessons as segment_lessons

LESSONS.extend(segment_lessons())
from app.features import install as install_features

install_features(app)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://[a-p]{32}",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Eye-Client"],
)
from app.accounts import install as install_accounts

install_accounts(app)
from app.workbench import install as install_workbench
install_workbench(app)

from app.segment_analysis import install as install_segment_analysis
install_segment_analysis(app)

from app.live import install as install_live
install_live(app)

from app.kite_workspace import install as install_kite_workspace
install_kite_workspace(app)

from app.investing import install as install_investing
install_investing(app)
