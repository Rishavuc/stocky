from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.services.market_ingest import market_ingest
from app.schemas.schemas import QuoteResponse, CandleResponse

router = APIRouter(prefix="/v1", tags=["Instruments & Quotes"])

@router.get("/instruments/search")
def search_instruments(q: str = Query(..., min_length=1)):
    return market_ingest.search_instruments(q)

@router.get("/quotes", response_model=List[QuoteResponse])
def get_quotes():
    return market_ingest.get_all_quotes()

@router.get("/quotes/{symbol}", response_model=QuoteResponse)
def get_single_quote(symbol: str):
    q = market_ingest.get_quote(symbol)
    if not q:
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found")
    return q

@router.get("/candles/{symbol}", response_model=List[CandleResponse])
def get_candles(symbol: str, timeframe: str = "1d", limit: int = 30):
    return market_ingest.get_candles(symbol, timeframe, limit)
