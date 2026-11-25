from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security import current_user_id
from app.services.paper_trading import run_on_book
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse

router = APIRouter(prefix="/v1/paper", tags=["Paper / Mock Trading"])

# Every route: who is asking (signed token) -> load THEIR book -> run -> save.
# Reading the portfolio also saves, because it can fill pending limit orders.


@router.get("/portfolio", response_model=PaperPortfolioResponse)
async def get_paper_portfolio(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)):
    return await run_on_book(db, user_id, lambda book: book.get_portfolio())


@router.post("/orders")
async def place_paper_order(order: PaperOrderRequest, user_id: str = Depends(current_user_id),
                            db: AsyncSession = Depends(get_db)):
    try:
        return await run_on_book(db, user_id, lambda book: book.execute_order(order))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/orders/{order_id}")
async def cancel_paper_order(order_id: int, user_id: str = Depends(current_user_id),
                             db: AsyncSession = Depends(get_db)):
    try:
        return await run_on_book(db, user_id, lambda book: book.cancel_order(order_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/square-off")
async def square_off(symbol: str, product: str = "CNC", user_id: str = Depends(current_user_id),
                     db: AsyncSession = Depends(get_db)):
    try:
        return await run_on_book(db, user_id, lambda book: book.square_off_position(symbol, product))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset")
async def reset_paper_account(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)):
    return await run_on_book(db, user_id, lambda book: book.reset_account())
