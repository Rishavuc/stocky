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
def square_off(symbol: str, product: str = "CNC"):
    try:
        return paper_trading.square_off_position(symbol, product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset")
def reset_paper_account():
    return paper_trading.reset_account()
