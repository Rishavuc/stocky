from typing import Optional

from fastapi import APIRouter, HTTPException
from app.services.paper_trading import paper_trading
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse

router = APIRouter(prefix="/v1/paper", tags=["Paper / Mock Trading"])

@router.get("/portfolio", response_model=PaperPortfolioResponse)
def get_paper_portfolio():
    return paper_trading.get_portfolio()

@router.post("/orders")
def place_paper_order(order: PaperOrderRequest):
    try:
        return paper_trading.execute_order(order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/square-off")
def square_off(
    symbol: str,
    product: str = "CNC",
    client_order_id: Optional[str] = None,
    created_at: Optional[str] = None,
    price: Optional[float] = None,
):
    try:
        return paper_trading.square_off_position(
            symbol, product, client_order_id, created_at, price
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset")
def reset_paper_account():
    return paper_trading.reset_account()
