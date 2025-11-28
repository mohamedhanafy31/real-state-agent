"""
Prometheus metrics endpoint.
"""
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Metrics
websocket_connections = Counter(
    'orchestrator_websocket_connections_total',
    'Total number of WebSocket connections',
    ['mode']
)

websocket_messages = Counter(
    'orchestrator_websocket_messages_total',
    'Total number of WebSocket messages',
    ['type']
)

session_duration = Histogram(
    'orchestrator_session_duration_seconds',
    'Session duration in seconds',
    ['mode', 'status']
)

api_requests = Counter(
    'orchestrator_api_requests_total',
    'Total number of API requests',
    ['service', 'status']
)

api_latency = Histogram(
    'orchestrator_api_latency_seconds',
    'API request latency in seconds',
    ['service']
)

active_sessions = Gauge(
    'orchestrator_active_sessions',
    'Number of active sessions',
    ['mode']
)


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

