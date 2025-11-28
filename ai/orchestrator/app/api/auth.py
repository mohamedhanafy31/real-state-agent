"""
Authentication utility endpoints (service token issuance).
"""
from datetime import datetime, timedelta, timezone
import secrets

import jwt
from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings
from app.logging_config import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/token")
async def issue_service_token(
    x_service_key: str = Header(default=None, alias="X-Service-Key")
):
    """
    Issue a short-lived JWT for client WebSocket sessions.

    Requires callers to present the shared SERVICE_API_KEY via the X-Service-Key header.
    """
    if not settings.service_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service token issuance is disabled",
        )

    if not x_service_key or not secrets.compare_digest(
        x_service_key, settings.service_api_key
    ):
        logger.warning("Denied token issuance due to invalid service key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service key",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.client_token_ttl_seconds)

    payload = {
        "sub": "ai-p-client",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": settings.client_token_ttl_seconds,
    }

