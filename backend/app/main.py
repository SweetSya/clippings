import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.worker import worker_instance

# Import all routers
from app.routers import (
    health,
    auth,
    settings as settings_router,
    videos,
    clips,
    shorts,
    tts,
    presets,
    audio
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    await init_db()
    logger.info("Starting background worker...")
    worker_instance.start()
    yield
    logger.info("Stopping background worker...")
    await worker_instance.stop()

app = FastAPI(
    title="Local AI Video Clipper & Shorts Generator",
    version="2.1.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler for uniform Error Envelope
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 409:
        code = "CONFLICT"
    elif exc.status_code == 422:
        code = "UNPROCESSABLE_ENTITY"
    elif exc.status_code == 429:
        code = "TOO_MANY_REQUESTS"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "detail": None
            }
        }
    )

# Include routers under /api
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(settings_router.public_router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(clips.router, prefix="/api")
app.include_router(shorts.router, prefix="/api")
app.include_router(tts.router, prefix="/api")
app.include_router(presets.router, prefix="/api")
app.include_router(audio.router, prefix="/api")

@app.get("/")
async def root():
    return {
        "name": "Local AI Video Clipper API",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/api/health"
    }
