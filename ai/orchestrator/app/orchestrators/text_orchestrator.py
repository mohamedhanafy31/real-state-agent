"""
Text orchestrator for handling text input flow.
"""
from typing import Dict, Any
from fastapi import WebSocket
from app.orchestrators.base import BaseOrchestrator
from app.services.redis_client import redis_client
from app.core.utils import validate_session_id
from app.logging_config import get_logger

logger = get_logger(__name__)


class TextOrchestrator(BaseOrchestrator):
    """Orchestrator for text mode: Text → RAG → TTS → Audio."""
    
    async def handle_session(self, websocket: WebSocket, session_id: str, metadata: Dict[str, Any]):
        """
        Handle text session.
        
        Flow:
        1. Receive text message
        2. Stream RAG response
        3. Synthesize TTS and send audio chunks
        """
        if not validate_session_id(session_id):
            await self.send_error(websocket, 400, "Invalid session ID format")
            return
        
        # Initialize session state
        await redis_client.set_session_state(session_id, {
            "mode": "text",
            "metadata": metadata,
            "stage": "waiting_for_text"
        })
        
        language = metadata.get("lang", "ar")
        
        try:
            # Wait for text message
            logger.info(f"Text session {session_id} started, waiting for text message")
            
            text_received = False
            while not text_received:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")
                    
                    if msg_type == "text_message":
                        text = message.get("text", "").strip()
                        
                        if not text:
                            await self.send_error(websocket, 400, "Empty text message")
                            continue
                        
                        text_received = True
                        logger.info(f"Received text message: {text[:100]}...")
                        
                        # Phase 1: Send to RAG and stream response
                        await redis_client.set_session_state(session_id, {
                            "mode": "text",
                            "stage": "rag_processing"
                        })
                        
                        try:
                            full_text, tts_sentences = await self.send_rag_chunks(websocket, session_id, text)
                            
                            if not full_text:
                                await self.send_error(websocket, 500, "Empty response from RAG")
                                await self._close_session(websocket, session_id, "empty_rag_response")
                                return
                            
                        except Exception as e:
                            logger.error(f"RAG processing failed: {e}")
                            await self._close_session(websocket, session_id, "rag_error")
                            return
                        
                        # Phase 2: Synthesize TTS and send audio chunks
                        await redis_client.set_session_state(session_id, {
                            "mode": "text",
                            "stage": "tts_processing"
                        })
                        
                        tts_success = False
                        try:
                            tts_success = await self.send_tts_audio(
                                websocket,
                                session_id,
                                full_text,
                                language=language,
                                sentences=tts_sentences
                            )
                        except Exception as e:
                            logger.error(f"TTS processing failed: {e}")
                            tts_success = False
                        
                        # Phase 3: Close session
                        # Use different reason if TTS completely failed
                        close_reason = "completed" if tts_success else "tts_error"
                        await self._close_session(websocket, session_id, close_reason)
                        break
                    
                    elif msg_type == "start_session":
                        # Ignore duplicate start_session
                        continue
                    
                    elif msg_type == "end_stream":
                        # In text mode, end_stream can be used to close without processing
                        await self._close_session(websocket, session_id, "cancelled")
                        break
                    
                    else:
                        logger.warning(f"Unexpected message type in text mode: {msg_type}")
                        await self.send_error(websocket, 400, f"Unexpected message type: {msg_type}")
                
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    await self.send_error(websocket, 500, f"Error processing message: {str(e)}")
                    break
            
            if not text_received:
                await self._close_session(websocket, session_id, "no_text")
        
        except Exception as e:
            logger.error(f"Text session error: {e}", exc_info=True)
            await self.send_error(websocket, 500, f"Session error: {str(e)}")
            await self._close_session(websocket, session_id, "error")
        
        finally:
            # Cleanup
            await redis_client.delete_session_state(session_id)
    
    async def _close_session(self, websocket: WebSocket, session_id: str, reason: str):
        """Close session and send closure message."""
        try:
            await websocket.send_json({
                "type": "session_closed",
                "session_id": session_id,
                "reason": reason
            })
            await redis_client.delete_session_state(session_id)
            logger.info(f"Session {session_id} closed: {reason}")
        except Exception as e:
            logger.error(f"Error closing session: {e}")

