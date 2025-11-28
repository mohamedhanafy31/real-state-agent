"""
Base orchestrator class.
"""
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, Any, Optional, List, Tuple, Deque
from fastapi import WebSocket
from app.services.asr_client import ASRClient
from app.services.rag_client import RAGClient
from app.services.tts_client import TTSClient
from app.services.redis_client import redis_client
from app.services.asr_stream_client import StreamingASRClient
from app.core.utils import (
    split_into_sentences,
    audio_bytes_to_base64,
    sanitize_rag_text,
    normalize_tts_text
)
from app.logging_config import get_logger
from websockets.exceptions import ConnectionClosed

logger = get_logger(__name__)
DEFAULT_TTS_VOICE = "ar-EG-Standard-A"


class ClientDisconnectedError(Exception):
    """Raised when the client WebSocket has already closed."""
    pass


class BaseOrchestrator(ABC):
    """Base class for orchestrators."""
    
    def __init__(self):
        self.asr_client = ASRClient()
        self.rag_client = RAGClient()
        self.tts_client = TTSClient()
        self.asr_stream_client = StreamingASRClient()
    
    @abstractmethod
    async def handle_session(self, websocket: WebSocket, session_id: str, metadata: Dict[str, Any]):
        """
        Handle a session.
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
            metadata: Session metadata
        """
        pass
    
    async def _send_json_safe(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        context: str,
        raise_on_disconnect: bool = True
    ) -> bool:
        """
        Send JSON payload but swallow client disconnects.
        Returns True when send succeeds, False when client is already gone (and raise_on_disconnect=False).
        """
        try:
            await websocket.send_json(payload)
            return True
        except ConnectionClosed as exc:
            logger.info("WebSocket closed while %s: %s", context, exc)
        except RuntimeError as exc:
            # Starlette raises RuntimeError when the socket is already closed.
            if "WebSocket" in str(exc):
                logger.info("WebSocket runtime error while %s: %s", context, exc)
            else:
                raise

        if raise_on_disconnect:
            raise ClientDisconnectedError(f"Client disconnected during {context}")
        return False

    async def send_error(self, websocket: WebSocket, code: int, message: str, error_type: Optional[str] = None):
        """Send error message to client."""
        await self._send_json_safe(
            websocket,
            {
                "type": "error",
                "code": code,
                "message": message,
                "error_type": error_type
            },
            context="sending error response",
            raise_on_disconnect=False
        )
    
    async def send_rag_chunks(self, websocket: WebSocket, session_id: str, question: str, retrieval_k: int = 5) -> Tuple[str, List[str]]:
        """
        Stream RAG response chunks to client.
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
            question: User question
            retrieval_k: Number of chunks to retrieve
            
        Returns:
            Tuple of (full sanitized text, list of sanitized sentences for TTS)
        """
        logger.info("Streaming RAG response for session %s", session_id)
        clean_chunks: List[str] = []
        fallback_text = ""
        try:
            async for event in self.rag_client.query_stream(
                question=question,
                session_id=session_id,
                retrieval_k=retrieval_k
            ):
                event_type = event.get("type")
                
                if event_type == "metadata":
                    metadata_payload = {k: v for k, v in event.items() if k != "type"}
                    logger.debug("Session %s metadata event: %s", session_id, metadata_payload.keys())
                    await self._send_json_safe(
                        websocket,
                        {
                            "type": "rag_metadata",
                            "session_id": session_id,
                            **metadata_payload
                        },
                        context="sending RAG metadata"
                    )
                
                elif event_type == "chunk":
                    chunk_text = event.get("text", "")
                    cleaned_chunk = sanitize_rag_text(chunk_text)
                    if cleaned_chunk:
                        clean_chunks.append(cleaned_chunk)
                        logger.debug(
                            "Session %s streaming chunk (%d chars)", session_id, len(cleaned_chunk)
                        )
                    await self._send_json_safe(
                        websocket,
                        {
                            "type": "rag_chunk",
                            "session_id": session_id,
                            "chunk": cleaned_chunk if cleaned_chunk else "",
                            "is_last": False
                        },
                        context="streaming RAG chunk"
                    )
                
                elif event_type == "done":
                    raw_full_text = event.get("full_text")
                    if raw_full_text:
                        fallback_text = sanitize_rag_text(raw_full_text)
                    logger.info(
                        "Session %s received RAG completion (clean_chunks=%d fallback=%s)",
                        session_id, len(clean_chunks), bool(fallback_text)
                    )
                    # Send final marker
                    await self._send_json_safe(
                        websocket,
                        {
                            "type": "rag_chunk",
                            "session_id": session_id,
                            "chunk": "",
                            "is_last": True
                        },
                        context="signaling end of RAG stream"
                    )
                    break
                
                elif event_type == "error":
                    error_msg = event.get("message", "Unknown error")
                    await self.send_error(websocket, 500, f"RAG service error: {error_msg}")
                    raise Exception(error_msg)
        
        except ClientDisconnectedError:
            logger.info("Client disconnected while streaming RAG response for session %s", session_id)
            raise
        except Exception as e:
            logger.error(f"Error streaming RAG response: {e}")
            await self.send_error(websocket, 500, f"Failed to get RAG response: {str(e)}")
            raise
        
        full_text = fallback_text or " ".join(clean_chunks).strip()
        tts_sentences = split_into_sentences(full_text, language="ar") if full_text else []
        logger.info(
            "Session %s sanitized full text length=%d, sentences=%d",
            session_id, len(full_text), len(tts_sentences)
        )
        return full_text, tts_sentences
    
    async def send_tts_audio(
        self,
        websocket: WebSocket,
        session_id: str,
        text: str,
        language: str = "ar",
        sentences: Optional[List[str]] = None,
    ) -> bool:
        """
        Synthesize text to speech and send audio chunks to client.
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
            text: Text to synthesize
            language: Language code
            sentences: Optional pre-split sentences
            
        Returns:
            True if at least one audio chunk was successfully sent, False otherwise
        """
        if sentences is None:
            sentences = split_into_sentences(text, language=language)
        logger.info("Session %s TTS sentences=%d", session_id, len(sentences))
        
        tts_queue: Deque[Dict[str, Any]] = deque()
        preferred_voice = DEFAULT_TTS_VOICE
        successful_chunks = 0
        failed_chunks = 0
        
        try:
            for i, sentence in enumerate(sentences):
                try:
                    tts_input = normalize_tts_text(sentence)
                    if not tts_input:
                        logger.debug("Session %s skipping empty TTS sentence index=%d", session_id, i)
                        continue
                    audio_bytes = await self.tts_client.synthesize(
                        text=tts_input,
                        voice_used=preferred_voice
                    )
                    tts_queue.append({
                        "seq": i,
                        "audio_base64": audio_bytes_to_base64(audio_bytes),
                        "format": "mp3",
                        "is_last": i == len(sentences) - 1
                    })
                    
                    logger.debug(
                        "Session %s queued TTS chunk seq=%d size=%d queue_len=%d",
                        session_id, i, len(audio_bytes), len(tts_queue)
                    )
                    await self._send_json_safe(
                        websocket,
                        {
                            "type": "tts_queue_update",
                            "session_id": session_id,
                            "queued": len(tts_queue),
                            "next_seq": tts_queue[0]["seq"],
                            "voice_used": preferred_voice
                        },
                        context="sending TTS queue update"
                    )
                    
                    await self._drain_tts_queue(websocket, session_id, tts_queue, preferred_voice)
                    successful_chunks += 1
                    logger.debug(f"Queued TTS audio chunk {i+1}/{len(sentences)}")
                
                except Exception as e:
                    failed_chunks += 1
                    logger.error(f"Error synthesizing sentence {i+1}/{len(sentences)}: {e}")
                    await self.send_error(websocket, 500, f"TTS synthesis failed: {str(e)}")
                    continue
            
            # Log summary
            if successful_chunks == 0 and failed_chunks > 0:
                logger.warning(
                    "Session %s TTS completely failed: %d sentences failed, 0 succeeded",
                    session_id, failed_chunks
                )
            elif failed_chunks > 0:
                logger.warning(
                    "Session %s TTS partial failure: %d succeeded, %d failed",
                    session_id, successful_chunks, failed_chunks
                )
            
            return successful_chunks > 0
            
        except ClientDisconnectedError:
            logger.info("Client disconnected during TTS streaming for session %s", session_id)
            return successful_chunks > 0

    async def _drain_tts_queue(
        self,
        websocket: WebSocket,
        session_id: str,
        queue: Deque[Dict[str, Any]],
        voice_used: str
    ):
        while queue:
            chunk = queue.popleft()
            logger.debug(
                "Session %s sending TTS chunk seq=%d remaining=%d",
                session_id, chunk["seq"], len(queue)
            )
            await self._send_json_safe(
                websocket,
                {
                    "type": "tts_audio",
                    "session_id": session_id,
                    "seq": chunk["seq"],
                    "chunk_index": chunk["seq"],
                    "audio_base64": chunk["audio_base64"],
                    "audio_data": chunk["audio_base64"],
                    "format": chunk["format"],
                    "is_last": chunk["is_last"],
                    "is_final_chunk": chunk["is_last"],
                    "voice_used": voice_used
                },
                context="sending TTS audio chunk"
            )

