from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from typing import List, Optional
from app.security import current_user_id
from app.services.trade_sync import trade_sync
from app.schemas.schemas import UnifiedTradeItem, BrokerConnectRequest

router = APIRouter(prefix="/v1", tags=["Unified Trade Book & Brokers"])

MAX_CSV_BYTES = 1_000_000  # 1 MB is thousands of trades; stops memory abuse

# Trade books are per user: every call passes the signed-in user_id down.

@router.get("/trades", response_model=List[UnifiedTradeItem])
async def get_trades(broker: Optional[str] = Query(None, max_length=50),
                     user_id: str = Depends(current_user_id)):
    return trade_sync.get_unified_trade_book(user_id, broker)

@router.get("/portfolio/holdings")
async def get_unified_holdings(user_id: str = Depends(current_user_id)):
    return trade_sync.get_holdings_summary(user_id)

@router.post("/brokers/connect")
async def connect_broker(req: BrokerConnectRequest, user_id: str = Depends(current_user_id)):
    try:
        return trade_sync.connect_broker(user_id, req.broker_name, req.client_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/trades/upload-csv")
async def upload_tradebook_csv(file: UploadFile = File(...),
                               broker_name: str = Form("CSV Import", min_length=1, max_length=50),
                               user_id: str = Depends(current_user_id)):
    # Read one byte past the limit so an oversized file is detected without
    # loading all of it.
    contents = await file.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is too large (max 1 MB).")
    try:
        csv_text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 text.")
    return trade_sync.import_csv_tradebook(user_id, csv_text, broker_name)
