"""
ASR (Arabic Speech Recognition) service client.
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class ASRClient:
    """Client for ASR API service."""
    
    def __init__(self):
        self.base_url = settings.asr_api_url.rstrip("/")
        self.timeout = settings.asr_timeout
    
    async def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str = "webm"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text.
        
        Args:
            audio_bytes: Audio file bytes
            audio_format: Audio format (webm, wav, mp3)
            
        Returns:
            Dictionary with transcript, confidence, and words
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.base_url}/asr"
        
        # Determine content type
        content_type_map = {
            "webm": "audio/webm",
            "wav": "audio/wav",
            "mp3": "audio/mpeg"
        }
        content_type = content_type_map.get(audio_format.lower(), "audio/webm")
        
        files = {
            "file": (f"audio.{audio_format}", audio_bytes, content_type)
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Sending audio to ASR API: {len(audio_bytes)} bytes, format: {audio_format}")
                response = await client.post(url, files=files)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"ASR transcription completed: {result.get('transcript', '')[:50]}...")
                return result
                
        except httpx.TimeoutException:
            logger.error(f"ASR API timeout after {self.timeout}s")
            raise Exception(f"ASR service timeout after {self.timeout} seconds")
        except httpx.HTTPStatusError as e:
            logger.error(f"ASR API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"ASR service error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"ASR API request failed: {e}")
            raise

