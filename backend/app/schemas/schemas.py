from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

# ========================================================
# MARKET & INSTRUMENT SCHEMAS
# ========================================================
class InstrumentBase(BaseModel):
    symbol: str
    name: str
    segment: str
    exchange: str = "NSE"
    lot_size: int = 1
    strike: Optional[float] = None
    expiry: Optional[str] = None
    option_type: Optional[str] = None

class QuoteResponse(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    high_24h: float
    low_24h: float
    volume: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"
    is_synthetic: bool = False
    as_of: Optional[datetime] = None

class CandleResponse(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "unknown"
    is_synthetic: bool = False

class IndexOverview(BaseModel):
    name: str
    value: float
    change: float
    change_pct: float
    positive: bool
    sparkline: List[float]

# ========================================================
# ANALYSIS SCHEMAS
# ========================================================
class IndicatorItem(BaseModel):
    name: str
    value: str
    signal: str
    signal_type: str # buy, sell, neutral

class TechnicalAnalysisResponse(BaseModel):
    symbol: str
    price: float
    change_pct: float
    summary_signal: str # STRONG_BUY, BUY, NEUTRAL, SELL
    indicators: List[IndicatorItem]
    ratios: Dict[str, str]
    support_levels: List[float]
    resistance_levels: List[float]

class OptionChainItem(BaseModel):
    strike: float
    ce_oi: float
    ce_change_oi: float
    ce_ltp: float
    ce_iv: float
    pe_ltp: float
    pe_iv: float
    pe_change_oi: float
    pe_oi: float

class OptionChainResponse(BaseModel):
    underlying: str
    spot_price: float
    pcr: float
    max_pain: float
    atm_iv: float
    expiry_date: str
    strikes: List[OptionChainItem]

# ========================================================
# ML PREDICTION SCHEMAS
# ========================================================
class PredictionPoint(BaseModel):
    day: str
    date: Optional[str] = None
    predicted: float
    lower_band: float
    upper_band: float

class PredictionResponse(BaseModel):
    symbol: str
    horizon: str = "7D"
    current_price: float
    predicted_target: float
    expected_return_pct: float
    lower_bound: float
    upper_bound: float
    confidence_score: float
    accuracy_metrics: Dict[str, Any] # mae, rmse, r2, win_rate
    forecast_points: List[PredictionPoint]
    predictions: List[PredictionPoint] = []  # alias of forecast_points for client compatibility
    data_source: str = "unknown"
    as_of: Optional[datetime] = None
    disclaimer: str

# ========================================================
# MOCK / PAPER TRADING SCHEMAS
# ========================================================
class PaperOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=30)
    side: Literal["BUY", "SELL"]
    product: Literal["CNC", "MIS"] = "CNC"
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    # float so crypto can trade fractions (0.01 BTC); the engine still
    # requires whole shares for equities.
    qty: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)

    @field_validator("symbol", "side", "product", "order_type", mode="before")
    @classmethod
    def _normalise(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _limit_needs_price(self):
        if self.order_type == "LIMIT" and self.price is None:
            raise ValueError("LIMIT orders need a price")
        return self

class PaperPositionResponse(BaseModel):
    symbol: str
    product: str
    qty: float
    avg_price: float
    ltp: float
    current_value: float
    pnl: float
    pnl_pct: float

class PaperPortfolioResponse(BaseModel):
    total_portfolio_value: float
    cash_balance: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    total_trades_count: int
    positions: List[PaperPositionResponse]
    orders: List[Dict[str, Any]] = []
    pending_orders: List[Dict[str, Any]] = []
    # Cash is always INR; crypto positions are priced in USDT and converted
    # with this rate, so the UI can do the same maths.
    usd_inr_rate: float = 1.0

# ========================================================
# BROKER & UNIFIED TRADE BOOK SCHEMAS
# ========================================================
class BrokerConnectRequest(BaseModel):
    broker_name: str # Zerodha, Upstox, AngelOne
    client_id: str
    api_key: Optional[str] = None
    access_token: Optional[str] = None

class UnifiedTradeItem(BaseModel):
    id: int
    broker: str
    symbol: str
    segment: str
    side: str
    qty: int
    price: float
    traded_at: str

# ========================================================
# ALERTS SCHEMAS
# ========================================================
class AlertCreateRequest(BaseModel):
    symbol: str
    condition_type: str
    target_value: float
    channels: str = "telegram,email"

class AlertRuleResponse(BaseModel):
    id: int
    symbol: str
    condition_type: str
    target_value: float
    channels: str
    active: bool
    created_at: datetime

# ========================================================
# LEARN & QUIZ SCHEMAS
# ========================================================
class QuizAnswerRequest(BaseModel):
    question_id: int = Field(..., ge=1)
    selected_option: int = Field(..., ge=0, le=3)

class QuizAnswerResponse(BaseModel):
    correct: bool
    explanation: str
    next_question_id: Optional[int] = None
    correct_option: Optional[int] = None
    correct_answer: Optional[str] = None
