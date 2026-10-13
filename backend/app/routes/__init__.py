from app.routes.instruments import router as instruments_router
from app.routes.markets import router as markets_router
from app.routes.analysis import router as analysis_router
from app.routes.predictions import router as predictions_router
from app.routes.paper_trading import router as paper_trading_router
from app.routes.trades import router as trades_router
from app.routes.alerts import router as alerts_router
from app.routes.learn import router as learn_router
from app.routes.ws import router as ws_router
from app.routes.integrations import router as integrations_router
from app.routes.auth import router as auth_router

__all__ = [
    "instruments_router",
    "markets_router",
    "analysis_router",
    "predictions_router",
    "paper_trading_router",
    "trades_router",
    "alerts_router",
    "learn_router",
    "ws_router",
    "integrations_router",
    "auth_router"
]

