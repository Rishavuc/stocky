from fastapi import APIRouter
from typing import List, Dict, Any
from app.services.market_ingest import market_ingest
from app.schemas.schemas import IndexOverview

router = APIRouter(prefix="/v1/markets", tags=["Markets"])

@router.get("/indices", response_model=List[IndexOverview])
async def get_market_indices():
    return market_ingest.get_indices()

@router.get("/trending")
async def get_trending_stocks():
    all_quotes = market_ingest.get_all_quotes()
    # Sort gainers and losers
    gainers = sorted(all_quotes, key=lambda x: x.change_pct, reverse=True)[:5]
    losers = sorted(all_quotes, key=lambda x: x.change_pct)[:5]
    active = sorted(all_quotes, key=lambda x: x.volume, reverse=True)[:5]

    return {
        "gainers": gainers,
        "losers": losers,
        "most_active": active
    }

@router.get("/sectors")
async def get_sector_performance():
    return [
        {"sector": "NIFTY IT", "change_pct": 2.15, "positive": True},
        {"sector": "NIFTY Pharma", "change_pct": 1.56, "positive": True},
        {"sector": "NIFTY Auto", "change_pct": 1.12, "positive": True},
        {"sector": "NIFTY Metal", "change_pct": 0.84, "positive": True},
        {"sector": "NIFTY FMCG", "change_pct": -0.28, "positive": False},
        {"sector": "NIFTY Bank", "change_pct": -0.42, "positive": False}
    ]

@router.get("/breadth")
async def get_market_breadth():
    return market_ingest.get_market_breadth()

@router.get("/fii-dii")
async def get_fii_dii():
    return market_ingest.get_fii_dii_flows()

