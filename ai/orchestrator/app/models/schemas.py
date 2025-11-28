"""
Pydantic models for WebSocket messages and API requests.
"""
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# Client → Orchestrator Messages

class StartSessionMessage(BaseModel):
    """Start session message from client."""
    type: Literal["start_session"]
    session_id: str = Field(..., description="Unique session identifier")
    auth: Optional[str] = Field(None, description="Bearer token for authentication")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Session metadata (lang, sample_rate, etc.)"
    )


class AudioChunkMessage(BaseModel):
    """Audio chunk message from client."""
    type: Literal["audio_chunk"]
    seq: int = Field(..., description="Sequence number of the chunk")
    audio_base64: str = Field(..., description="Base64 encoded audio data")
    timestamp: Optional[float] = Field(None, description="Timestamp of the chunk")


class TextMessage(BaseModel):
    """Text message from client."""
    type: Literal["text_message"]
    text: str = Field(..., description="Text input from user")


class EndStreamMessage(BaseModel):
    """End stream message from client."""
    type: Literal["end_stream"]
    additional_messages: Optional[str] = Field(
        None,
        description="Optional additional messages to append to the transcribed text (added as new line)"
    )


# Orchestrator → Client Messages

class TranscriptMessage(BaseModel):
    """Transcript message to client."""
    type: Literal["transcript"]
    session_id: str
    text: str
    is_final: bool = Field(default=True, description="Whether this is the final transcript")


class RAGChunkMessage(BaseModel):
    """RAG chunk message to client."""
    type: Literal["rag_chunk"]
    session_id: str
    chunk: str
    is_last: bool = Field(default=False, description="Whether this is the last chunk")


class TTSAudioMessage(BaseModel):
    """TTS audio chunk message to client."""
    type: Literal["tts_audio"]
    seq: int = Field(..., description="Sequence number of the audio chunk")
    audio_base64: str = Field(..., description="Base64 encoded MP3 audio")
    format: str = Field(default="mp3", description="Audio format")
    is_last: bool = Field(default=False, description="Whether this is the last audio chunk")


class ErrorMessage(BaseModel):
    """Error message to client."""
    type: Literal["error"]
    code: int
    message: str
    error_type: Optional[str] = None


class SessionClosedMessage(BaseModel):
    """Session closed message to client."""
    type: Literal["session_closed"]
    session_id: str
    reason: str = Field(..., description="Reason for session closure")


# Union type for client messages (for validation)
ClientMessage = StartSessionMessage | AudioChunkMessage | TextMessage | EndStreamMessage

