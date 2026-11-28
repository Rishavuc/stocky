"""Security regression checks for the backend hardening pass.

Run from backend/ (no pytest needed, uses a throwaway SQLite DB):
    ../.venv/bin/python tests/security_checks.py
Exits non-zero if any check fails. Network calls to Yahoo may be attempted
for one quote check; it passes with or without network.
"""
import os, sys, tempfile, threading, time
d = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{d}/r2.db"
os.environ["TRUST_PROXY_HEADERS"] = "true"
os.environ["ADMIN_USER_IDS"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
import app.main as m
from app.config import settings
from app.services.trade_sync import TradeSyncService
from app.services.ml_service import ml_service

ok = True
def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)

with TestClient(m.app) as c:
    # 1. Demo cannot be locked out by strangers.
    for i in range(12):
        c.post("/v1/auth/login", json={"username_or_email": "demo", "password": "wrong"},
               headers={"X-Forwarded-For": f"10.0.{i}.1"})
    r = c.post("/v1/auth/login", json={"username_or_email": "demo", "password": "demo"},
               headers={"X-Forwarded-For": "10.9.9.9"})
    check("demo login after 12 bad tries", r.status_code == 200, r.status_code)
    demo_tok = r.json().get("access_token")

    # 2. Spoofed left XFF entries share the real (rightmost) bucket.
    c.post("/v1/auth/register", json={"name": "Vic", "email": "vic@example.com", "password": "rightpass123"})
    codes = []
    for i in range(22):
        r = c.post("/v1/auth/login", json={"username_or_email": f"nobody{i}@x.com", "password": "x"},
                   headers={"X-Forwarded-For": f"1.2.3.{i}, 203.0.113.7"})
        codes.append(r.status_code)
    check("spoofed XFF still rate limited", 429 in codes, codes[-3:])

    # 3. Victim not locked out by attacker on another IP.
    for i in range(12):
        c.post("/v1/auth/login", json={"username_or_email": "vic@example.com", "password": "bad"},
               headers={"X-Forwarded-For": "198.51.100.1"})
    r = c.post("/v1/auth/login", json={"username_or_email": "vic@example.com", "password": "rightpass123"},
               headers={"X-Forwarded-For": "192.0.2.50"})
    check("owner logs in from own IP during attack", r.status_code == 200, r.status_code)
    vic_tok = r.json().get("access_token")
    H = {"Authorization": f"Bearer {vic_tok}"}
    D = {"Authorization": f"Bearer {demo_tok}"}

    # 4. Kite token / binance account need admin.
    r = c.post("/v1/integrations/kite/token", json={"access_token": "AAAAAAAAAAAAAAAA"}, headers=H)
    check("non-admin kite token 403", r.status_code == 403, r.status_code)
    r = c.get("/v1/integrations/binance/account", headers=H)
    check("non-admin binance account 403", r.status_code == 403, r.status_code)
    r = c.get("/v1/integrations/status")
    check("status still public 200", r.status_code == 200, r.status_code)

    # 5. Kite callback disabled when setting off.
    settings.KITE_CALLBACK_ENABLED = False
    r = c.get("/v1/integrations/kite/callback?request_token=abcdefgh12345678")
    check("kite callback disabled", r.status_code == 200 and "disabled" in r.text)

    # 6. Demo cannot write broker book; labels validated.
    r = c.post("/v1/brokers/connect", json={"broker_name": "Zerodha", "client_id": "AB1234"}, headers=D)
    check("demo broker connect 403", r.status_code == 403, r.status_code)
    r = c.post("/v1/brokers/connect", json={"broker_name": "<img src=x onerror=alert(1)>", "client_id": "AB1"}, headers=H)
    check("html broker name 422", r.status_code == 422, r.status_code)
    r = c.post("/v1/brokers/connect", json={"broker_name": "Upstox", "client_id": "AB1"}, headers=H)
    check("normal broker connect ok", r.status_code == 200, r.status_code)

    # 7. ^ index symbol passes validation (provider may still have no data).
    r = c.get("/v1/quotes/%5ENSEI")
    check("^NSEI not rejected as invalid symbol", r.status_code != 422, r.status_code)

# 7b. Huge pagination offset is clamped, not a 500.
with TestClient(m.app, raise_server_exceptions=False) as c:
    tok = c.post("/v1/auth/login", json={"username_or_email": "demo", "password": "demo"},
                 headers={"X-Forwarded-For": "192.0.2.90"}).json()["access_token"]
    r = c.get("/v1/auth/activity?offset=9223372036854775808", headers={"Authorization": f"Bearer {tok}"})
    check("huge activity offset no 500", r.status_code == 200, r.status_code)

# 8. Google sign-in disables a password someone else pre-registered.
import app.routes.auth as auth
auth.google_id_token.verify_oauth2_token = lambda cred, req, aud: {
    "iss": "accounts.google.com", "email": "prey@example.com", "email_verified": True, "name": "Prey"}
auth.google_enabled = lambda: True
with TestClient(m.app) as c:
    c.post("/v1/auth/register", json={"name": "Squatter", "email": "prey@example.com", "password": "squatpass123"},
           headers={"X-Forwarded-For": "192.0.2.77"})
    r = c.post("/v1/auth/google", json={"credential": "x" * 50}, headers={"X-Forwarded-For": "192.0.2.78"})
    check("owner google sign-in ok", r.status_code == 200, r.status_code)
    r = c.post("/v1/auth/login", json={"username_or_email": "prey@example.com", "password": "squatpass123"},
               headers={"X-Forwarded-For": "192.0.2.77"})
    check("squatter password disabled after google", r.status_code == 401, r.status_code)

# 9. CSV overflow rows are skipped, not a 500.
check("csv inf qty skipped", TradeSyncService._parse_row({"Symbol": "TCS", "Qty": "1e999", "Price": "10"}) is None)
check("csv html symbol skipped", TradeSyncService._parse_row({"Symbol": "<B>", "Qty": "1", "Price": "10"}) is None)
check("csv good row ok", TradeSyncService._parse_row({"Symbol": "TCS", "Qty": "2", "Price": "10"}) is not None)

# 10. Busy training lock -> fallback (None) within ~1s instead of queueing.
ml_service._train_lock.acquire()
t0 = time.time()
res = ml_service._get_or_train("ZZZ", "lstm", __import__("numpy").linspace(1, 2, 300))
dt = time.time() - t0
ml_service._train_lock.release()
check("busy train lock returns fallback fast", res is None and dt < 2.0, f"{dt:.2f}s")

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
