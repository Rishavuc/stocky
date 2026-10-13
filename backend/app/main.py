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

# Mount remaining static assets (css, js, pdf, images)
if os.path.exists(project_root):
    app.mount("/", StaticFiles(directory=project_root, html=True), name="static")
