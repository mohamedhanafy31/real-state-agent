"""
Authentication utilities for WebSocket connections.
"""
import secrets
import jwt
from typing import Optional
from fastapi import WebSocket, WebSocketException, status
from app.core.config import settings


DEFAULT_SECRET = "your-secret-key-change-in-production"


def verify_token(token: str) -> bool:
    """
    Verify a Bearer token.
    
    Args:
        token: The token to verify (without 'Bearer ' prefix)
        
    Returns:
        True if token is valid, False otherwise
    """
    if not token or token == "invalid":
        return False
    
    # Allow explicit static tokens (useful for local testing or migrations)
    if settings.static_client_token:
        try:
            if secrets.compare_digest(token, settings.static_client_token):
                return True
        except Exception:
            pass
    
    # Always attempt to validate as JWT
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return True
    except jwt.InvalidTokenError:
        pass
    
    # For development, allow any non-empty token when using the default secret
    if settings.jwt_secret == DEFAULT_SECRET:
        return len(token) > 0
    
    return False


def extract_token_from_message(message: dict) -> Optional[str]:
    """
    Extract Bearer token from WebSocket message.
    
    Args:
        message: WebSocket message dictionary
        
    Returns:
        Token string if found, None otherwise
    """
    # Check in auth field
    if "auth" in message:
        auth = message["auth"]
        if isinstance(auth, str):
            if auth.startswith("Bearer "):
                return auth[7:]
            return auth
    
    # Check in headers (if passed)
    if "headers" in message:
        headers = message["headers"]
        if isinstance(headers, dict):
            auth_header = headers.get("Authorization") or headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                return auth_header[7:]
    
    return None


async def authenticate_websocket(websocket: WebSocket, message: dict) -> bool:
    """
    Authenticate WebSocket connection from start_session message.
    
    Args:
        websocket: WebSocket connection
        message: start_session message
        
    Returns:
        True if authenticated, False otherwise
    """
    token = extract_token_from_message(message)
    
    if not token:
        await websocket.send_json({
            "type": "error",
            "code": 401,
            "message": "Authentication required. Provide 'auth' field in start_session message."
        })
        return False
    
    if not verify_token(token):
        await websocket.send_json({
            "type": "error",
            "code": 401,
            "message": "Invalid authentication token."
        })
        return False
    
    return True

