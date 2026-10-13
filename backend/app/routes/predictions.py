from fastapi import APIRouter
from app.services.ml_service import ml_service
from app.schemas.schemas import PredictionResponse

router = APIRouter(prefix="/v1/predictions", tags=["Predictions (LSTM)"])

@router.get("/{symbol}", response_model=PredictionResponse)
async def get_prediction(symbol: str, horizon: int = 7):
    return ml_service.predict_symbol(symbol, horizon)

@router.get("/{symbol}/backtest")
async def get_backtest(symbol: str):
    return ml_service.get_backtest_scorecard(symbol)
