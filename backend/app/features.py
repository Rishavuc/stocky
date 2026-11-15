"""Connected product features: imported ledger, providers, channels, markets, and learning."""

import csv, io, json, secrets, hashlib, os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException, Request, Response
from app import trading, market, ledger, connections, notifications
from app.store import now


class ImportRequest(BaseModel):
    csv: str = Field(max_length=2_000_000)
    broker: str = Field(default="csv", pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    mapping: dict[str, str] | None = None


class Credentials(BaseModel):
    credentials: dict[str, str]


class ChannelRequest(Credentials):
    provider: str
    quiet_start: int | None = Field(default=None, ge=0, le=23)
    quiet_end: int | None = Field(default=None, ge=0, le=23)


class Verify(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class Compare(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=4)


class FinancialFacts(BaseModel):
    source_url: str = Field(pattern=r"^https://", max_length=1000)
    statement_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    eps: Decimal
    book_value_per_share: Decimal = Field(gt=0)
    debt: Decimal = Field(ge=0)
    equity: Decimal = Field(gt=0)


def install(app):
    from app.main import current, database, csv_response, LESSONS

    dep = Depends(database, scope="function")

    @app.post("/v1/imports/preview")
    def preview(req: ImportRequest, u=Depends(current), db=dep):
        p = ledger.parse_csv(req.csv, req.mapping)
        existing = {r.key for r in trading.records(db, u.id, "imported_trade")}
        p["duplicates"] = sum(
            hashlib.sha256((req.broker + ":" + r["external_id"]).encode()).hexdigest()
            in existing
            for r in p["rows"]
        )
        return p

    @app.post("/v1/imports/commit")
    def commit(req: ImportRequest, u=Depends(current), db=dep):
        p = ledger.parse_csv(req.csv, req.mapping)
        if not p["valid"]:
            raise HTTPException(
                422,
                {"message": "Fix CSV errors before importing", "errors": p["errors"]},
            )
        return ledger.import_rows(db, u.id, req.broker, p["rows"])

    @app.get("/v1/imports")
    def batches(u=Depends(current), db=dep):
        return [r.data for r in trading.records(db, u.id, "import_batch")]

    @app.get("/v1/trades")
    def trades(
        broker: str | None = None,
        segment: str | None = None,
        start: str | None = None,
        end: str | None = None,
        u=Depends(current),
        db=dep,
    ):
        rows = [r.data for r in trading.records(db, u.id, "imported_trade")]
        catalog = {m["symbol"]: m for m in market.catalog()}
        return sorted(
            [
                r
                for r in rows
                if (not broker or r["broker"] == broker)
                and (not start or r["executed_at"][:10] >= start)
                and (not end or r["executed_at"][:10] <= end)
                and (
                    not segment
                    or catalog.get(r["symbol"], {}).get("segment", "equities")
                    == segment
                )
            ],
            key=lambda x: x["executed_at"],
            reverse=True,
        )

    @app.get("/v1/portfolio/unified")
    def unified(broker: str | None = None, u=Depends(current), db=dep):
        rows = [
            r.data
            for r in trading.records(db, u.id, "imported_trade")
            if not broker or r.data["broker"] == broker
        ]
        snapshots = {
            r.key: r.data["rows"]
            for r in trading.records(db, u.id, "broker_holdings")
            if not broker or r.key == broker
        }
        # Reconcile each broker separately, never compare an aggregate quantity against one broker.
        result = ledger.summarize(rows)
        result["reconciliation"] = []
        for name, holdings in snapshots.items():
            result["reconciliation"] += ledger.summarize(
                [r for r in rows if r["broker"] == name], {name: holdings}
            )["reconciliation"]
        return result

    @app.get("/v1/trades/export.csv")
    def export(u=Depends(current), db=dep):
        rows = [r.data for r in trading.records(db, u.id, "imported_trade")]
        cols = ["broker", *ledger.COLUMNS]
        return csv_response(
            [cols]
            + [
                [
                    ""
                    if k == "fees"
                    and not r.get("fees_known", float(r.get("fees", 0)) > 0)
                    else r.get(k, "")
                    for k in cols
                ]
                for r in rows
            ],
            "imported-trades.csv",
        )

    @app.post("/v1/extensions/pair")
    def pair(u=Depends(current), db=dep):
        from app.store import Session

        token = secrets.token_urlsafe(48)
        db.add(
            Session(
                digest=hashlib.sha256(token.encode()).hexdigest(),
                owner=u.id,
                expires=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            )
        )
        return {"token": token, "expires_in_days": 7}

    @app.get("/v1/connections")
    def providers(u=Depends(current), db=dep):
        return [
            connections.public(r.data) for r in trading.records(db, u.id, "connection")
        ]

    @app.put("/v1/connections/{provider}")
    def connect(provider: str, req: Credentials, u=Depends(current), db=dep):
        return connections.save(db, u.id, provider, req.credentials)

    @app.post("/v1/connections/{provider}/authorize")
    def authorize(provider: str, u=Depends(current), db=dep):
        return connections.authorize(db, u.id, provider)

    @app.get("/v1/connections/{provider}/callback")
    def callback(
        provider: str,
        state: str,
        code: str | None = None,
        request_token: str | None = None,
        db=dep,
    ):
        from fastapi.responses import RedirectResponse

        if not code and not request_token:
            raise HTTPException(422, "Authorization code missing")
        connections.callback(db, provider, state, code or request_token)
        return RedirectResponse("/connections", status_code=303)

    @app.delete("/v1/connections/{provider}")
    def disconnect(provider: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "connection", provider)
        if r:
            db.delete(r)
        from app.store import Observation
        from sqlalchemy import delete

        db.execute(delete(Observation).where(Observation.owner == u.id))
        if provider == "kite":
            for kind in ("kite_portfolio","kite_candles","oauth_state"):
                for cached in trading.records(db,u.id,kind):db.delete(cached)
            for cached in trading.records(db,u.id,"live_feed"):
                if cached.key.startswith("kite_"):db.delete(cached)
        return {"disconnected": True}

    @app.post("/v1/connections/{provider}/sync")
    def sync(provider: str, u=Depends(current), db=dep):
        return connections.sync(db, u.id, provider)

    @app.get("/v1/channels")
    def channels(u=Depends(current), db=dep):
        return [
            {k: v for k, v in r.data.items() if k not in ("secret", "challenge_hash")}
            for r in trading.records(db, u.id, "channel")
        ]

    @app.post("/v1/channels")
    def add_channel(req: ChannelRequest, u=Depends(current), db=dep):
        if req.provider not in ("telegram", "email", "whatsapp"):
            raise HTTPException(422, "Unsupported channel")
        key = trading.ident()
        trading.put(
            db,
            u.id,
            "channel",
            key,
            {
                "id": key,
                "provider": req.provider,
                "secret": connections.seal(req.credentials),
                "verified": False,
                "enabled": True,
                "quiet_start": req.quiet_start,
                "quiet_end": req.quiet_end,
                "timezone": "Asia/Kolkata",
                "created_at": now(),
            },
        )
        return {"id": key, "verified": False, "provider": req.provider}

    @app.post("/v1/channels/{cid}/challenge")
    def challenge(cid: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "channel", cid)
        if not r:
            raise HTTPException(404, "Channel not found")
        code = secrets.token_hex(3).upper()
        try:
            result = notifications.send(
                r.data["provider"],
                connections.unseal(r.data["secret"]),
                "InvestorsEYE verification code: " + code,
            )
        except Exception:
            raise HTTPException(
                502,
                "Verification could not be sent. Check channel credentials and provider access.",
            )
        r.data = {
            **r.data,
            "challenge_hash": hashlib.sha256(code.encode()).hexdigest(),
            "challenge_expires": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
        }
        return {
            "status": result["status"],
            "message": "Enter the code received at your channel. Provider acceptance does not confirm receipt.",
        }

    @app.post("/v1/channels/{cid}/verify")
    def verify(cid: str, req: Verify, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "channel", cid)
        if not r:
            raise HTTPException(404, "Channel not found")
        if r.data.get("challenge_expires", "") < now() or not secrets.compare_digest(
            r.data.get("challenge_hash", ""),
            hashlib.sha256(req.code.strip().upper().encode()).hexdigest(),
        ):
            raise HTTPException(422, "Code invalid or expired")
        r.data = {**r.data, "verified": True, "challenge_hash": None}
        return {"verified": True}

    @app.delete("/v1/channels/{cid}")
    def disable(cid: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "channel", cid)
        if not r:
            raise HTTPException(404, "Channel not found")
        r.data = {**r.data, "enabled": False}
        return {"enabled": False}

    @app.post("/v1/channels/{cid}/test")
    def test(cid: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "channel", cid)
        if not r or not r.data.get("verified"):
            raise HTTPException(409, "Verify the recipient first")
        e = {
            "id": trading.ident(),
            "message": "InvestorsEYE test notification",
            "observed_at": now(),
        }
        notifications.enqueue(db, u.id, e, channel_id=cid)
        return {"status": "queued"}

    @app.get("/v1/webhooks/whatsapp")
    def whatsapp_verify(request: Request):
        token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        if not token or not secrets.compare_digest(
            request.query_params.get("hub.verify_token", ""), token
        ):
            raise HTTPException(403, "Webhook verification failed")
        return Response(
            request.query_params.get("hub.challenge", ""), media_type="text/plain"
        )

    @app.post("/v1/webhooks/whatsapp")
    async def whatsapp_receipt(request: Request, db=dep):
        import hmac

        secret = os.getenv("WHATSAPP_APP_SECRET")
        if not secret:
            raise HTTPException(503, "WhatsApp receipt validation is not configured")
        body = await request.body()
        expected = (
            "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not secrets.compare_digest(
            expected, request.headers.get("x-hub-signature-256", "")
        ):
            raise HTTPException(403, "Invalid receipt signature")
        from app.store import Record
        from sqlalchemy import select

        payload = json.loads(body)
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for status in change.get("value", {}).get("statuses", []):
                    for r in db.scalars(
                        select(Record).where(Record.kind == "delivery")
                    ):
                        if r.data.get("provider_id") == status.get("id") and status.get(
                            "status"
                        ) in ("delivered", "read"):
                            r.data = {
                                **r.data,
                                "status": "confirmed",
                                "receipt": status["status"],
                                "confirmed_at": now(),
                            }
        return {"accepted": True}

    @app.get("/v1/deliveries")
    def deliveries(u=Depends(current), db=dep):
        return [r.data for r in trading.records(db, u.id, "delivery")]

    @app.post("/v1/deliveries/{did}/retry")
    def retry(did: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "delivery", did)
        if not r:
            raise HTTPException(404, "Delivery not found")
        if r.data["status"] not in ("failed", "uncertain"):
            raise HTTPException(409, "This delivery cannot be retried")
        r.data = {**r.data, "status": "retry", "next_attempt": now()}
        return {"status": "retry"}

    @app.get("/v1/markets/segments")
    def segments():
        from collections import Counter

        counts = Counter(m.get("segment", "equities") for m in market.catalog())
        return [
            {"id": k, "count": counts.get(k, 0)}
            for k in (
                "equities",
                "indices",
                "intraday",
                "derivatives",
                "funds",
                "crypto",
            )
        ]

    @app.post("/v1/analysis/compare")
    def compare(req: Compare):
        result = []
        for sym in req.symbols:
            m = market.meta(sym)
            rows = market.history(sym)
            first = rows[-min(252, len(rows))]["close"]
            last = rows[-1]["close"]
            result.append(
                {
                    "symbol": sym,
                    "name": m["name"],
                    "currency": m["currency"],
                    "as_of": rows[-1]["date"],
                    "return_pct": round((last / first - 1) * 100, 2),
                    "observations": min(252, len(rows)),
                    "source": m["source"],
                }
            )
        return result

    @app.get("/v1/markets/sectors")
    def sectors():
        buckets = {}
        for m in market.catalog():
            if m.get("segment", "equities") != "equities":
                continue
            q = market.latest(m["symbol"])
            buckets.setdefault(m.get("sector", "Unclassified"), []).append(
                {"change": q["change_pct"], "observed_at": q.get("observed_at"), "source": m["source"]}
            )
        return [
            {
                "sector": k,
                "mean_change_pct": round(sum(x["change"] for x in v) / len(v), 2),
                "members": len(v),
                "observed_at": sorted(set(x["observed_at"] for x in v if x["observed_at"])),
                "sources": sorted(set(x["source"] for x in v)),
                "method": "Equal-weight observed sample, not an official sector index",
            }
            for k, v in buckets.items()
        ]

    @app.get("/v1/analysis/funds/{symbol}")
    def fund_analysis(symbol: str):
        m = market.meta(symbol)
        if m.get("segment") != "funds":
            raise HTTPException(422, "Choose a fund instrument")
        rows = market.history(symbol)
        result = {
            "symbol": symbol,
            "name": m["name"],
            "nav": rows[-1]["close"],
            "as_of": rows[-1]["date"],
            "source": m["source"],
            "returns": {},
        }
        for n in (21, 252, 756):
            if len(rows) > n:
                result["returns"][str(n) + " observations"] = round(
                    (rows[-1]["close"] / rows[-n - 1]["close"] - 1) * 100, 2
                )
        from app.workbench import risk_summary
        result['risk']=risk_summary(rows)
        # Compare only matching observed NAV/index dates, without filling missing publications.
        import pandas as pd
        fund=pd.Series({r['date']:r['close'] for r in rows})
        benchmark=pd.Series({r['date']:r['close'] for r in market.history('NIFTY50')})
        aligned=pd.concat([fund.rename('fund'),benchmark.rename('benchmark')],axis=1).dropna().pct_change().dropna()
        if len(aligned)>=60 and aligned.benchmark.var()>0:
            beta=float(aligned['fund'].cov(aligned.benchmark)/aligned.benchmark.var())
            result['benchmark']={'symbol':'NIFTY50','beta':beta,'annualized_alpha_zero_rf_pct':float((aligned['fund'].mean()-beta*aligned.benchmark.mean())*252*100),'matched_observations':len(aligned),'assumptions':'Date-matched simple returns, 252-observation annualization, zero risk-free rate; not a category-adjusted rating.'}
        result["note"] = (
            "NAV observations are not intraday quotes. Missing dates are not filled with fabricated NAVs."
        )
        return result

    @app.post("/v1/analysis/funds/{symbol}/sip")
    def sip(symbol: str, body: dict):
        m = market.meta(symbol)
        if m.get("segment") != "funds":
            raise HTTPException(422, "Choose a fund")
        try:
            amount = Decimal(str(body.get("monthly_amount", 0)))
        except Exception:
            raise HTTPException(422, "Invalid monthly amount")
        if not amount.is_finite() or amount <= 0:
            raise HTTPException(422, "Monthly amount must be positive")
        start = str(body.get("start_date", ""))
        end = str(body.get("end_date", "9999-12-31"))
        rows = [r for r in market.history(symbol) if start <= r["date"] <= end]
        if not rows:
            raise HTTPException(422, "No observed NAVs in that date range")
        seen = set()
        payments = []
        units = Decimal(0)
        for r in rows:
            month = r["date"][:7]
            if month in seen:
                continue
            seen.add(month)
            units += amount / Decimal(str(r["close"]))
            payments.append(
                {"date": r["date"], "amount": str(amount), "nav": r["close"]}
            )
        invested = amount * len(payments)
        value = units * Decimal(str(rows[-1]["close"]))
        return {
            "payments": payments,
            "invested": str(invested),
            "units": str(units),
            "value": str(value.quantize(Decimal(".01"))),
            "gain": str((value - invested).quantize(Decimal(".01"))),
            "as_of": rows[-1]["date"],
            "source": m["source"],
            "assumptions": "Invest on the first observed NAV each month; fractional units; no exit load, tax or timing guarantee. This is historical simulation, not a return promise.",
        }

    @app.get("/v1/analysis/options")
    def options(
        underlying: str = "NIFTY", expiry: str | None = None, u=Depends(current), db=dep
    ):
        return connections.options(db, u.id, underlying, expiry)

    @app.post("/v1/analysis/fundamentals/{symbol}")
    def save_fundamentals(symbol: str, req: FinancialFacts, u=Depends(current), db=dep):
        market.meta(symbol)
        trading.put(db, u.id, "financial_facts", symbol, req.model_dump(mode="json"))
        return {
            "saved": True,
            "verification": "User-supplied; not independently verified",
        }

    @app.get("/v1/analysis/fundamentals/{symbol}")
    def fundamentals(symbol: str, u=Depends(current), db=dep):
        market.meta(symbol)
        r = trading.get(db, u.id, "financial_facts", symbol)
        if not r:
            return {
                "symbol": symbol,
                "status": "unavailable",
                "reason": "Import attributed financial-statement values; no company ratios are invented.",
            }
        d = r.data
        price = market.latest(symbol)["price"]
        return {
            "symbol": symbol,
            "status": "user_supplied",
            "facts": d,
            "ratios": {
                "price_to_earnings": price / float(d["eps"])
                if float(d["eps"]) > 0
                else None,
                "price_to_book": price / float(d["book_value_per_share"]),
                "debt_to_equity": float(d["debt"]) / float(d["equity"]),
            },
            "price_as_of": market.latest(symbol)["observed_at"],
            "verification": "Calculated from user-supplied statement values; not independently verified.",
        }

    @app.get("/v1/learn/glossary")
    def glossary():
        from app.curriculum import GLOSSARY

        return GLOSSARY

    @app.get("/v1/learn/resources")
    def resources():
        from app.curriculum import RESOURCES

        return RESOURCES

    @app.get("/v1/learn/bookmarks")
    def bookmarks(u=Depends(current), db=dep):
        return [r.key for r in trading.records(db, u.id, "bookmark")]

    @app.post("/v1/learn/bookmarks/{lid}")
    def bookmark(lid: str, u=Depends(current), db=dep):
        if lid not in {x["id"] for x in LESSONS}:
            raise HTTPException(404, "Lesson not found")
        trading.put(db, u.id, "bookmark", lid, {"created_at": now()})
        return {"saved": True}

    @app.delete("/v1/learn/bookmarks/{lid}")
    def unbookmark(lid: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, "bookmark", lid)
        if r:
            db.delete(r)
        return {"saved": False}

    @app.get("/v1/models/runs")
    def model_runs():
        from app.store import DB

        with DB() as db:
            return [r.data for r in trading.records(db, "system", "model_run")]

    @app.get("/v1/models/runs/{version}")
    def run_report(version: str):
        import re

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,180}", version):
            raise HTTPException(422, "Invalid run identifier")
        path = market.ROOT / "models/runs" / version / "report.json"
        if not path.exists():
            raise HTTPException(404, "Saved run not found")
        return json.loads(path.read_text())

    @app.get("/v1/models/outcomes")
    def model_outcomes():
        from app.store import DB

        with DB() as db:
            return [r.data for r in trading.records(db, "system", "prediction")]

    @app.get("/v1/operations")
    def operations(u=Depends(current), db=dep):
        return {
            "jobs": [r.data for r in trading.records(db, "system", "job")],
            "worker": (
                trading.get(db, "system", "worker", "status").data
                if trading.get(db, "system", "worker", "status")
                else {"status": "not_observed"}
            ),
            "datasets": [
                {
                    "symbol": m["symbol"],
                    "version": m["sha256"],
                    "as_of": m["end"],
                    "source": m["source"],
                }
                for m in market.catalog()
            ],
        }
