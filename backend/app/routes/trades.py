from fastapi import APIRouter, UploadFile, File, Form
from typing import List, Optional
from app.services.trade_sync import trade_sync
from app.schemas.schemas import UnifiedTradeItem, BrokerConnectRequest

router = APIRouter(prefix="/v1", tags=["Unified Trade Book & Brokers"])

@router.get("/trades", response_model=List[UnifiedTradeItem])
async def get_trades(broker: Optional[str] = None):
    return trade_sync.get_unified_trade_book(broker)

@router.get("/portfolio/holdings")
async def get_unified_holdings():
    return trade_sync.get_holdings_summary()

@router.post("/brokers/connect")
async def connect_broker(req: BrokerConnectRequest):
    return trade_sync.connect_broker(req.broker_name, req.client_id)

@router.post("/trades/upload-csv")
async def upload_tradebook_csv(file: UploadFile = File(...), broker_name: str = Form("CSV Import")):
    contents = await file.read()
    csv_text = contents.decode("utf-8")
    return trade_sync.import_csv_tradebook(csv_text, broker_name)
