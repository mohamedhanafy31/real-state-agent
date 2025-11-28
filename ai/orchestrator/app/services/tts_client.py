"""
TTS (Arabic Text-to-Speech) service client.
"""
import httpx
from typing import Optional
from app.core.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class TTSClient:
    """Client for TTS API service."""
    
    def __init__(self):
        self.base_url = settings.tts_api_url.rstrip("/")
        self.timeout = settings.tts_timeout
    
    async def synthesize(
        self,
        text: str,
        audio_encoding: str = "MP3",
        voice_used: str | None = "ar-EG-Standard-A"
    ) -> bytes:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            audio_encoding: Audio encoding format (MP3, WAV, etc.)
            
        Returns:
            Audio bytes (MP3 format)
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.base_url}/tts"
        
        payload = {
            "text": text,
            "audio_encoding": audio_encoding
        }
        if voice_used:
            payload["voice_used"] = voice_used
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Sending TTS request: {text[:50]}... voice={voice_used or 'default'}")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # TTS API returns binary MP3 data
                audio_bytes = response.content
                logger.info(f"TTS synthesis completed: {len(audio_bytes)} bytes")
                return audio_bytes
                
        except httpx.TimeoutException:
            logger.error(f"TTS API timeout after {self.timeout}s")
            raise Exception(f"TTS service timeout after {self.timeout} seconds")
        except httpx.HTTPStatusError as e:
            logger.error(f"TTS API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"TTS service error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"TTS API request failed: {e}")
            raise

