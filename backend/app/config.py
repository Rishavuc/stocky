import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def is_configured(value: Optional[str]) -> bool:
    """Treat blank, placeholder and 'none' strings as an unset credential."""
    if not value:
        return False
    lowered = value.strip().lower()
    return not (lowered.startswith("your_") or "placeholder" in lowered or lowered == "none")

class Settings(BaseSettings):
    APP_NAME: str = "StockVista Analysis Platform"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./investors_eye.db"
    
    # Redis
    REDIS_URL: Optional[str] = None
    
    # Auth
    JWT_SECRET_KEY: str = "investors_eye_super_secret_jwt_key_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Google Sign-In (OAuth 2.0 Web client ID from Google Cloud Console).
    # Public value: it is sent to the browser to render the Google button.
    GOOGLE_CLIENT_ID: Optional[str] = None

    # External Broker & Feed Credentials
    ZERODHA_API_KEY: Optional[str] = None
    ZERODHA_API_SECRET: Optional[str] = None
    KITE_API_KEY: Optional[str] = None
    KITE_API_SECRET: Optional[str] = None
    KITE_ACCESS_TOKEN: Optional[str] = None

    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    UPSTOX_API_KEY: Optional[str] = None
    UPSTOX_API_SECRET: Optional[str] = None
    
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_DEFAULT_CHAT_ID: Optional[str] = None
    
    class Config:
        env_file = str(ENV_FILE)
        extra = "allow"

settings = Settings()
