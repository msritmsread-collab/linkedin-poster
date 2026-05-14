"""
LinkedIn Auto-Poster — FastAPI Backend

In production, serves the built React app from frontend/dist/
In development, run the Vite dev server separately on port 5174.

Start: uvicorn projects.linkedin_poster.backend.main:app --port 8001
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
load_dotenv(Path(_ROOT, ".env"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import database as db
from backend.api.routes import router as api_router
from backend.api.settings_routes import router as settings_router
from backend.api.analytics import router as analytics_router
from backend.api.auth_routes import router as auth_router
from backend.api.admin_routes import router as admin_router
from backend.api.alert_routes import router as alerts_router
from backend.scheduler import create_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_poster")

_DATA_IMAGES = _ROOT / "data" / "images"
_FRONTEND_DIST = _ROOT / "frontend" / "dist"
os.makedirs(_DATA_IMAGES, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("Database initialised.")
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="MS. READ LinkedIn Auto-Poster",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True if _CORS_ORIGINS != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(api_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")

# Uploaded images
app.mount("/uploads", StaticFiles(directory=_DATA_IMAGES), name="uploads")

# Serve built React SPA (production)
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str = ""):
        # Don't intercept API or upload routes
        if full_path.startswith("api/") or full_path.startswith("uploads/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "service": "MS. READ LinkedIn Auto-Poster",
            "note": "Frontend not built yet. Run: cd projects/linkedin_poster/frontend && npm install && npm run build",
            "api_docs": "/api/docs",
        }
