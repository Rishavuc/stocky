import json, csv, io, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from app import market, trading, store, notifications, connections, accounts, datasets
from app.store import Record
from fastapi.testclient import TestClient
from app.main import app

HEADER = {"X-Eye-Client": "workspace"}
CSV = "external_id,symbol,side,qty,price,fees,executed_at,currency\na,RELIANCE,BUY,10,100,10,2026-01-01T10:00:00+05:30,INR\nb,RELIANCE,SELL,4,120,4,2026-01-02T10:00:00+05:30,INR\n"


def test_csv_preview_fifo_duplicates_and_wallet_isolation(alice):
    before = alice.get("/v1/paper/portfolio").json()["cash"]
    p = alice.post("/v1/imports/preview", json={"csv": CSV, "broker": "sample"})
    assert p.status_code == 200, p.text
    assert p.json()["valid"]
    imported = alice.post("/v1/imports/commit", json={"csv": CSV, "broker": "sample"})
    assert imported.status_code == 200
    assert imported.json()["inserted"] == 2
    assert (
        alice.post("/v1/imports/commit", json={"csv": CSV, "broker": "sample"}).json()[
            "duplicates"
        ]
        == 2
    )
    result = alice.get("/v1/portfolio/unified").json()
    assert result["holdings"][0]["qty"] == "6"
    assert result["realized_by_currency"]["INR"] == "72.00"
    assert alice.get("/v1/paper/portfolio").json()["cash"] == before
    assert "RELIANCE" in alice.get("/v1/trades/export.csv").text
    with TestClient(app, headers=HEADER) as other:
        other.post(
            "/v1/auth/register",
            json={
                "name": "Other",
                "email": "ledger-other@example.com",
                "password": "long-password-123",
            },
        )
        assert other.get("/v1/trades").json() == []


def test_invalid_csv_rolls_back_and_conflicting_ids_fail(alice):
    invalid = CSV + "bad,INFY,BUY,-1,20,0,2026-01-01T10:00:00Z,INR\n"
    assert not alice.post("/v1/imports/preview", json={"csv": invalid}).json()["valid"]
    assert alice.post("/v1/imports/commit", json={"csv": invalid}).status_code == 422
    assert not alice.get("/v1/trades").json()
    assert alice.post("/v1/imports/commit", json={"csv": CSV}).status_code == 200
    assert (
        alice.post(
            "/v1/imports/commit", json={"csv": CSV.replace("10,100", "10,101")}
        ).status_code
        == 409
    )
    assert len(alice.get("/v1/trades").json()) == 2


def test_connection_secrets_encrypted_and_isolated(alice):
    response = alice.put(
        "/v1/connections/kite",
        json={
            "credentials": {
                "api_key": "example-key",
                "access_token": "never-return-this",
            }
        },
    )
    assert response.status_code == 200
    assert "never-return-this" not in response.text
    assert "never-return-this" not in alice.get("/v1/connections").text
    with store.DB() as db:
        record = db.query(Record).filter_by(kind="connection").one()
        assert "never-return-this" not in record.data["secret"]
        assert connections.unseal(record.data["secret"])["api_key"] == "example-key"


def test_channel_verification_and_durable_outbox(alice, monkeypatch):
    captured = []
    monkeypatch.setattr(
        notifications,
        "send",
        lambda provider, credentials, text: (
            captured.append(text) or {"status": "sent", "provider_id": "test-only"}
        ),
    )
    c = alice.post(
        "/v1/channels",
        json={
            "provider": "telegram",
            "credentials": {"bot_token": "not-real", "chat_id": "test"},
        },
    ).json()
    cid = c["id"]
    assert alice.post("/v1/channels/" + cid + "/test").status_code == 409
    assert alice.post("/v1/channels/" + cid + "/challenge").status_code == 200
    code = captured[-1].split(": ")[-1]
    assert alice.post("/v1/channels/" + cid + "/verify", json={"code": code}).json()[
        "verified"
    ]
    assert alice.post("/v1/channels/" + cid + "/test").status_code == 200
    assert notifications.deliver_one()
    rows = alice.get("/v1/deliveries").json()
    assert len(rows) == 1 and rows[0]["status"] == "sent"
    assert not notifications.deliver_one()
    assert len(captured) == 2


def test_uncertain_delivery_is_not_automatically_duplicated(alice, monkeypatch):
    import httpx

    with store.DB.begin() as db:
        owner = db.query(store.User).filter_by(email="alice@example.com").one().id
        trading.put(
            db,
            owner,
            "channel",
            "one",
            {
                "id": "one",
                "provider": "telegram",
                "secret": connections.seal({"bot_token": "x", "chat_id": "x"}),
                "verified": True,
                "enabled": True,
            },
        )
        notifications.enqueue(db, owner, {"id": "event", "message": "Test only"})

    def timeout(*args):
        raise httpx.ReadTimeout("Lost provider reply")

    monkeypatch.setattr(notifications, "send", timeout)
    assert notifications.deliver_one()
    assert alice.get("/v1/deliveries").json()[0]["status"] == "uncertain"
    assert not notifications.deliver_one()


def test_dataset_refresh_pins_replay_and_preserves_failed_symbols(
    alice, monkeypatch, tmp_path
):
    original = market.DATA
    manifest = json.loads((original / "manifest.json").read_text())
    chosen = next(x for x in manifest if x["symbol"] == "RELIANCE")
    other = next(x for x in manifest if x["symbol"] == "TCS")
    for m in (chosen, other):
        (tmp_path / (m["symbol"] + ".csv")).write_bytes(datasets.read(m["symbol"]))
    (tmp_path / "manifest.json").write_text(json.dumps([chosen, other]))
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(market, "DATA", tmp_path)
    datasets.ensure_versions()
    rows = market.history("RELIANCE")
    r = alice.post(
        "/v1/replays", json={"symbol": "RELIANCE", "start_date": rows[100]["date"]}
    ).json()
    rid = r["id"]
    before = alice.get("/v1/replays/" + rid).json()
    raw = (tmp_path / "RELIANCE.csv").read_text().splitlines()
    changed = ("\n".join([raw[0], *raw[2:]]) + "\n").encode()
    datasets.publish([(chosen, changed)])
    after = alice.get("/v1/replays/" + rid).json()
    assert (
        after["date"] == before["date"]
        and after["current_price"] == before["current_price"]
    )
    assert "TCS" in [x["symbol"] for x in market.catalog()]
    assert datasets.read("RELIANCE", before["dataset_version"]) != datasets.read(
        "RELIANCE"
    )


def test_recovery_tokens_single_use_and_sessions_revoked(alice, monkeypatch):
    captured = []
    monkeypatch.setattr(accounts, "mail", lambda recipient, text: captured.append(text))
    assert alice.post("/v1/auth/request-verification").status_code == 200
    token = captured[-1].split(": ")[-1]
    assert alice.post("/v1/auth/verify-email", json={"token": token}).json()["verified"]
    assert (
        alice.post(
            "/v1/auth/request-recovery", json={"email": "alice@example.com"}
        ).status_code
        == 200
    )
    reset = captured[-1].split(": ")[-1]
    assert alice.post(
        "/v1/auth/reset-password",
        json={"token": reset, "password": "replacement-password"},
    ).json()["reset"]
    assert alice.get("/v1/auth/me").status_code == 401
    assert (
        alice.post(
            "/v1/auth/reset-password",
            json={"token": reset, "password": "another-password"},
        ).status_code
        == 422
    )
    assert (
        alice.post(
            "/v1/auth/login",
            json={"email": "alice@example.com", "password": "replacement-password"},
        ).status_code
        == 200
    )


def test_curriculum_bookmarks_and_extension_token(alice):
    lessons = alice.get("/v1/learn/lessons").json()
    assert {x.get("segment") for x in lessons if x.get("segment")} == {
        "equities",
        "funds",
        "derivatives",
        "intraday",
        "crypto",
    }
    assert len(alice.get("/v1/learn/glossary").json()) >= 8
    assert alice.post("/v1/learn/bookmarks/equities-0").json()["saved"]
    assert "equities-0" in alice.get("/v1/learn/bookmarks").json()
    paired = alice.post("/v1/extensions/pair").json()["token"]
    with TestClient(
        app,
        headers={
            **HEADER,
            "Authorization": "Bearer " + paired,
            "Origin": "chrome-extension://" + "a" * 32,
        },
    ) as extension:
        assert extension.get("/v1/auth/me").status_code == 200
        assert extension.post("/v1/watchlist/RELIANCE").status_code == 200
    assert alice.get("/v1/watchlist").json() == ["RELIANCE"]


def test_financial_facts_never_invented(alice):
    assert (
        alice.get("/v1/analysis/fundamentals/RELIANCE").json()["status"]
        == "unavailable"
    )
    r = alice.post(
        "/v1/analysis/fundamentals/RELIANCE",
        json={
            "source_url": "https://example.com/statement",
            "statement_date": "2026-03-31",
            "eps": "100",
            "book_value_per_share": "500",
            "debt": "1000",
            "equity": "2000",
        },
    )
    assert r.status_code == 200, r.text
    f = alice.get("/v1/analysis/fundamentals/RELIANCE").json()
    assert f["status"] == "user_supplied"
    assert f["ratios"]["debt_to_equity"] == 0.5


def test_replay_costs_are_reserved_and_charged(alice):
    rows = market.history("RELIANCE")
    r = alice.post(
        "/v1/replays",
        json={"symbol": "RELIANCE", "start_date": rows[-120]["date"], "fee_bps": 10},
    ).json()
    rid = r["id"]
    request = {
        "request_id": trading.ident(),
        "symbol": "RELIANCE",
        "side": "BUY",
        "qty": 10,
        "order_type": "MARKET",
    }
    assert alice.post("/v1/replays/" + rid + "/orders", json=request).status_code == 200
    result = alice.post("/v1/replays/" + rid + "/advance", json={"steps": 1}).json()
    p = result["portfolio"]
    price = next(x for x in rows if x["date"] == result["date"])["open"]
    notional = trading.money(price) * 10
    fee = trading.money(notional / 1000)
    assert p["cash"] == float(1000000 - notional - fee)
    assert p["reserved_cash"] == 0


def test_user_quote_observations_are_not_shared(alice):
    from app.store import Observation

    with store.DB.begin() as db:
        owner = db.query(store.User).filter_by(email="alice@example.com").one().id
    market.persist_quotes(
        owner,
        {
            "RELIANCE": {
                "symbol": "RELIANCE",
                "price": 123.45,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "source": "Test broker",
                "status": "live",
                "tradable": True,
            }
        },
    )
    assert alice.get("/v1/quotes/RELIANCE").json()["price"] == 123.45
    with TestClient(app, headers=HEADER) as anonymous:
        assert anonymous.get("/v1/quotes/RELIANCE").json()["status"] == "historical"


def test_extension_unpair_revokes_server_token(alice):
    token = alice.post("/v1/extensions/pair").json()["token"]
    with TestClient(
        app, headers={**HEADER, "Authorization": "Bearer " + token}
    ) as extension:
        assert extension.get("/v1/auth/me").status_code == 200
        assert extension.post("/v1/auth/logout").status_code == 200
        assert extension.get("/v1/auth/me").status_code == 401
    assert alice.get("/v1/auth/me").status_code == 200


def test_forged_delivery_receipt_is_rejected(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-secret")
    assert (
        client.post(
            "/v1/webhooks/whatsapp",
            json={"entry": []},
            headers={"X-Hub-Signature-256": "sha256=forged"},
        ).status_code
        == 403
    )


def test_sip_uses_actual_monthly_nav_observations(alice):
    funds = [m for m in market.catalog() if m.get("segment") == "funds"]
    assert funds
    r = alice.post(
        "/v1/analysis/funds/" + funds[0]["symbol"] + "/sip",
        json={"monthly_amount": "1000", "start_date": "2025-01-01"},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert len({x["date"][:7] for x in result["payments"]}) == len(result["payments"])
    assert float(result["invested"]) == len(result["payments"]) * 1000


def test_saved_inference_does_not_refit_preprocessing(alice, monkeypatch, tmp_path):
    import shutil
    from app import research
    from sklearn.preprocessing import StandardScaler

    source = market.ROOT / "models/RELIANCE_1_report.json"
    report = json.loads(source.read_text())
    version = report["version"]
    (tmp_path / "models").mkdir()
    shutil.copytree(
        market.ROOT / "models/runs" / version, tmp_path / "models/runs" / version
    )
    report["as_of"] = "1900-01-01"
    (tmp_path / "models/RELIANCE_1_report.json").write_text(json.dumps(report))
    monkeypatch.setattr(research, "ROOT", tmp_path)

    def no_fit(*args, **kwargs):
        raise AssertionError("Inference refitted training preprocessing")

    monkeypatch.setattr(StandardScaler, "fit", no_fit)
    result = research.infer("RELIANCE", 1)
    assert result["as_of"] == market.history("RELIANCE")[-1]["date"]
    assert result["version"] == version
    assert result["trained_data_sha256"]
    assert result["inference_at"]


def test_market_context_never_uses_an_unclosed_index_bar(monkeypatch):
    import numpy as np
    import pandas as pd
    from app import research

    reference = [
        {"date": "2025-12-31", "close": 100},
        {"date": "2026-01-01", "close": 110},
        {"date": "2026-01-02", "close": 220},
    ]
    original_meta = market.meta
    monkeypatch.setattr(
        market,
        "meta",
        lambda symbol: (
            {"sha256": "0" * 64} if symbol == "NIFTY50" else {"segment": "intraday"}
        ),
    )
    monkeypatch.setattr(market, "history", lambda symbol: reference)
    asset = pd.DataFrame(
        {
            "date": ["2026-01-02T05:00:00+00:00", "2026-01-02T11:00:00+00:00"],
            "close": [100, 101],
            "volume": [20, 30],
        }
    )
    features, context = research.feature_matrix(asset, "RELIANCE_5m")
    assert np.isclose(features[0, 3], np.log(110 / 100))
    assert np.isclose(features[1, 3], np.log(220 / 110))
    assert context["dataset_version"] == "0" * 64


def test_missing_broker_fees_can_be_enriched_without_duplicate_trades(alice):
    unknown = CSV.replace("10,100,10,", "10,100,,").replace("4,120,4,", "4,120,,")
    assert (
        alice.post(
            "/v1/imports/commit", json={"csv": unknown, "broker": "upstox"}
        ).status_code
        == 200
    )
    assert alice.get("/v1/portfolio/unified").json()["fee_status"] == "incomplete"
    updated = alice.post(
        "/v1/imports/commit", json={"csv": CSV, "broker": "upstox"}
    ).json()
    assert updated["fees_updated"] == 2 and updated["inserted"] == 0
    assert len(alice.get("/v1/trades").json()) == 2
    assert (
        alice.get("/v1/portfolio/unified").json()["realized_by_currency"]["INR"]
        == "72.00"
    )
    # A later fee-less broker resync does not erase verified CSV fees.
    assert (
        alice.post(
            "/v1/imports/commit", json={"csv": unknown, "broker": "upstox"}
        ).json()["duplicates"]
        == 2
    )
    assert alice.get("/v1/portfolio/unified").json()["fee_status"] == "complete"


def test_broker_timestamp_formats_are_normalized():
    naive = connections.provider_timestamp("2026-01-01 10:00:00")
    assert naive == "2026-01-01T04:30:00+00:00"
    assert connections.provider_timestamp("1767241800000") == naive
