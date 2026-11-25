from fastapi import APIRouter, HTTPException
from app.services.ml_service import ml_service
from app.schemas.schemas import PredictionResponse

# Public-facing name is "Estimates"; the legacy /v1/predictions prefix is
# retained so existing bookmarks and integrations keep working.
router = APIRouter(prefix="/v1/predictions", tags=["Estimates (LSTM)"])
estimates_router = APIRouter(prefix="/v1/estimates", tags=["Estimates (LSTM)"])


def _get_estimate(symbol: str, horizon: int = 7, model: str = "lstm"):
    try:
        return ml_service.predict_symbol(symbol, horizon, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _get_backtest(symbol: str, model: str = "lstm"):
    try:
        return ml_service.get_backtest_scorecard(symbol, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{symbol}", response_model=PredictionResponse)
def get_prediction(symbol: str, horizon: int = 7, model: str = "lstm"):
    return _get_estimate(symbol, horizon, model)


@router.get("/{symbol}/backtest")
def get_backtest(symbol: str, model: str = "lstm"):
    return _get_backtest(symbol, model)


@estimates_router.get("/{symbol}", response_model=PredictionResponse)
def get_estimate(symbol: str, horizon: int = 7, model: str = "lstm"):
    return _get_estimate(symbol, horizon, model)


@estimates_router.get("/{symbol}/backtest")
def get_estimate_backtest(symbol: str, model: str = "lstm"):
    return _get_backtest(symbol, model)
