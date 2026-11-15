from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, hash_password
from app import market, trading, store

HEADER = {"X-Eye-Client": "workspace"}


def payload(**kwargs):
    return {
        "request_id": trading.ident(),
        "symbol": "RELIANCE",
        "side": "BUY",
        "qty": 2,
        "order_type": "MARKET",
        "reason": "Compare the observed price trend",
        **kwargs,
    }


def replay(client):
    rows = market.history("RELIANCE")
    r = client.post(
        "/v1/replays", json={"symbol": "RELIANCE", "start_date": rows[-120]["date"]}
    )
    assert r.status_code == 200, r.text
    return r.json()


def quote(monkeypatch, price=100):
    monkeypatch.setattr(
        market,
        "live_quote",
        lambda symbol, *args, **kwargs: {
            "price": price,
            "source": "Test provider",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "status": "live",
        },
    )


def test_complete_replay_and_saved_progress(alice):
    c = alice
    assert c.post("/v1/watchlist/RELIANCE").status_code == 200
    r = replay(c)
    rid = r["id"]
    rows = market.history("RELIANCE")
    idx = next(i for i, x in enumerate(rows) if x["date"] == r["date"])
    req = payload()
    o = c.post(f"/v1/replays/{rid}/orders", json=req)
    assert o.status_code == 200, o.text
    assert o.json()["status"] == "PENDING"
    # Idempotency returns the original order, without adding another debit.
    assert c.post(f"/v1/replays/{rid}/orders", json=req).json()["id"] == o.json()["id"]
    advanced = c.post(f"/v1/replays/{rid}/advance", json={"steps": 1})
    assert advanced.status_code == 200, advanced.text
    v = advanced.json()
    assert len(v["portfolio"]["positions"]) == 1
    assert v["portfolio"]["positions"][0]["qty"] == 2
    orders = c.get("/v1/paper/orders", params={"scope": rid}).json()
    assert orders[0]["fill_price"] == float(trading.money(rows[idx + 1]["open"]))
    assert orders[0]["filled_at"] == rows[idx + 1]["date"]
    assert all(x["date"] <= v["date"] for x in v["candles"])
    assert c.get(f"/v1/replays/{rid}/analysis").json()["as_of"] == v["date"]
    assert c.get("/v1/paper/portfolio").json()["positions"] == []
    assert c.get("/v1/journal").json()[0]["reason"] == req["reason"]
    quiz = c.post("/v1/learn/quiz", json={"lesson_id": "risk", "answer": 1}).json()
    assert quiz["passed"]
    # Separate client and database session demonstrate persisted login/data.
    with TestClient(app, headers=HEADER) as reopened:
        assert (
            reopened.post(
                "/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-horse-123"},
            ).status_code
            == 200
        )
        assert reopened.get("/v1/watchlist").json() == ["RELIANCE"]
        assert (
            reopened.get(f"/v1/replays/{rid}").json()["portfolio"]["positions"][0][
                "qty"
            ]
            == 2
        )
        assert reopened.get("/v1/learn/lessons").json()[0]["progress"]["passed"]


def test_private_accounts_and_csrf(alice):
    rid = replay(alice)["id"]
    alice.post("/v1/watchlist/RELIANCE")
    with TestClient(app, headers=HEADER) as bob:
        assert (
            bob.post(
                "/v1/auth/register",
                json={
                    "name": "Bob",
                    "email": "bob@example.com",
                    "password": "another-password",
                },
            ).status_code
            == 200
        )
        assert bob.get("/v1/watchlist").json() == []
        assert bob.get(f"/v1/replays/{rid}").status_code == 404
        assert (
            bob.post(f"/v1/replays/{rid}/advance", json={"steps": 1}).status_code == 404
        )
    assert (
        alice.post(
            "/v1/watchlist/TCS", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    with TestClient(app) as anonymous:
        assert anonymous.get("/v1/paper/portfolio").status_code == 401
        assert anonymous.post("/v1/auth/login", json={}).status_code == 403
        anonymous.cookies.set("eye_session", "ie_sec_usr_demo_1001_123")
        assert anonymous.get("/v1/auth/me").status_code == 401
    assert alice.post("/v1/auth/logout").status_code == 200
    assert alice.get("/v1/auth/me").status_code == 401


def test_private_files_never_served(client):
    for path in [
        "/.env",
        "/investors_eye_v2.db",
        "/.git/config",
        "/backend/app/main.py",
        "/README.md",
        "/models/RELIANCE_1.pt",
        "/index.html",
        "/mock-trading.html",
    ]:
        assert client.get(path).status_code == 404, path
    assert client.get("/health").status_code == 200


def test_invalid_orders_and_freshness(alice, monkeypatch):
    monkeypatch.setattr(market, "live_quote", lambda symbol, *args, **kwargs: None)
    assert alice.post("/v1/paper/orders", json=payload()).status_code == 409
    for invalid in [
        payload(qty=-1),
        payload(qty=0),
        payload(qty=1.2),
        payload(side="HACK"),
        payload(order_type="SL"),
        payload(symbol="../../x"),
        payload(price="NaN"),
    ]:
        assert alice.post("/v1/paper/orders", json=invalid).status_code == 422, invalid
    quote(monkeypatch)
    assert alice.post("/v1/paper/orders", json=payload(qty=10001)).status_code == 409
    assert (
        alice.post("/v1/paper/orders", json=payload(symbol="UNKNOWN")).status_code
        == 404
    )
    assert alice.post("/v1/paper/orders", json=payload(side="SELL")).status_code == 409
    assert (
        alice.post("/v1/paper/orders", json=payload(order_type="LIMIT")).status_code
        == 422
    )


def test_decimal_accounting_duplicates_and_reservations(alice, monkeypatch):
    quote(monkeypatch, 100.01)
    req = payload(qty=3)
    r = alice.post("/v1/paper/orders", json=req)
    assert r.status_code == 200, r.text
    assert alice.get("/v1/paper/portfolio").json()["cash"] == 999699.97
    assert alice.post("/v1/paper/orders", json=req).json() == r.json()
    assert alice.post("/v1/paper/orders", json={**req, "qty": 4}).status_code == 409
    # Reserve all shares for a pending sell; a second sale is rejected.
    pending = alice.post(
        "/v1/paper/orders",
        json=payload(side="SELL", qty=3, order_type="LIMIT", price="110.00"),
    )
    assert pending.status_code == 200, pending.text
    assert (
        alice.post("/v1/paper/orders", json=payload(side="SELL", qty=1)).status_code
        == 409
    )
    assert alice.delete("/v1/paper/orders/" + pending.json()["id"]).status_code == 200
    quote(monkeypatch, 110.01)
    assert (
        alice.post("/v1/paper/orders", json=payload(side="SELL", qty=3)).status_code
        == 200
    )
    p = alice.get("/v1/paper/portfolio").json()
    assert p["cash"] == 1000030
    assert p["realized"] == 30
    assert not p["positions"]


def test_replay_limits_cancel_and_ownership(alice):
    r = replay(alice)
    rid = r["id"]
    pending = alice.post(
        f"/v1/replays/{rid}/orders", json=payload(order_type="LIMIT", price="0.01")
    ).json()
    assert (
        alice.post(f"/v1/replays/{rid}/advance", json={"steps": 3}).status_code == 200
    )
    assert (
        alice.get("/v1/paper/orders", params={"scope": rid}).json()[0]["status"]
        == "PENDING"
    )
    assert alice.delete("/v1/paper/orders/" + pending["id"]).status_code == 200
    assert alice.get(f"/v1/replays/{rid}").json()["portfolio"]["reserved_cash"] == 0
    assert alice.delete("/v1/paper/orders/" + pending["id"]).status_code == 409
    assert (
        alice.post(f"/v1/replays/{rid}/orders", json=payload(symbol="TCS")).status_code
        == 422
    )


def test_crossing_alert_event_and_progress(alice):
    r = replay(alice)
    rows = market.history(r["symbol"])
    idx = next(i for i, x in enumerate(rows) if x["date"] == r["date"])
    price = r["current_price"]
    nextprice = rows[idx + 1]["close"]
    direction = "above" if nextprice > price else "below"
    target = round((price + nextprice) / 2, 2)
    alert = alice.post(
        "/v1/alerts",
        json={
            "symbol": r["symbol"],
            "direction": direction,
            "target": str(target),
            "scope": r["id"],
        },
    )
    assert alert.status_code == 200, alert.text
    assert alice.get("/v1/alerts/events").json() == []
    alice.post(f"/v1/replays/{r['id']}/advance", json={"steps": 1})
    events = alice.get("/v1/alerts/events").json()
    assert len(events) == 1
    assert events[0]["price"] == nextprice
    assert alice.delete("/v1/alerts/" + alert.json()["id"]).status_code == 200
    assert (
        alice.post("/v1/learn/quiz", json={"lesson_id": "risk", "answer": 0}).json()[
            "correct"
        ]
        is False
    )
    assert alice.post("/v1/learn/quiz", json={"lesson_id": "risk", "answer": 1}).json()[
        "passed"
    ]
    assert alice.post("/v1/learn/quiz", json={"lesson_id": "risk", "answer": 0}).json()[
        "passed"
    ]


def test_model_provenance(client):
    r = client.get("/v1/predictions/RELIANCE?horizon=1")
    if r.status_code == 409:
        return  # Training artifacts are reproducibly generated, not required for lightweight CI.
    assert r.status_code == 200
    r = r.json()
    s = r["split"]
    assert (
        s["train_end"] < s["validation_start"] < s["validation_end"] < s["test_start"]
    )
    assert set(r["test"]) == {
        "Last-price baseline",
        "Moving-average baseline",
        "Gradient boosting",
        "LSTM",
    }
    assert r["selected_model"] == min(
        r["validation"], key=lambda k: r["validation"][k]["mae"]
    )
    assert not "confidence_score" in r


def test_alert_cooldown_and_every_advanced_bar(alice):
    from app.main import evaluate_alerts

    with store.DB.begin() as db:
        owner = db.query(store.User).filter_by(email="alice@example.com").one().id
        trading.put(
            db,
            owner,
            "alert",
            "cooldown",
            {
                "scope": "paper",
                "symbol": "RELIANCE",
                "direction": "above",
                "target": "100",
                "active": True,
                "last_price": 99,
                "last_fired": None,
            },
        )
        evaluate_alerts(
            db, owner, "paper", "RELIANCE", 101, "2026-01-01T10:00:00+00:00"
        )
        evaluate_alerts(db, owner, "paper", "RELIANCE", 99, "2026-01-01T10:01:00+00:00")
        evaluate_alerts(
            db, owner, "paper", "RELIANCE", 101, "2026-01-01T10:02:00+00:00"
        )
        assert len(trading.records(db, owner, "event")) == 1
        evaluate_alerts(db, owner, "paper", "RELIANCE", 99, "2026-01-01T10:06:00+00:00")
        evaluate_alerts(
            db, owner, "paper", "RELIANCE", 101, "2026-01-01T10:07:00+00:00"
        )
        assert len(trading.records(db, owner, "event")) == 2
    r = replay(alice)
    rows = market.history(r["symbol"])
    idx = next(i for i, x in enumerate(rows) if x["date"] == r["date"])
    p0 = rows[idx]["close"]
    p1 = rows[idx + 1]["close"]
    target = round((p0 + p1) / 2, 2)
    a = alice.post(
        "/v1/alerts",
        json={
            "symbol": r["symbol"],
            "scope": r["id"],
            "target": str(target),
            "direction": "above" if p1 > p0 else "below",
        },
    ).json()
    alice.post(f"/v1/replays/{r['id']}/advance", json={"steps": 5})
    assert any(
        x["alert_id"] == a["id"] and x["observed_at"] == rows[idx + 1]["date"]
        for x in alice.get("/v1/alerts/events").json()
    )


def test_quote_freshness_and_no_synthetic_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(market, "ROOT", tmp_path)
    market._quotes.clear()
    assert market.live_quote("RELIANCE") is None
    market._quotes["RELIANCE"] = {
        "price": 100,
        "observed_at": (
            datetime.now(timezone.utc) - timedelta(seconds=100)
        ).isoformat(),
    }
    assert market.live_quote("RELIANCE") is None
    market._quotes["RELIANCE"] = {
        "price": 100,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert market.live_quote("RELIANCE")["price"] == 100
    market._quotes.clear()


def test_replay_gap_rejection_releases_cash(alice):
    r = replay(alice)
    rid = r["id"]
    rows = market.history("RELIANCE")
    idx = next(i for i, x in enumerate(rows) if x["date"] == r["date"])
    # Pick a real gap-up session with a quantity that fits at the visible close but not at next open.
    for i in range(100, len(rows) - 2):
        qty = int(1000000 / rows[i]["close"])
        if float(trading.money(rows[i + 1]["open"])) * qty > 1000000:
            rr = alice.post(
                "/v1/replays",
                json={"symbol": "RELIANCE", "start_date": rows[i]["date"]},
            ).json()
            break
    else:
        raise AssertionError("Dataset has no usable gap-up example")
    o = alice.post(f"/v1/replays/{rr['id']}/orders", json=payload(qty=qty))
    assert o.status_code == 200, o.text
    v = alice.post(f"/v1/replays/{rr['id']}/advance", json={"steps": 1}).json()
    assert v["portfolio"]["reserved_cash"] == 0
    assert v["portfolio"]["cash"] == 1000000
    assert (
        alice.get("/v1/paper/orders", params={"scope": rr["id"]}).json()[0]["status"]
        == "REJECTED"
    )


def test_exports_are_generated_and_scoped(alice):
    r = replay(alice)
    response = alice.get(f"/v1/replays/{r['id']}/export.csv")
    assert response.status_code == 200
    assert "portfolio_value" in response.text
    assert "attachment" in response.headers["content-disposition"]
    with TestClient(app, headers=HEADER) as other:
        assert other.get(f"/v1/replays/{r['id']}/export.csv").status_code == 401
    prediction = alice.get("/v1/predictions/RELIANCE/export.csv")
    assert prediction.status_code == 200
    assert "last_price_baseline" in prediction.text


def test_worker_fills_pending_orders_and_keeps_users_separate(alice, monkeypatch):
    from app.worker import tick

    quote(monkeypatch, 100)
    pending = alice.post(
        "/v1/paper/orders", json=payload(order_type="LIMIT", price="90.00", qty=10)
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "PENDING"
    quote(monkeypatch, 89)
    monkeypatch.setattr(market, "refresh_quotes", lambda: {"status": "updated"})
    tick()
    orders = alice.get("/v1/paper/orders").json()
    assert orders[0]["status"] == "FILLED"
    assert orders[0]["fill_price"] == 89
    p = alice.get("/v1/paper/portfolio").json()
    assert p["cash"] == 999110
    assert p["reserved_cash"] == 0
    assert p["positions"][0]["qty"] == 10
    assert len(alice.get("/v1/paper/performance").json()) == 1
    tick()  # Filled orders are not processed twice.
    assert alice.get("/v1/paper/portfolio").json()["cash"] == 999110


def test_forecast_attachment_is_verified(alice, monkeypatch):
    quote(monkeypatch, 100)
    assert (
        alice.post(
            "/v1/paper/orders", json=payload(forecast_version="invented-model")
        ).status_code
        == 422
    )
    rid = replay(alice)["id"]
    assert (
        alice.post(
            f"/v1/replays/{rid}/orders", json=payload(forecast_version="invented-model")
        ).status_code
        == 422
    )
