"""
Main FastAPI application for the orchestrator.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from app.core.config import settings
from app.logging_config import setup_logging, get_logger
from app.services.redis_client import redis_client
from app.api import health, metrics
from app.api import documents
from app.api.websocket import websocket_endpoint

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("Starting orchestrator service...")
    try:
        await redis_client.connect()
        logger.info("Orchestrator service started successfully")
    except Exception as e:
        logger.error(f"Failed to start orchestrator service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down orchestrator service...")
    try:
        await redis_client.disconnect()
        logger.info("Orchestrator service shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Real-Time Orchestrator",
    description="High-performance orchestrator for Arabic RAG chatbot with voice/text support",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(documents.router)


# WebSocket endpoints
@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """WebSocket endpoint for voice mode."""
    await websocket_endpoint(websocket, mode="voice")


@app.websocket("/ws/text")
async def websocket_text(websocket: WebSocket):
    """WebSocket endpoint for text mode."""
    await websocket_endpoint(websocket, mode="text")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Real-Time Orchestrator",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket_voice": "/ws/voice",
            "websocket_text": "/ws/text",
            "health": "/health",
            "health_detailed": "/health/detailed",
            "metrics": "/metrics",
            "test_client": "/test"
        }
    }


# Test client page
@app.get("/test", response_class=HTMLResponse)
async def test_client():
    """Serve the test client HTML page."""
    static_dir = Path(__file__).parent / "static"
    html_file = static_dir / "test_client.html"
    
    if not html_file.exists():
        return HTMLResponse(
            content="<h1>Test client not found</h1><p>The test_client.html file is missing.</p>",
            status_code=404
        )
    
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)


def _redoc_response():
    """Helper to render the ReDoc HTML shell."""
    return get_redoc_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title="Real-Time Orchestrator ReDoc",
        redoc_js_url="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"
    )


@app.get("/docs/redoc", include_in_schema=False)
async def redoc_documentation_docs():
    """Serve ReDoc under /docs/redoc for consistency with Swagger UI."""
    return _redoc_response()


@app.get("/redoc", include_in_schema=False)
async def redoc_documentation_root():
    """Serve ReDoc under /redoc to match FastAPI defaults and tooling expectations."""
    return _redoc_response()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )

