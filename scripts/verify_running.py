"""Real HTTP acceptance path. Creates and cleans only its own temporary accounts."""

import os, sys, secrets, time
from pathlib import Path
from datetime import datetime
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))
from app import market, trading
from app.store import DB, User, Session, Record
from sqlalchemy import delete

BASE = os.getenv("EYE_TEST_URL", "http://127.0.0.1:8000")
HEADER = {"X-Eye-Client": "workspace"}
users = []


def check(res, status=200):
    assert res.status_code == status, (
        f"{res.request.method} {res.request.url.path}: {res.status_code} {res.text[:200]}"
    )
    return (
        res.json() if "application/json" in res.headers.get("content-type", "") else res
    )


try:
    with httpx.Client(base_url=BASE, headers=HEADER, timeout=30) as c:
        assert check(c.get("/health"))["status"] == "healthy"
        page = check(c.get("/"))
        assert "InvestorsEYE" in page.text
        import re

        for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text):
            check(c.get(asset))
        email = "verify-" + secrets.token_hex(6) + "@example.com"
        password = secrets.token_urlsafe(24)
        u = check(
            c.post(
                "/v1/auth/register",
                json={
                    "name": "Verification user",
                    "email": email,
                    "password": password,
                },
            )
        )
        users.append(u["id"])
        assert c.cookies.get("eye_session")
        assert check(c.get("/v1/auth/me"))["id"] == u["id"]
        check(c.post("/v1/watchlist/RELIANCE"))
        assert check(c.get("/v1/watchlist")) == ["RELIANCE"]
        rows = market.history("RELIANCE")
        start = rows[-150]["date"]
        idx = len(rows) - 150
        r = check(
            c.post("/v1/replays", json={"symbol": "RELIANCE", "start_date": start})
        )
        rid = r["id"]
        body = {
            "request_id": trading.ident(),
            "symbol": "RELIANCE",
            "side": "BUY",
            "qty": 10,
            "order_type": "MARKET",
            "reason": "Acceptance test: compare observed trend with later outcome",
        }
        order = check(c.post(f"/v1/replays/{rid}/orders", json=body))
        assert order["status"] == "PENDING"
        assert (
            check(c.post(f"/v1/replays/{rid}/orders", json=body))["id"] == order["id"]
        )
        target = round((rows[idx]["close"] + rows[idx + 1]["close"]) / 2, 2)
        direction = "above" if rows[idx + 1]["close"] > rows[idx]["close"] else "below"
        check(
            c.post(
                "/v1/alerts",
                json={
                    "symbol": "RELIANCE",
                    "scope": rid,
                    "direction": direction,
                    "target": str(target),
                },
            )
        )
        advanced = check(c.post(f"/v1/replays/{rid}/advance", json={"steps": 1}))
        assert advanced["portfolio"]["positions"][0]["qty"] == 10
        saved = check(c.get("/v1/paper/orders", params={"scope": rid}))
        assert saved[0]["fill_price"] == float(trading.money(rows[idx + 1]["open"]))
        assert len(check(c.get("/v1/alerts/events"))) == 1
        assert check(c.post("/v1/learn/quiz", json={"lesson_id": "risk", "answer": 1}))[
            "passed"
        ]
        assert check(c.get("/v1/journal"))[0]["order"]["status"] == "FILLED"
        check(
            c.post("/v1/paper/orders", json={**body, "request_id": trading.ident()}),
            409,
        )
        f = check(c.get("/v1/predictions/RELIANCE"))
        assert f["as_of"] == rows[-1]["date"]
        assert (
            f["split"]["train_end"]
            < f["split"]["validation_start"]
            < f["split"]["test_start"]
        )
        with c.stream("GET", "/openapi.json") as spec:
            assert spec.status_code == 200
        for private in [
            "/.env",
            "/.git/config",
            "/backend/app/main.py",
            "/investors_eye_v2.db",
            "/models/RELIANCE_1.pt",
        ]:
            check(c.get(private), 404)
        check(
            c.post(
                "/v1/watchlist/TCS", headers={"Origin": "https://unapproved.example"}
            ),
            403,
        )
        check(c.post("/v1/auth/logout"))
        check(c.get("/v1/auth/me"), 401)
        check(c.post("/v1/auth/login", json={"email": email, "password": password}))
        assert (
            check(c.get(f"/v1/replays/{rid}"))["portfolio"]["positions"][0]["qty"] == 10
        )
        with httpx.Client(base_url=BASE, headers=HEADER, timeout=30) as other:
            bob = check(
                other.post(
                    "/v1/auth/register",
                    json={
                        "name": "Other verification user",
                        "email": "other-" + email,
                        "password": password,
                    },
                )
            )
            users.append(bob["id"])
            check(other.get(f"/v1/replays/{rid}"), 404)
            assert check(other.get("/v1/journal")) == []
        # A real WebSocket handshake and first snapshot, with the allowed origin.
        from websockets.sync.client import connect
        import json

        with connect(
            BASE.replace("http://", "ws://").replace("https://", "wss://")
            + "/ws/stream",
            origin=BASE,
            open_timeout=10,
        ) as ws:
            snapshot = json.loads(ws.recv(timeout=10))
            assert snapshot["type"] == "SNAPSHOT"
            assert len(snapshot["data"]) == len(market.catalog())
        print(
            "PASS: HTTP assets, fresh accounts, saved watchlist, replay next-bar fill, idempotency, alerts, quiz, journal, login persistence, account isolation, private file protection, origin protection, model provenance, and WebSocket snapshot."
        )
finally:
    with DB.begin() as db:
        for owner in users:
            db.execute(delete(Record).where(Record.owner == owner))
            db.execute(delete(Session).where(Session.owner == owner))
            db.execute(delete(User).where(User.id == owner))
