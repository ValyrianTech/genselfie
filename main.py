import argparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings, setup_logging, logger
from database import init_db
from routers import admin, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting GenSelfie server...")
    await init_db()
    logger.info(f"ComfyUI URL: {settings.comfyui_url}")
    yield
    logger.info("Shutting down GenSelfie server...")


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    debug=settings.debug
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(public.router)
app.include_router(admin.router, prefix="/admin")


if __name__ == "__main__":
    import uvicorn
    
    parser = argparse.ArgumentParser(description="GenSelfie Server")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    settings.verbose = args.verbose
    
    log_level = "debug" if args.verbose else "info"
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload, log_level=log_level)
