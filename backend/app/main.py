import html as html_lib
import os
import re
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import math

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.security import check_jwt_config
from app.services.activity_logger import record_activity, resolve_user_id_from_header
from app.routes import (
    instruments_router,
    markets_router,
    analysis_router,
    predictions_router, estimates_router,
    paper_trading_router,
    trades_router,
    alerts_router,
    learn_router,
    ws_router,
    integrations_router,
    auth_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast: never serve production with a guessable token secret.
    check_jwt_config()
    # Startup: Initialize DB models
    try:
        await init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database init warning (running in lightweight mode): {e}")
    yield
    # Shutdown
    print("Shutting down StockVista Analysis Platform API...")
    try:
        from app.services.ws_gateway import ws_gateway
        await ws_gateway.shutdown()
    except Exception as exc:
        print(f"WebSocket gateway shutdown warning: {type(exc).__name__}")

app = FastAPI(
    title="StockVista Analysis Platform — Market Analysis & Trading API",
    description="Real-time Indian Stocks, F&O, Mutual Funds & Crypto Analysis, LSTM Predictions, Mock Trading & Unified Trade Book API.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Kite request/access tokens are short alphanumeric strings.
_KITE_TOKEN_RE = re.compile(r"[A-Za-z0-9]{8,128}")

def _finite(value):
    """Replace inf/nan (not valid JSON) with None, recursively."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Same 422 shape as FastAPI's default, minus the echoed raw input: it can
    # hold passwords, and Infinity/NaN in it made the default handler 500.
    errors = []
    for err in exc.errors():
        err = {k: v for k, v in err.items() if k not in ("input", "url")}
        if isinstance(err.get("ctx"), dict):
            err["ctx"] = {k: str(v) if isinstance(v, Exception) else v for k, v in err["ctx"].items()}
        errors.append(err)
    return JSONResponse(status_code=422, content={"detail": _finite(jsonable_encoder(errors))})


MEANINGFUL_GET_PATHS = ("/v1/auth/me", "/v1/auth/activity", "/v1/paper/portfolio")


@app.middleware("http")
async def log_user_activity(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Response-Time-ms"] = str(elapsed_ms)

    path = request.url.path
    method = request.method.upper()
    meaningful_get = method == "GET" and (
        path in MEANINGFUL_GET_PATHS or path.startswith("/v1/auth/")
    )
    if path.startswith("/v1/") and (method != "GET" or meaningful_get):
        user_id = resolve_user_id_from_header(request.headers.get("authorization"))
        if user_id:
            await record_activity(
                user_id=user_id,
                event_type="api_request",
                method=method,
                path=path,
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                details={"duration_ms": elapsed_ms},
            )
    return response

# CORS: explicit origins only. The frontend sends a Bearer token header, not
# cookies, so credentials stay off (a wildcard plus credentials would let any
# site make authenticated calls). No wildcard regex: anyone can create a
# Vercel project whose name starts with ours. Add preview URLs to CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Response-Time-ms"],
)

# Include all API Routers
app.include_router(instruments_router)
app.include_router(markets_router)
app.include_router(analysis_router)
app.include_router(predictions_router)
app.include_router(estimates_router)
app.include_router(paper_trading_router)
app.include_router(trades_router)
app.include_router(alerts_router)
app.include_router(learn_router)
app.include_router(ws_router)
app.include_router(integrations_router)
app.include_router(auth_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV
    }

# Serve root project directory as static files for integrated frontend delivery
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(project_root, "index.html")
    if settings.SERVE_FRONTEND and os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "StockVista Analysis Platform API is running. Visit /docs for OpenAPI specs."}


def _page(name: str) -> FileResponse:
    if not settings.SERVE_FRONTEND:
        raise StarletteHTTPException(status_code=404)
    return FileResponse(os.path.join(project_root, name))


@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
async def serve_login():
    return _page("login.html")

@app.get("/markets.html", include_in_schema=False)
async def serve_markets():
    return _page("markets.html")

@app.get("/analysis.html", include_in_schema=False)
async def serve_analysis():
    return _page("analysis.html")

@app.get("/predictions.html", include_in_schema=False)
async def serve_predictions():
    return _page("predictions.html")

@app.get("/estimates.html", include_in_schema=False)
async def serve_estimates():
    return _page("predictions.html")

@app.get("/mock-trading.html", include_in_schema=False)
async def serve_mock_trading():
    return _page("mock-trading.html")

@app.get("/courses.html", include_in_schema=False)
async def serve_courses():
    return _page("courses.html")

@app.get("/kite/callback", include_in_schema=False)
@app.get("/v1/integrations/kite/callback", include_in_schema=False)
async def kite_callback(request_token: str = None, action: str = None, status: str = None):
    from app.services.market_ingest import market_ingest
    success = False
    message = "No request token received."
    if request_token and _KITE_TOKEN_RE.fullmatch(request_token):
        # Kite's SDK does blocking HTTP; keep it off the event loop.
        res = await run_in_threadpool(market_ingest.generate_kite_session, request_token)
        if res.get("success"):
            success = True
            message = "Zerodha Kite Connect session activated successfully! Live quotes and historical candles are now running directly through your Kite API key."
        else:
            # Log the provider error server-side; never echo it into HTML.
            print(f"[Kite callback] session exchange failed: {str(res.get('error'))[:200]}")
            message = "Kite session could not be activated. The fallback NSE live feed remains active."
    elif request_token:
        message = "Invalid request token."
    message = html_lib.escape(message)
    markets_url = html_lib.escape(f"{settings.FRONTEND_URL.rstrip('/')}/markets.html", quote=True)

    status_icon = "✅" if success else "ℹ️"
    status_title = "Kite Connected Successfully!" if success else "Kite Authentication Status"
    
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>{status_title} — StockVista Analysis Platform</title>
        <meta http-equiv="refresh" content="3;url={markets_url}" />
        <style>
            body {{ font-family: 'Inter', system-ui, sans-serif; background: #0b0e14; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #151922; border: 1px solid {'#00d09c' if success else '#3b82f6'}; border-radius: 16px; padding: 40px; max-width: 480px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
            h1 {{ font-size: 24px; margin-bottom: 12px; color: {'#00d09c' if success else '#60a5fa'}; }}
            p {{ color: #94a3b8; line-height: 1.6; margin-bottom: 24px; font-size: 14px; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #00d09c; color: #0b0e14; font-weight: 600; border-radius: 8px; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 48px; margin-bottom: 16px;">{status_icon}</div>
            <h1>{status_title}</h1>
            <p>{message}</p>
            <p style="font-size: 13px; color: #64748b;">Redirecting to markets overview in 3 seconds...</p>
            <a href="{markets_url}" class="btn">Go to Dashboard Now</a>
        </div>
    </body>
    </html>"""
    return HTMLResponse(content=html, headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
    })

class PublicStaticFiles(StaticFiles):
    """Serve the frontend only: an allowlist of top-level files and asset types.

    The repo root also holds backend source, render.yaml, .env, SQLite
    databases (backend/data/*.db) and logs, so anything not explicitly a
    frontend asset is a 404.
    """

    ALLOWED_SUFFIXES = (
        ".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".ico", ".webp", ".woff", ".woff2", ".ttf", ".map",
    )
    BLOCKED_TOP_DIRS = {
        "backend", "python_backend", "api", "tools", "presentation", "report",
        "deliverables", "node_modules", "android", "ios", "linux", "macos",
        "windows", "data", "build",
    }

    async def get_response(self, path, scope):
        parts = [p for p in path.replace("\\", "/").split("/") if p and p != "."]
        name = parts[-1].lower() if parts else ""
        if (
            not parts
            or any(p.startswith(".") or p == ".." for p in parts)
            or parts[0].lower() in self.BLOCKED_TOP_DIRS
            or not name.endswith(self.ALLOWED_SUFFIXES)
        ):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


# Mount the frontend assets (css, js, images) only where the backend hosts the
# UI (local dev). In production Vercel serves the frontend.
if settings.SERVE_FRONTEND and os.path.exists(project_root):
    app.mount("/", PublicStaticFiles(directory=project_root, html=False), name="static")

