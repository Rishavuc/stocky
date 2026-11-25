from fastapi import APIRouter, HTTPException
from app.services.analysis_engine import analysis_engine
from app.services.market_ingest import market_ingest


router = APIRouter(prefix="/v1/analysis", tags=["Analysis"])


def _verified_or_422(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/technical/{symbol}")
def get_technical_analysis(symbol: str):
    return _verified_or_422(analysis_engine.get_technical_analysis, symbol)


@router.get("/option-chain")
def get_option_chain(underlying: str = "NIFTY"):
    return _verified_or_422(analysis_engine.get_option_chain, underlying)


@router.get("/funds/growth")
def get_growth_funds():
    return market_ingest.get_growth_mutual_funds()

@router.get("/funds/{code}")
def get_fund_analysis(code: str = "PPFCF"):
    return _verified_or_422(analysis_engine.get_fund_analysis, code)


@router.get("/crypto/{symbol}")
def get_crypto_analysis(symbol: str = "BTCINR"):
    return _verified_or_422(analysis_engine.get_crypto_analysis, symbol)
