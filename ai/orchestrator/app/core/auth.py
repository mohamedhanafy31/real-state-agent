"""
Authentication utilities for WebSocket connections.
"""
import jwt
from typing import Optional
from fastapi import WebSocket, WebSocketException, status
from app.core.config import settings


def verify_token(token: str) -> bool:
    """
    Verify a Bearer token.
    
    Args:
        token: The token to verify (without 'Bearer ' prefix)
        
    Returns:
        True if token is valid, False otherwise
    """
    try:
        # In production, verify against your auth service
        # For now, simple check if token exists
        if not token or token == "invalid":
            return False
        
        # If JWT_SECRET is set and not default, verify JWT
        if settings.jwt_secret != "your-secret-key-change-in-production":
            try:
                jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
                return True
            except jwt.InvalidTokenError:
                return False
        
        # For development: accept any non-empty token
        return len(token) > 0
    except Exception:
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

