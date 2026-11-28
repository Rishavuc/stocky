from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.services.market_ingest import (
    market_ingest, normalize_symbol, ALLOWED_TIMEFRAMES, MAX_CANDLE_LIMIT,
)
from app.schemas.schemas import QuoteResponse, CandleResponse

router = APIRouter(prefix="/v1", tags=["Instruments & Quotes"])


def _valid_symbol_or_422(symbol: str) -> str:
    sym = normalize_symbol(symbol)
    if not sym:
        raise HTTPException(status_code=422, detail="Invalid symbol")
    return sym


@router.get("/instruments/search")
def search_instruments(q: str = Query(..., min_length=1, max_length=32)):
    return market_ingest.search_instruments(q)

@router.get("/quotes", response_model=List[QuoteResponse])
def get_quotes():
    return market_ingest.get_all_quotes()

@router.get("/quotes/{symbol}", response_model=QuoteResponse)
def get_single_quote(symbol: str):
    sym = _valid_symbol_or_422(symbol)
    q = market_ingest.get_quote(sym, prefer_intraday=True)
    if not q:
        raise HTTPException(status_code=404, detail=f"Instrument {sym} not found")
    return q

@router.get("/candles/{symbol}", response_model=List[CandleResponse])
def get_candles(symbol: str, timeframe: str = "1d", limit: int = 30):
    sym = _valid_symbol_or_422(symbol)
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise HTTPException(
            status_code=422,
            detail=f"timeframe must be one of {sorted(ALLOWED_TIMEFRAMES)}",
        )
    # Clamp rather than reject so older clients asking for "all" still work.
    limit = max(1, min(limit, MAX_CANDLE_LIMIT))
    return market_ingest.get_candles(sym, timeframe, limit)
