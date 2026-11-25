from fastapi import APIRouter, HTTPException
from app.services.ml_service import ml_service
from app.schemas.schemas import PredictionResponse

router = APIRouter(prefix="/v1/predictions", tags=["Predictions (LSTM)"])


@router.get("/{symbol}", response_model=PredictionResponse)
def get_prediction(symbol: str, horizon: int = 7, model: str = "lstm"):
    try:
        return ml_service.predict_symbol(symbol, horizon, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{symbol}/backtest")
def get_backtest(symbol: str, model: str = "lstm"):
    try:
        return ml_service.get_backtest_scorecard(symbol, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
