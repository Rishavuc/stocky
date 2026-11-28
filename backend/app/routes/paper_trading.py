from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security import current_user_id
from app.services.paper_trading import BookConflict, run_on_book
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse

router = APIRouter(prefix="/v1/paper", tags=["Paper / Mock Trading"])

# Every route: who is asking (signed token) -> load THEIR book -> run -> save.
# Reading the portfolio also saves, because it can fill pending limit orders.

_BUSY = "Your portfolio was updated by another request. Please retry."


async def _run(db, user_id, operation, error_status: int = 400):
    try:
        return await run_on_book(db, user_id, operation)
    except BookConflict:
        raise HTTPException(status_code=409, detail=_BUSY)
    except ValueError as e:
        raise HTTPException(status_code=error_status, detail=str(e))


@router.get("/portfolio", response_model=PaperPortfolioResponse)
async def get_paper_portfolio(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)):
    return await _run(db, user_id, lambda book: book.get_portfolio())


@router.post("/orders")
async def place_paper_order(order: PaperOrderRequest, user_id: str = Depends(current_user_id),
                            db: AsyncSession = Depends(get_db)):
    return await _run(db, user_id, lambda book: book.execute_order(order))


@router.delete("/orders/{order_id}")
async def cancel_paper_order(order_id: int, user_id: str = Depends(current_user_id),
                             db: AsyncSession = Depends(get_db)):
    return await _run(db, user_id, lambda book: book.cancel_order(order_id), error_status=404)


@router.post("/square-off")
async def square_off(symbol: str = Query(..., min_length=1, max_length=30),
                     product: str = Query("CNC", max_length=5),
                     user_id: str = Depends(current_user_id),
                     db: AsyncSession = Depends(get_db)):
    return await _run(db, user_id, lambda book: book.square_off_position(symbol, product))


@router.post("/reset")
async def reset_paper_account(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)):
    return await _run(db, user_id, lambda book: book.reset_account())
