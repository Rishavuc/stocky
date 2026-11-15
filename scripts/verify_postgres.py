"""Dedicated-process restart and concurrent spending acceptance on PostgreSQL."""

import os, sys, subprocess, time, secrets, concurrent.futures
from pathlib import Path
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))
from app.store import DB, User, Session, Record, URL
from app import market, trading
from sqlalchemy import delete

assert URL.startswith("postgresql"), "This acceptance test requires PostgreSQL"
BASE = "http://127.0.0.1:8001"
HEAD = {"X-Eye-Client": "workspace"}
process = None
owner = None
log = open(ROOT / "runtime/acceptance-server.log", "w")


def start():
    global process
    process = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "backend/run.py")],
        cwd=ROOT,
        env={**os.environ, "APP_PORT": "8001", "ALLOWED_ORIGINS": BASE},
        stdout=log,
        stderr=log,
    )
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(
                "Acceptance server exited; see runtime/acceptance-server.log"
            )
        try:
            if httpx.get(BASE + "/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Server did not become ready")


def stop():
    global process
    if process:
        process.terminate()
        process.wait(timeout=15)
        process = None


try:
    start()
    with httpx.Client(base_url=BASE, headers=HEAD, timeout=30) as c:
        email = "concurrency-" + secrets.token_hex(6) + "@example.com"
        password = secrets.token_urlsafe(24)
        res = c.post(
            "/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Concurrency verification",
            },
        )
        assert res.status_code == 200, res.text
        owner = res.json()["id"]
        r = c.post(
            "/v1/replays",
            json={
                "symbol": "RELIANCE",
                "start_date": market.history("RELIANCE")[-120]["date"],
            },
        ).json()
        rid = r["id"]
        cookies = dict(c.cookies)

        def submit(request_id):
            return httpx.post(
                BASE + f"/v1/replays/{rid}/orders",
                headers=HEAD,
                cookies=cookies,
                timeout=30,
                json={
                    "request_id": request_id,
                    "symbol": "RELIANCE",
                    "side": "BUY",
                    "qty": 100,
                    "order_type": "LIMIT",
                    "price": "10000.00",
                    "reason": "Reserve the whole account",
                },
            )

        # All identical concurrent requests must resolve to one order.
        key = trading.ident()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(submit, [key] * 8))
        assert all(x.status_code == 200 for x in results), [
            (x.status_code, x.text[:100]) for x in results
        ]
        assert len({x.json()["id"] for x in results}) == 1
        p = c.get(f"/v1/replays/{rid}").json()["portfolio"]
        assert p["reserved_cash"] == 1000000
        assert c.delete("/v1/paper/orders/" + key).status_code == 200
        # Distinct competing requests cannot reserve the same million twice.
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(submit, [trading.ident() for _ in range(8)]))
        assert sum(x.status_code == 200 for x in results) == 1, [
            (x.status_code, x.text[:100]) for x in results
        ]
        assert sum(x.status_code == 409 for x in results) == 7
        assert (
            c.get(f"/v1/replays/{rid}").json()["portfolio"]["reserved_cash"] == 1000000
        )
        c.post("/v1/watchlist/RELIANCE")
        stop()
        start()  # A new OS process, not just a new request/session.
        assert c.get("/v1/auth/me").json()["id"] == owner
        assert c.get("/v1/watchlist").json() == ["RELIANCE"]
        assert (
            c.get(f"/v1/replays/{rid}").json()["portfolio"]["reserved_cash"] == 1000000
        )
    print(
        "PASS: PostgreSQL concurrent idempotency, double-spend prevention, and full web-process restart persistence."
    )
finally:
    stop()
    log.close()
    if owner:
        with DB.begin() as db:
            db.execute(delete(Record).where(Record.owner == owner))
            db.execute(delete(Session).where(Session.owner == owner))
            db.execute(delete(User).where(User.id == owner))
