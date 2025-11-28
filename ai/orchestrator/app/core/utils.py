"""
Utility functions for the orchestrator.
"""
import base64
import io
import re
from typing import List
from pydub import AudioSegment  # type: ignore
from app.logging_config import get_logger

logger = get_logger(__name__)


def base64_to_audio_bytes(base64_audio: str) -> bytes:
    """
    Convert base64 encoded audio to bytes.
    
    Args:
        base64_audio: Base64 encoded audio string
        
    Returns:
        Audio bytes
    """
    return base64.b64decode(base64_audio)


def audio_bytes_to_base64(audio_bytes: bytes) -> str:
    """
    Convert audio bytes to base64 encoded string.
    
    Args:
        audio_bytes: Audio bytes
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(audio_bytes).decode("utf-8")


def combine_audio_chunks(chunks: List[bytes], format: str = "webm", target_format: str = "wav") -> bytes:
    """
    Combine multiple audio chunks into a single audio file and convert to target format.
    
    Args:
        chunks: List of audio chunk bytes
        format: Source audio format (webm, wav, mp3)
        target_format: Target audio format (wav, mp3). Default: wav for ASR compatibility
        
    Returns:
        Combined and converted audio bytes
    """
    if not chunks:
        raise ValueError("No audio chunks provided")
    
    try:
        # Combine chunks
        if len(chunks) == 1:
            combined_bytes = chunks[0]
        else:
            # Simple concatenation for same format chunks
            combined_bytes = b"".join(chunks)
        
        # Convert to target format if needed
        if format.lower() != target_format.lower():
            logger.info(f"Converting audio from {format} to {target_format}")
            
            # Load audio from bytes
            audio_segment = AudioSegment.from_file(
                io.BytesIO(combined_bytes),
                format=format.lower()
            )
            
            # Convert to 16-bit PCM WAV (required by ASR API)
            if target_format.lower() == "wav":
                # Export as 16-bit PCM WAV, mono, 16kHz (common ASR requirements)
                output = io.BytesIO()
                # Normalize audio: mono, 16kHz, 16-bit
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio_segment.export(output, format="wav")
                combined_bytes = output.getvalue()
                logger.info(f"Converted audio to 16-bit PCM WAV: {len(combined_bytes)} bytes")
            else:
                # Export in target format
                output = io.BytesIO()
                audio_segment.export(output, format=target_format.lower())
                combined_bytes = output.getvalue()
        
        return combined_bytes
    
    except Exception as e:
        logger.error(f"Error combining/converting audio chunks: {e}")
        # Fallback to simple concatenation if conversion fails
        logger.warning("Falling back to simple concatenation")
        return b"".join(chunks)


def audio_chunk_to_pcm16(
    audio_bytes: bytes,
    source_format: str = "webm",
    target_sample_rate: int = 16000
) -> bytes:
    """
    Convert a single compressed chunk (e.g. WebM) to raw 16-bit PCM data.

    Args:
        audio_bytes: Encoded audio chunk bytes
        source_format: Source encoding (default: webm)
        target_sample_rate: Output sample rate (default: 16 kHz)

    Returns:
        Raw PCM bytes suitable for streaming ASR services.
    """
    if not audio_bytes:
        return b""
    try:
        audio_segment = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format=source_format.lower()
        )
        audio_segment = audio_segment.set_frame_rate(target_sample_rate).set_channels(1).set_sample_width(2)
        return audio_segment.raw_data
    except Exception as exc:
        logger.error("Failed to convert chunk to PCM16: %s", exc)
        raise


def split_into_sentences(text: str, language: str = "ar") -> List[str]:
    """
    Split text into sentences for TTS pseudo-streaming.
    
    Args:
        text: Full text to split
        language: Language code (ar for Arabic)
        
    Returns:
        List of sentences
    """
    if not text or not text.strip():
        return []
    
    # Arabic sentence delimiters
    if language == "ar":
        # Arabic punctuation: period, question mark, exclamation, semicolon
        # Also handle Arabic-specific punctuation
        sentences = re.split(r'[.!?؛]\s+', text)
    else:
        # Default: English punctuation
        sentences = re.split(r'[.!?]\s+', text)
    
    # Filter out empty sentences and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # If no sentence delimiters found, split by commas or return as single sentence
    if len(sentences) == 1 and len(text) > 200:
        # Long text without sentence breaks - split by commas
        sentences = re.split(r'[،,]\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
    
    # Ensure we have at least one sentence
    if not sentences:
        sentences = [text.strip()]
    
    return sentences


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not session_id:
        return False
    
    # UUID format or alphanumeric with dashes/underscores
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, session_id, re.IGNORECASE):
        return True
    
    # Alphanumeric with dashes/underscores, 8-64 chars
    if re.match(r'^[a-zA-Z0-9_-]{8,64}$', session_id):
        return True
    
    return False


def format_error_message(error: Exception, code: int = 500) -> dict:
    """
    Format error message for WebSocket response.
    
    Args:
        error: Exception object
        code: HTTP status code
        
    Returns:
        Formatted error dictionary
    """
    return {
        "type": "error",
        "code": code,
        "message": str(error),
        "error_type": type(error).__name__
    }


EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)


def sanitize_rag_text(text: str) -> str:
    """
    Remove markdown, special formatting and emoji characters from RAG output.
    """
    if not text:
        return ""
    
    cleaned = text
    # Remove fenced code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    # Remove inline code ticks
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    # Remove markdown links/images
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    # Remove headings and block quotes
    cleaned = re.sub(r"^\s{0,3}(#{1,6}|>|\d+\.)\s*", "", cleaned, flags=re.MULTILINE)
    # Remove bullet markers
    cleaned = re.sub(r"^\s{0,3}[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    # Remove emphasis markers
    cleaned = re.sub(r"[_*~]+", "", cleaned)
    # Remove emojis
    cleaned = EMOJI_PATTERN.sub("", cleaned)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    return cleaned.strip()


def normalize_tts_text(text: str) -> str:
    """
    Prepare text for TTS by spacing out special symbols and removing artifacts
    that can cause the TTS provider to truncate audio (e.g., consecutive slashes).
    """
    if not text:
        return ""
    
    normalized = text
    normalized = normalized.replace("/", " / ")
    normalized = normalized.replace("\\", " ")
    normalized = normalized.replace("|", " ")
    normalized = normalized.replace(":", " : ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

