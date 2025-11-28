"""
Voice orchestrator for handling voice input flow.
"""
import asyncio
import contextlib
import io
import wave
from typing import Dict, Any, Optional, TYPE_CHECKING, List
from fastapi import WebSocket
from app.orchestrators.base import BaseOrchestrator, ClientDisconnectedError
from app.services.redis_client import redis_client
from app.core.utils import (
    audio_chunk_to_pcm16,
    base64_to_audio_bytes,
    combine_audio_chunks,
    validate_session_id
)
from app.core.config import settings
from app.logging_config import get_logger
from app.services.asr_stream_client import StreamingASRUnavailable

if TYPE_CHECKING:
    from app.services.asr_stream_client import StreamingASRSession

logger = get_logger(__name__)


class VoiceOrchestrator(BaseOrchestrator):
    """Orchestrator for voice mode: Audio → ASR → RAG → TTS → Audio."""
    
    async def handle_session(self, websocket: WebSocket, session_id: str, metadata: Dict[str, Any]):
        """
        Handle voice session.
        
        Flow:
        1. Receive audio chunks
        2. On end_stream, combine chunks and send to ASR
        3. Send transcript to client
        4. Stream RAG response
        5. Synthesize TTS and send audio chunks
        """
        if not validate_session_id(session_id):
            await self.send_error(websocket, 400, "Invalid session ID format")
            return
        
        # Initialize session state
        await redis_client.set_session_state(session_id, {
            "mode": "voice",
            "metadata": metadata,
            "audio_chunks": {},
            "stage": "collecting_audio"
        })
        
        audio_chunks: Dict[int, bytes] = {}
        max_seq = -1
        language = metadata.get("lang", "ar")
        sample_rate = int(metadata.get("sample_rate", 16000) or 16000)
        additional_messages: Optional[str] = None
        streaming_session: Optional["StreamingASRSession"] = None
        streaming_listener_task: Optional[asyncio.Task] = None
        streaming_transcript_future: Optional[asyncio.Future] = None
        streaming_transcript_text: Optional[str] = None
        streaming_pcm_bytes = 0
        
        try:
            # Attempt to start streaming ASR if available
            if self.asr_stream_client.is_enabled:
                try:
                    streaming_session = await self.asr_stream_client.create_session(
                        language_code="ar-EG" if language.startswith("ar") else language,
                        sample_rate=sample_rate,
                        encoding="LINEAR16"
                    )
                    streaming_transcript_future = asyncio.get_running_loop().create_future()
                    streaming_listener_task = asyncio.create_task(
                        self._relay_streaming_transcripts(
                            websocket,
                            session_id,
                            streaming_session,
                            streaming_transcript_future
                        )
                    )
                    logger.info("Streaming ASR enabled for session %s", session_id)
                except StreamingASRUnavailable as exc:
                    logger.warning("Streaming ASR unavailable: %s", exc)
                except Exception as exc:
                    logger.error("Failed to initialize streaming ASR: %s", exc)
                    streaming_session = None
                    if streaming_listener_task:
                        streaming_listener_task.cancel()
                        streaming_listener_task = None
                        streaming_transcript_future = None
            
            # Phase 1: Collect audio chunks
            logger.info(f"Voice session {session_id} started, collecting audio chunks")
            
            while True:
                try:
                    # Receive message
                    message = await websocket.receive_json()
                    msg_type = message.get("type")
                    
                    if msg_type == "audio_chunk":
                        seq = message.get("seq")
                        audio_base64 = message.get("audio_base64")
                        
                        if seq is None or not audio_base64:
                            await self.send_error(websocket, 400, "Missing seq or audio_base64 in audio_chunk")
                            continue
                        
                        # Decode and store chunk
                        try:
                            audio_bytes = base64_to_audio_bytes(audio_base64)
                            audio_chunks[seq] = audio_bytes
                            max_seq = max(max_seq, seq)
                            
                            # Store in Redis for persistence
                            await redis_client.add_audio_chunk(session_id, seq, audio_bytes)
                            
                            logger.debug(f"Received audio chunk {seq} ({len(audio_bytes)} bytes)")

                            if streaming_session and streaming_transcript_future and not streaming_transcript_future.done():
                                try:
                                    pcm_bytes = await self._convert_chunk_for_streaming(audio_bytes, sample_rate)
                                    if pcm_bytes:
                                        streaming_pcm_bytes += len(pcm_bytes)
                                        await streaming_session.send_audio(pcm_bytes)
                                except Exception as exc:
                                    logger.error("Failed to forward chunk %s to streaming ASR: %s", seq, exc)
                                    if streaming_transcript_future and not streaming_transcript_future.done():
                                        streaming_transcript_future.set_exception(exc)
                                    if streaming_session:
                                        await streaming_session.close()
                                    streaming_session = None
                            
                            # Check buffer size
                            total_size = sum(len(chunk) for chunk in audio_chunks.values())
                            if total_size > settings.max_audio_buffer_size:
                                await self.send_error(websocket, 413, "Audio buffer size exceeded")
                                break
                        
                        except Exception as e:
                            logger.error(f"Error processing audio chunk {seq}: {e}")
                            await self.send_error(websocket, 400, f"Invalid audio chunk: {str(e)}")
                            continue
                    
                    elif msg_type == "end_stream":
                        # Capture additional_messages if provided
                        additional_messages = message.get("additional_messages")
                        if additional_messages:
                            logger.info(f"End stream received with additional_messages: {len(additional_messages)} chars")
                        else:
                            logger.info(f"End stream received, processing {len(audio_chunks)} audio chunks")
                        break
                    
                    elif msg_type == "start_session":
                        # Ignore duplicate start_session
                        continue
                    
                    else:
                        logger.warning(f"Unexpected message type in voice mode: {msg_type}")
                        await self.send_error(websocket, 400, f"Unexpected message type: {msg_type}")
                
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    await self.send_error(websocket, 500, f"Error processing message: {str(e)}")
                    break
            
            # Phase 2: Collect transcript (prefer streaming)
            if not audio_chunks:
                await self.send_error(websocket, 400, "No audio chunks received")
                await self._close_session(websocket, session_id, "no_audio")
                return

            # Await streaming transcript if enabled
            transcript: Optional[str] = None
            duration_seconds: float = 0.0
            if streaming_transcript_future:
                try:
                    streaming_transcript_text = await asyncio.wait_for(
                        streaming_transcript_future,
                        timeout=settings.asr_streaming_result_timeout
                    )
                    if streaming_transcript_text:
                        transcript = streaming_transcript_text.strip()
                        if streaming_pcm_bytes and sample_rate:
                            duration_seconds = streaming_pcm_bytes / float(2 * sample_rate)
                except Exception as exc:
                    logger.warning("Streaming ASR transcript unavailable: %s", exc)
                    streaming_transcript_text = None

            # Fallback to batch ASR if needed
            if streaming_transcript_text and duration_seconds > settings.max_asr_audio_duration:
                warning_msg = (
                    f"Recording too long ({duration_seconds:.1f}s). "
                    f"Limit is {settings.max_asr_audio_duration}s."
                )
                logger.warning("Session %s %s", session_id, warning_msg)
                await self.send_error(
                    websocket,
                    413,
                    warning_msg,
                    error_type="audio_too_long"
                )
                await self._close_session(websocket, session_id, "audio_too_long")
                return

            combined_audio: Optional[bytes] = None
            if not transcript:
                # Sort chunks by sequence number
                sorted_chunks = [audio_chunks[i] for i in sorted(audio_chunks.keys())]
                try:
                    combined_audio = combine_audio_chunks(sorted_chunks, format="webm", target_format="wav")
                    duration_seconds = self._get_wav_duration_seconds(combined_audio)
                    logger.info(
                        "Combined %d chunks into %d bytes (converted to WAV, %.2fs)",
                        len(sorted_chunks),
                        len(combined_audio),
                        duration_seconds
                    )
                except Exception as e:
                    logger.error(f"Error combining audio chunks: {e}")
                    await self.send_error(websocket, 500, f"Failed to combine audio: {str(e)}")
                    await self._close_session(websocket, session_id, "audio_processing_error")
                    return

                if duration_seconds > settings.max_asr_audio_duration:
                    warning_msg = (
                        f"Recording too long ({duration_seconds:.1f}s). "
                        f"Limit is {settings.max_asr_audio_duration}s."
                    )
                    logger.warning("Session %s %s", session_id, warning_msg)
                    await self.send_error(
                        websocket,
                        413,
                        warning_msg,
                        error_type="audio_too_long"
                    )
                    await self._close_session(websocket, session_id, "audio_too_long")
                    return

                # Update state
                await redis_client.set_session_state(session_id, {
                    "mode": "voice",
                    "stage": "transcribing"
                })

                try:
                    asr_result = await self.asr_client.transcribe(combined_audio, audio_format="wav")
                    transcript = asr_result.get("transcript", "")
                    confidence = asr_result.get("confidence", 0.0)
                    logger.info(f"ASR transcript: {transcript[:100]}... (confidence: {confidence})")
                except ClientDisconnectedError:
                    logger.info("Client disconnected before receiving transcript for session %s", session_id)
                    await self._close_session(websocket, session_id, "client_disconnected")
                    return
                except Exception as e:
                    logger.error(f"ASR transcription failed: {e}")
                    await self.send_error(websocket, 500, f"ASR transcription failed: {str(e)}")
                    await self._close_session(websocket, session_id, "asr_error")
                    return
            else:
                logger.info("Using streaming ASR transcript for session %s", session_id)
                # Update state even when streaming succeeds
                await redis_client.set_session_state(session_id, {
                    "mode": "voice",
                    "stage": "transcribing"
                })

            if additional_messages and transcript:
                combined_transcript = f"{transcript}\n{additional_messages}"
                logger.info(
                    "Combined transcript with additional_messages: %d chars total",
                    len(combined_transcript)
                )
                transcript = combined_transcript

            if transcript and not streaming_transcript_text:
                # Streaming relay already pushed final transcripts; avoid duplicates
                await self._send_json_safe(
                    websocket,
                    {
                        "type": "transcript",
                        "session_id": session_id,
                        "text": transcript,
                        "is_final": True
                    },
                    context="sending ASR transcript"
                )

            if not transcript:
                await self.send_error(websocket, 400, "Empty transcript from ASR")
                await self._close_session(websocket, session_id, "empty_transcript")
                return
            
            # Phase 3: Send to RAG and stream response
            await redis_client.set_session_state(session_id, {
                "mode": "voice",
                "stage": "rag_processing"
            })
            
            try:
                full_text, tts_sentences = await self.send_rag_chunks(websocket, session_id, transcript)
                
                if not full_text:
                    await self.send_error(websocket, 500, "Empty response from RAG")
                    await self._close_session(websocket, session_id, "empty_rag_response")
                    return
                
            except ClientDisconnectedError:
                logger.info("Client disconnected before RAG response for session %s", session_id)
                await self._close_session(websocket, session_id, "client_disconnected")
                return
            except Exception as e:
                logger.error(f"RAG processing failed: {e}")
                await self._close_session(websocket, session_id, "rag_error")
                return
            
            # Phase 4: Synthesize TTS and send audio chunks
            await redis_client.set_session_state(session_id, {
                "mode": "voice",
                "stage": "tts_processing"
            })
            
            try:
                await self.send_tts_audio(
                    websocket,
                    session_id,
                    full_text,
                    language=language,
                    sentences=tts_sentences
                )
            except Exception as e:
                logger.error(f"TTS processing failed: {e}")
                # Don't fail completely, just log the error
            
            # Phase 5: Close session
            await self._close_session(websocket, session_id, "completed")
            
        except Exception as e:
            logger.error(f"Voice session error: {e}", exc_info=True)
            await self.send_error(websocket, 500, f"Session error: {str(e)}")
            await self._close_session(websocket, session_id, "error")
        
        finally:
            # Cleanup
            if streaming_listener_task:
                streaming_listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await streaming_listener_task
            if streaming_session:
                await streaming_session.close()
            await redis_client.clear_audio_chunks(session_id)
    
    async def _close_session(self, websocket: WebSocket, session_id: str, reason: str):
        """Close session and send closure message."""
        try:
            await self._send_json_safe(
                websocket,
                {
                    "type": "session_closed",
                    "session_id": session_id,
                    "reason": reason
                },
                context="closing session",
                raise_on_disconnect=False
            )
            await redis_client.delete_session_state(session_id)
            logger.info(f"Session {session_id} closed: {reason}")
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    async def _convert_chunk_for_streaming(self, audio_bytes: bytes, sample_rate: int) -> bytes:
        """Convert compressed chunk into raw PCM suitable for streaming ASR."""
        return await asyncio.to_thread(audio_chunk_to_pcm16, audio_bytes, "webm", sample_rate)

    async def _relay_streaming_transcripts(
        self,
        websocket: WebSocket,
        session_id: str,
        streaming_session: "StreamingASRSession",
        transcript_future: Optional[asyncio.Future]
    ):
        """Forward streaming ASR events to the client and store final transcript."""
        final_segments: List[str] = []
        try:
            async for event in streaming_session:
                if not event:
                    continue
                event_type = event.get("type")
                if event_type == "metadata":
                    continue
                if event_type == "transcript":
                    text = event.get("text", "")
                    is_final = bool(event.get("is_final"))
                    if text:
                        await self._send_json_safe(
                            websocket,
                            {
                                "type": "transcript",
                                "session_id": session_id,
                                "text": text,
                                "is_final": is_final
                            },
                            context="streaming ASR transcript",
                            raise_on_disconnect=False
                        )
                    if is_final and text.strip():
                        final_segments.append(text.strip())
                elif event_type == "complete":
                    logger.info("Streaming ASR completed for session %s", session_id)
                    break
                elif event_type == "error":
                    detail = event.get("detail") or event.get("message") or "Streaming ASR error"
                    raise StreamingASRUnavailable(detail)
        except ClientDisconnectedError:
            logger.info("Client disconnected during streaming ASR for session %s", session_id)
            raise
        except Exception as exc:
            logger.error("Streaming ASR listener error for session %s: %s", session_id, exc)
            if transcript_future and not transcript_future.done():
                transcript_future.set_exception(exc)
        else:
            final_text = " ".join(final_segments).strip()
            if transcript_future and not transcript_future.done():
                transcript_future.set_result(final_text)
        finally:
            await streaming_session.close()

    def _get_wav_duration_seconds(self, audio_bytes: bytes) -> float:
        """Return duration of WAV audio bytes in seconds."""
        if not audio_bytes:
            return 0.0
        try:
            with contextlib.closing(wave.open(io.BytesIO(audio_bytes), "rb")) as wav_file:
                frames = wav_file.getnframes()
                frame_rate = wav_file.getframerate()
                if frame_rate <= 0:
                    return 0.0
                return frames / float(frame_rate)
        except wave.Error as exc:
            logger.error(f"Unable to determine WAV duration: {exc}")
            return 0.0

