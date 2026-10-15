from fastapi import APIRouter
from typing import Optional
from app.services.analysis_engine import analysis_engine
from app.schemas.schemas import TechnicalAnalysisResponse, OptionChainResponse

router = APIRouter(prefix="/v1/analysis", tags=["Analysis"])

@router.get("/technical/{symbol}", response_model=TechnicalAnalysisResponse)
def get_technical_analysis(symbol: str):
    return analysis_engine.get_technical_analysis(symbol)

@router.get("/option-chain", response_model=OptionChainResponse)
def get_option_chain(underlying: str = "NIFTY"):
    return analysis_engine.get_option_chain(underlying)

@router.get("/funds/{code}")
def get_fund_analysis(code: str = "PPFCF"):
    return analysis_engine.get_fund_analysis(code)

@router.get("/crypto/{symbol}")
def get_crypto_analysis(symbol: str = "BTCINR"):
    return analysis_engine.get_crypto_analysis(symbol)
