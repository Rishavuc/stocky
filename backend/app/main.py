import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routes import (
    instruments_router,
    markets_router,
    analysis_router,
    predictions_router,
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
    # Startup: Initialize DB models
    try:
        await init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database init warning (running in lightweight mode): {e}")
    yield
    # Shutdown
    print("Shutting down Investor's EYE API...")

app = FastAPI(
    title="Investor's EYE — Market Analysis & Trading API",
    description="Real-time Indian Stocks, F&O, Mutual Funds & Crypto Analysis, LSTM Predictions, Mock Trading & Unified Trade Book API.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API Routers
app.include_router(instruments_router)
app.include_router(markets_router)
app.include_router(analysis_router)
app.include_router(predictions_router)
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

# Dedicated HTML route fallbacks
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(project_root, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Investor's EYE API is running. Visit /docs for OpenAPI specs."}

@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
async def serve_login():
    return FileResponse(os.path.join(project_root, "login.html"))

@app.get("/markets.html", include_in_schema=False)
async def serve_markets():
    return FileResponse(os.path.join(project_root, "markets.html"))

@app.get("/analysis.html", include_in_schema=False)
async def serve_analysis():
    return FileResponse(os.path.join(project_root, "analysis.html"))

@app.get("/predictions.html", include_in_schema=False)
async def serve_predictions():
    return FileResponse(os.path.join(project_root, "predictions.html"))

@app.get("/mock-trading.html", include_in_schema=False)
async def serve_mock_trading():
    return FileResponse(os.path.join(project_root, "mock-trading.html"))

@app.get("/courses.html", include_in_schema=False)
async def serve_courses():
    return FileResponse(os.path.join(project_root, "courses.html"))

@app.get("/kite/callback", include_in_schema=False)
@app.get("/v1/integrations/kite/callback", include_in_schema=False)
async def kite_callback(request_token: str = None, action: str = None, status: str = None):
    from fastapi.responses import HTMLResponse
    from app.services.market_ingest import market_ingest
    success = False
    message = "No request token received."
    if request_token:
        res = market_ingest.generate_kite_session(request_token)
        if res.get("success"):
            success = True
            message = "Zerodha Kite Connect session activated successfully! Live quotes and historical candles are now running directly through your Kite API key."
        else:
            message = f"Kite session notice: {res.get('error')}. Fallback NSE live feed remains 100% active."

    status_icon = "✅" if success else "ℹ️"
    status_title = "Kite Connected Successfully!" if success else "Kite Authentication Status"
    
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>{status_title} — Investor's EYE</title>
        <meta http-equiv="refresh" content="3;url=/markets.html" />
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
            <a href="/markets.html" class="btn">Go to Dashboard Now</a>
        </div>
    </body>
    </html>"""
    return HTMLResponse(content=html)

# Mount remaining static assets (css, js, pdf, images)
if os.path.exists(project_root):
    app.mount("/", StaticFiles(directory=project_root, html=True), name="static")

