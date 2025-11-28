"""
WebSocket endpoint handlers.
"""
import uuid
from typing import Optional
from fastapi import WebSocket, WebSocketException, status
from app.orchestrators.voice_orchestrator import VoiceOrchestrator
from app.orchestrators.text_orchestrator import TextOrchestrator
from app.core.auth import authenticate_websocket
from app.logging_config import get_logger

logger = get_logger(__name__)


async def websocket_endpoint(websocket: WebSocket, mode: str = "voice"):
    """
    Main WebSocket endpoint for orchestrator.
    
    Args:
        websocket: WebSocket connection
        mode: Session mode ("voice" or "text")
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted (mode: {mode})")
    
    session_id: Optional[str] = None
    authenticated = False
    
    try:
        # Wait for start_session message
        message = await websocket.receive_json()
        
        if message.get("type") != "start_session":
            await websocket.send_json({
                "type": "error",
                "code": 400,
                "message": "First message must be 'start_session'"
            })
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
        
        # Authenticate
        authenticated = await authenticate_websocket(websocket, message)
        if not authenticated:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Get or generate session ID
        session_id = message.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated session ID: {session_id}")
        else:
            logger.info(f"Using provided session ID: {session_id}")
        
        metadata = message.get("metadata", {})
        metadata["mode"] = mode
        
        # Route to appropriate orchestrator
        if mode == "voice":
            orchestrator = VoiceOrchestrator()
        elif mode == "text":
            orchestrator = TextOrchestrator()
        else:
            await websocket.send_json({
                "type": "error",
                "code": 400,
                "message": f"Invalid mode: {mode}. Must be 'voice' or 'text'"
            })
            await websocket.close()
            return
        
        # Handle session
        await orchestrator.handle_session(websocket, session_id, metadata)
    
    except WebSocketException as e:
        logger.warning(f"WebSocket exception: {e}")
        try:
            await websocket.close(code=e.code)
        except:
            pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            })
            await websocket.close()
        except:
            pass
    finally:
        logger.info(f"WebSocket connection closed (session: {session_id})")

