"""Real HTTP acceptance for the newly connected platform, without provider secrets."""

import os, secrets, sys, json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.store import DB, Record, Session, User
from sqlalchemy import delete

base = "http://127.0.0.1:8000"
owner = None
try:
    with httpx.Client(
        base_url=base, headers={"X-Eye-Client": "workspace"}, timeout=30
    ) as c:
        r = c.post(
            "/v1/auth/register",
            json={
                "name": "Platform verification",
                "email": "platform-" + secrets.token_hex(6) + "@example.com",
                "password": secrets.token_urlsafe(20),
            },
        )
        assert r.status_code == 200, r.text
        owner = r.json()["id"]
        catalog = c.get("/v1/instruments/search").json()
        assert {"equities", "indices", "intraday", "crypto", "funds"} <= {
            m.get("segment", "equities") for m in catalog
        }
        for path in [
            "/explore",
            "/tradebook",
            "/connections",
            "/channels",
            "/operations",
            "/glossary",
            "/options",
            "/account",
            "/fundamentals",
        ]:
            assert c.get(path).status_code == 200, path
        text = "external_id,symbol,side,qty,price,fees,executed_at,currency\none,RELIANCE,BUY,10,100,1,2026-01-01T10:00:00Z,INR\ntwo,RELIANCE,SELL,5,120,1,2026-01-02T10:00:00Z,INR\n"
        assert c.post("/v1/imports/preview", json={"csv": text}).json()["valid"]
        assert c.post("/v1/imports/commit", json={"csv": text}).json()["inserted"] == 2
        assert (
            c.post("/v1/imports/commit", json={"csv": text}).json()["duplicates"] == 2
        )
        summary = c.get("/v1/portfolio/unified").json()
        assert summary["holdings"][0]["qty"] == "5"
        assert summary["realized_by_currency"]["INR"] == "98.50"
        assert c.get("/v1/paper/portfolio").json()["cash"] == 1000000
        assert len(c.get("/v1/learn/lessons").json()) == 13
        assert c.post("/v1/learn/bookmarks/funds-0").status_code == 200
        assert "funds-0" in c.get("/v1/learn/bookmarks").json()
        assert len(c.get("/v1/learn/glossary").json()) >= 8
        for symbol in ("RELIANCE", "BTCUSDT", "MF120716", "RELIANCE_5m"):
            response = c.get("/v1/predictions/" + symbol)
            assert response.status_code == 200, (symbol, response.text)
            report = response.json()
            assert len(report["folds"]) == 3
            assert report["training"]["seed"] == 42
        assert (
            c.get("/v1/analysis/options").status_code == 409
        )  # Explicitly requires an authenticated real provider.
        assert c.get("/v1/auth/account").json()["verified"] is False
        assert c.get("/v1/operations").status_code == 200
        assert c.get("/v1/models/runs").status_code == 200
        token = c.post("/v1/extensions/pair").json()["token"]
        with httpx.Client(
            base_url=base,
            headers={
                "X-Eye-Client": "workspace",
                "Authorization": "Bearer " + token,
                "Origin": "chrome-extension://" + "a" * 32,
            },
        ) as extension:
            assert extension.get("/v1/auth/me").json()["id"] == owner
            assert extension.post("/v1/watchlist/TCS").status_code == 200
        assert "TCS" in c.get("/v1/watchlist").json()
        print(
            "PASS: real HTTP multi-market data, connected pages, CSV/FIFO ledger, duplicate protection, portfolio isolation, 13 lessons, bookmarks, four segment forecast types, explicit provider blocking, operations and extension pairing."
        )
finally:
    if owner:
        with DB.begin() as db:
            db.execute(delete(Record).where(Record.owner == owner))
            db.execute(delete(Session).where(Session.owner == owner))
            db.execute(delete(User).where(User.id == owner))
