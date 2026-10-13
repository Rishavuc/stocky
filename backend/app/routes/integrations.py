from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.market_ingest import market_ingest
from app.config import settings

router = APIRouter(prefix="/v1/integrations", tags=["Broker & Exchange Integrations"])

class TokenPayload(BaseModel):
    request_token: Optional[str] = None
    access_token: Optional[str] = None

@router.get("/status")
async def get_integrations_status():
    binance_account = market_ingest.get_binance_account_status()
    kite_login_url = market_ingest.get_kite_login_url()

    return {
        "binance": {
            "status": "connected" if binance_account.get("authenticated") else "ready",
            "api_key_configured": bool(settings.BINANCE_API_KEY),
            "account_verified": binance_account.get("authenticated", False),
            "can_trade": binance_account.get("canTrade", False),
            "account_type": binance_account.get("accountType", "SPOT"),
            "supported_pairs": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]
        },
        "zerodha_kite": {
            "status": "authorized" if settings.KITE_ACCESS_TOKEN else "credentials_configured",
            "api_key_configured": bool(settings.KITE_API_KEY or settings.ZERODHA_API_KEY),
            "access_token_active": bool(settings.KITE_ACCESS_TOKEN),
            "login_url": kite_login_url,
            "broker": "Zerodha Kite Connect"
        }
    }

@router.get("/kite/login-url")
async def get_kite_login_url():
    return {
        "login_url": market_ingest.get_kite_login_url(),
        "api_key": settings.KITE_API_KEY
    }

@router.post("/kite/token")
async def set_kite_token(payload: TokenPayload):
    if payload.access_token:
        market_ingest.set_kite_access_token(payload.access_token)
        return {"success": True, "message": "Kite access token activated successfully"}
    elif payload.request_token:
        result = market_ingest.generate_kite_session(payload.request_token)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to generate session"))
        return {"success": True, "data": result.get("data")}
    else:
        raise HTTPException(status_code=400, detail="Must provide either request_token or access_token")

@router.get("/binance/account")
async def get_binance_account():
    return market_ingest.get_binance_account_status()
