from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Numeric, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# ========================================================
# USER & AUTHENTICATION
# ========================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False)
    plan = Column(String(50), default="Pro Trader")
    avatar = Column(String(10), default="IE")
    trading_interest = Column(String(50), default="stocks")
    virtual_balance = Column(Float, default=1000000.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, default=datetime.utcnow)

# ========================================================
# REFERENCE: INSTRUMENTS
# ========================================================
class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    segment = Column(String(20), index=True, nullable=False) # EQ, FNO, MF, CRYPTO
    symbol = Column(String(50), index=True, nullable=False)
    name = Column(String(150), nullable=False)
    exchange = Column(String(20), default="NSE")
    isin = Column(String(50), nullable=True)
    amfi_code = Column(String(50), nullable=True)
    lot_size = Column(Integer, default=1)
    expiry = Column(String(30), nullable=True)
    strike = Column(Float, nullable=True)
    option_type = Column(String(10), nullable=True) # CE, PE
    underlying_symbol = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ========================================================
# MARKET DATA: CANDLES & TICKS
# ========================================================
class Candle(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), index=True, nullable=False)
    timeframe = Column(String(10), index=True, default="1d") # 1m, 5m, 15m, 1h, 1d
    ts = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)
    oi = Column(Float, default=0.0)

class OptionChainSnapshot(Base):
    __tablename__ = "option_chain_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    underlying = Column(String(50), index=True, nullable=False)
    expiry = Column(String(30), index=True, nullable=False)
    ts = Column(DateTime, default=datetime.utcnow)
    strike = Column(Float, nullable=False)
    ce_oi = Column(Float, default=0.0)
    pe_oi = Column(Float, default=0.0)
    ce_iv = Column(Float, default=0.0)
    pe_iv = Column(Float, default=0.0)
    ce_ltp = Column(Float, default=0.0)
    pe_ltp = Column(Float, default=0.0)

# ========================================================
# MOCK / PAPER TRADING
# ========================================================
class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), default="guest_user", index=True)
    initial_cash = Column(Float, default=1000000.0)
    cash = Column(Float, default=1000000.0)
    realized_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), default="guest_user", index=True)
    symbol = Column(String(50), nullable=False)
    product = Column(String(10), default="CNC") # CNC (Delivery), MIS (Intraday 5x)
    qty = Column(Integer, nullable=False)
    avg_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), default="guest_user", index=True)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False) # BUY, SELL
    product = Column(String(10), default="CNC")
    qty = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String(20), default="EXECUTED")
    ts = Column(DateTime, default=datetime.utcnow)

# ========================================================
# UNIFIED TRADE BOOK & BROKER ACCOUNTS
# ========================================================
class BrokerAccount(Base):
    __tablename__ = "broker_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), default="guest_user", index=True)
    broker = Column(String(50), nullable=False) # Zerodha, Upstox, AngelOne, CSV
    account_ref = Column(String(100), nullable=False)
    status = Column(String(20), default="CONNECTED") # CONNECTED, EXPIRED
    last_synced_at = Column(DateTime, default=datetime.utcnow)

class UnifiedTrade(Base):
    __tablename__ = "unified_trades"

    id = Column(Integer, primary_key=True, index=True)
    broker = Column(String(50), nullable=False)
    source_trade_id = Column(String(100), unique=True, index=True)
    symbol = Column(String(50), index=True, nullable=False)
    segment = Column(String(20), default="EQ")
    side = Column(String(10), nullable=False) # BUY, SELL
    qty = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    product = Column(String(10), default="CNC")
    traded_at = Column(DateTime, default=datetime.utcnow)

# ========================================================
# ML PREDICTIONS
# ========================================================
class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), index=True, nullable=False)
    timeframe = Column(String(10), default="1d")
    forecast_horizon = Column(String(20), default="7D")
    current_price = Column(Float, nullable=False)
    predicted_price = Column(Float, nullable=False)
    lower_band = Column(Float, nullable=False) # 10th percentile
    upper_band = Column(Float, nullable=False) # 90th percentile
    confidence_pct = Column(Float, default=92.0)
    mae = Column(Float, default=14.2)
    rmse = Column(Float, default=18.5)
    r2_score = Column(Float, default=0.88)
    directional_accuracy = Column(Float, default=74.5)
    generated_at = Column(DateTime, default=datetime.utcnow)

# ========================================================
# ALERTS
# ========================================================
class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), index=True, nullable=False)
    condition_type = Column(String(50), nullable=False) # PRICE_CROSSES_ABOVE, PRICE_CROSSES_BELOW, RSI_OVERSOLD, PCR_ABOVE
    target_value = Column(Float, nullable=False)
    channels = Column(String(100), default="telegram,email")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"))
    symbol = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    fired_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="DELIVERED")

# ========================================================
# LEARNING & QUIZ
# ========================================================
class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    instructor = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)
    topic = Column(String(50), nullable=False)
    duration = Column(String(50), nullable=False)
    language = Column(String(30), default="English")
    rating = Column(Float, default=4.8)
    link = Column(String(300), nullable=False)
