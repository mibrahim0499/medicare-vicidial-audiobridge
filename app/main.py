"""FastAPI application entry point for Audio Streaming Bridge"""

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api import websocket, health, calls
from app.database.connection import init_db

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

app = FastAPI(
    title="Audio Streaming Bridge",
    description="Real-time audio streaming bridge between VICIdial/Asterisk and AI backend",
    version="1.0.0"
)

# CORS middleware - parse CORS_ORIGINS string
cors_origins = ["*"] if settings.CORS_ORIGINS == "*" else [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(calls.router, prefix="/api", tags=["calls"])
app.include_router(websocket.router, tags=["websocket"])

# Mount static files for dashboard
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # Static directory might not exist in all environments


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()
    
    # Start Asterisk monitor if configured (in background, non-blocking)
    if settings.ASTERISK_HOST and settings.ASTERISK_PASSWORD:
        try:
            # Try WebSocket monitor first, fallback to polling if enabled
            if settings.USE_POLLING_MONITOR:
                from app.services.asterisk_polling import start_polling_monitor
                async def start_monitor_background():
                    try:
                        await start_polling_monitor()
                    except Exception as e:
                        logger.warning(f"Polling monitor error: {e}")
                        logger.info("Application will continue running. REST API endpoints are available.")
                
                asyncio.create_task(start_monitor_background())
                logger.info("Asterisk polling monitor started")
            else:
                from app.services.asterisk_monitor import start_monitor
                # Start monitor in background task - don't block startup if it fails
                async def start_monitor_background():
                    try:
                        await start_monitor()
                    except Exception as e:
                        logger.warning(f"WebSocket monitor failed: {e}")
                        # Fallback to polling if WebSocket fails
                        if settings.USE_POLLING_MONITOR:
                            logger.info("Falling back to polling monitor...")
                            from app.services.asterisk_polling import start_polling_monitor
                            await start_polling_monitor()
                        else:
                            logger.info("Application will continue running. REST API endpoints are available.")
                
                asyncio.create_task(start_monitor_background())
                logger.info("Asterisk WebSocket monitor background task started")
        except Exception as e:
            logger.warning(f"Could not start Asterisk monitor: {e}")
            logger.info("Application will continue running. REST API endpoints are available.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        from app.services.asterisk_monitor import stop_monitor
        await stop_monitor()
    except Exception:
        pass


@app.get("/")
async def root():
    """Root endpoint - redirects to dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

