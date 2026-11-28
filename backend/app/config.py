import os
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List, Optional

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

    # Public frontend (Vercel). Used for CORS and for the Kite callback redirect.
    FRONTEND_URL: str = ""
    # Extra comma-separated browser origins allowed to call the API.
    CORS_ORIGINS: str = ""
    # Serve the static frontend from the repo root. Defaults to on in dev and
    # off in production, where Vercel hosts the frontend.
    SERVE_FRONTEND: Optional[bool] = None
    # Seed the shared demo@investorseye.com / "demo" account used by the
    # login page's 1-click demo button. It is public by design.
    DEMO_USERS_ENABLED: bool = True
    # Read the client IP from the rightmost X-Forwarded-For entry (the one a
    # reverse proxy appends). Defaults to on when running on Render.
    TRUST_PROXY_HEADERS: Optional[bool] = None
    # Comma-separated user ids allowed to change server-wide broker sessions
    # (Kite token, Binance account view). Empty means nobody can.
    ADMIN_USER_IDS: str = ""
    # Accept Zerodha's redirect to /kite/callback. Off by default in
    # production: anyone with a Zerodha login could swap the shared session.
    KITE_CALLBACK_ENABLED: Optional[bool] = None
    
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
    # Older name used in render.yaml; copied into KITE_ACCESS_TOKEN if that is unset.
    ZERODHA_ACCESS_TOKEN: Optional[str] = None

    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    UPSTOX_API_KEY: Optional[str] = None
    UPSTOX_API_SECRET: Optional[str] = None
    
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_DEFAULT_CHAT_ID: Optional[str] = None
    
    class Config:
        env_file = str(ENV_FILE)
        extra = "allow"

    @model_validator(mode="after")
    def _derive(self):
        if not is_configured(self.KITE_ACCESS_TOKEN) and is_configured(self.ZERODHA_ACCESS_TOKEN):
            self.KITE_ACCESS_TOKEN = self.ZERODHA_ACCESS_TOKEN
        if self.SERVE_FRONTEND is None:
            self.SERVE_FRONTEND = not self.is_production
        if self.TRUST_PROXY_HEADERS is None:
            self.TRUST_PROXY_HEADERS = os.getenv("RENDER", "").lower() == "true"
        if self.KITE_CALLBACK_ENABLED is None:
            self.KITE_CALLBACK_ENABLED = not self.is_production
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("production", "prod")

    @property
    def admin_user_ids(self) -> set:
        return {u.strip() for u in self.ADMIN_USER_IDS.split(",") if u.strip()}

    @property
    def cors_origins(self) -> List[str]:
        origins = [
            "https://stockvista-analysis-platform.vercel.app",
        ]
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL.rstrip("/"))
        origins += [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if not self.is_production:
            for port in (8000, 3000, 5500, 5173):
                origins += [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
        return list(dict.fromkeys(origins))

settings = Settings()
