import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from typing import Optional
from app.services.market_ingest import market_ingest
from app.config import settings, is_configured
from app.security import current_user_id

# Kite request/access tokens are short alphanumeric strings. Anything else
# (newlines especially) must never reach the .env writer in market_ingest.
_KITE_TOKEN_RE = re.compile(r"[A-Za-z0-9]{8,128}")
DEMO_USER_ID = "usr_demo_1001"

router = APIRouter(prefix="/v1/integrations", tags=["Broker & Exchange Integrations"])

# Binance's signed account call costs API weight and blocks; anyone can hit
# /status, so the answer is cached instead of fetched per request.
_BINANCE_TTL_SECONDS = 300
_binance_cache: dict = {"at": 0.0, "value": None}


async def _binance_status_cached() -> dict:
    now = time.monotonic()
    if _binance_cache["value"] is None or now - _binance_cache["at"] > _BINANCE_TTL_SECONDS:
        _binance_cache["value"] = dict(await run_in_threadpool(market_ingest.get_binance_account_status))
        _binance_cache["at"] = now
    return dict(_binance_cache["value"])


def require_admin(user_id: str = Depends(current_user_id)) -> str:
    """Server-wide broker settings: only ids listed in ADMIN_USER_IDS."""
    if user_id == DEMO_USER_ID or user_id not in settings.admin_user_ids:
        raise HTTPException(status_code=403, detail="Only the site administrator can change broker connections.")
    return user_id


class TokenPayload(BaseModel):
    request_token: Optional[str] = None
    access_token: Optional[str] = None

@router.get("/status")
async def get_integrations_status():
    binance_account = await _binance_status_cached()
    kite_login_url = market_ingest.get_kite_login_url()
    kite_configured = is_configured(settings.KITE_API_KEY or settings.ZERODHA_API_KEY)
    kite_token_active = is_configured(settings.KITE_ACCESS_TOKEN)

    return {
        "binance": {
            "status": "connected" if binance_account.get("authenticated") else "ready",
            "api_key_configured": is_configured(settings.BINANCE_API_KEY),
            "account_verified": binance_account.get("authenticated", False),
            "can_trade": binance_account.get("canTrade", False),
            "account_type": binance_account.get("accountType", "SPOT"),
            "supported_pairs": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]
        },
        "zerodha_kite": {
            "status": "authorized" if kite_token_active else ("credentials_configured" if kite_configured else "not_configured"),
            "api_key_configured": kite_configured,
            "access_token_active": kite_token_active,
            "login_url": kite_login_url,
            "broker": "Zerodha Kite Connect"
        }
    }

@router.get("/kite/login-url")
async def get_kite_login_url():
    return {
        "login_url": market_ingest.get_kite_login_url(),
        "api_key_configured": is_configured(settings.KITE_API_KEY or settings.ZERODHA_API_KEY)
    }

@router.post("/kite/token")
async def set_kite_token(payload: TokenPayload, user_id: str = Depends(require_admin)):
    # This swaps the server-wide Kite session for every visitor, so only an
    # admin may do it (sign-up is open, so "signed in" is no barrier).
    token = payload.access_token or payload.request_token
    if not token:
        raise HTTPException(status_code=400, detail="Must provide either request_token or access_token")
    if not _KITE_TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail="Invalid Kite token format.")

    if payload.access_token:
        await run_in_threadpool(market_ingest.set_kite_access_token, payload.access_token)
        return {"success": True, "message": "Kite access token activated successfully"}

    result = await run_in_threadpool(market_ingest.generate_kite_session, payload.request_token)
    if not result.get("success"):
        print(f"[Kite token] session exchange failed: {str(result.get('error'))[:200]}")
        raise HTTPException(status_code=400, detail="Failed to generate Kite session. The request token may have expired.")
    # Never return the session payload: it holds the access_token and the
    # broker account profile.
    data = result.get("data") or {}
    return {
        "success": True,
        "message": "Kite session activated successfully",
        "data": {"user_id": data.get("user_id"), "user_name": data.get("user_name")},
    }

@router.get("/binance/account")
async def get_binance_account(user_id: str = Depends(require_admin)):
    status = await _binance_status_cached()
    if "error" in status:
        # Raw exception text can include upstream URLs or request details.
        print(f"[Binance account] {str(status.pop('error'))[:200]}")
        status["message"] = "Binance account could not be verified."
    return status
