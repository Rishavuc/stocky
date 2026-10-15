from fastapi import APIRouter
from typing import List, Dict, Any
from app.services.market_ingest import market_ingest
from app.schemas.schemas import IndexOverview

router = APIRouter(prefix="/v1/markets", tags=["Markets"])

@router.get("/indices", response_model=List[IndexOverview])
def get_market_indices():
    return market_ingest.get_indices()

@router.get("/trending")
def get_trending_stocks():
    all_quotes = market_ingest.get_all_quotes()
    gainers = sorted(all_quotes, key=lambda x: x.change_pct, reverse=True)[:5]
    losers = sorted(all_quotes, key=lambda x: x.change_pct)[:5]
    active = sorted(all_quotes, key=lambda x: x.volume, reverse=True)[:5]

    return {
        "gainers": gainers,
        "losers": losers,
        "most_active": active
    }

@router.get("/sectors")
def get_sector_performance():
    return market_ingest.get_sector_performance()

@router.get("/breadth")
def get_market_breadth():
    return market_ingest.get_market_breadth()

@router.get("/fii-dii")
def get_fii_dii():
    return market_ingest.get_fii_dii_flows()

@router.get("/stocks")
def get_stocks_catalog():
    return market_ingest.get_stocks_catalog()

@router.get("/crypto")
def get_crypto_catalog():
    return market_ingest.get_crypto_catalog()

@router.get("/currencies")
def get_currencies_catalog():
    return market_ingest.get_currencies_catalog()
