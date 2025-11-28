"""
Health check endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.services.redis_client import redis_client
from app.services.asr_client import ASRClient
from app.services.rag_client import RAGClient
from app.services.tts_client import TTSClient
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "orchestrator"
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with service status."""
    health_status = {
        "status": "healthy",
        "service": "orchestrator",
        "services": {}
    }
    
    # Check Redis
    try:
        if redis_client.redis:
            await redis_client.redis.ping()
            health_status["services"]["redis"] = {
                "status": "healthy",
                "host": redis_client.redis.connection_pool.connection_kwargs.get("host", "unknown")
            }
        else:
            health_status["services"]["redis"] = {"status": "not_connected"}
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check ASR service
    try:
        asr_client = ASRClient()
        health_status["services"]["asr"] = {
            "status": "configured",
            "url": asr_client.base_url
        }
    except Exception as e:
        health_status["services"]["asr"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check RAG service
    try:
        rag_client = RAGClient()
        health_status["services"]["rag"] = {
            "status": "configured",
            "url": rag_client.base_url
        }
    except Exception as e:
        health_status["services"]["rag"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check TTS service
    try:
        tts_client = TTSClient()
        health_status["services"]["tts"] = {
            "status": "configured",
            "url": tts_client.base_url
        }
    except Exception as e:
        health_status["services"]["tts"] = {
            "status": "error",
            "error": str(e)
        }
    
    return health_status

