"""
TTS (Arabic Text-to-Speech) service client.
"""
import asyncio
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
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
    
    async def synthesize(
        self,
        text: str,
        audio_encoding: str = "MP3",
        voice_used: str | None = "ar-EG-Standard-A"
    ) -> bytes:
        """
        Synthesize text to speech with retry logic for transient failures.
        
        Args:
            text: Text to synthesize
            audio_encoding: Audio encoding format (MP3, WAV, etc.)
            
        Returns:
            Audio bytes (MP3 format)
            
        Raises:
            Exception: If API request fails after retries
        """
        url = f"{self.base_url}/tts"
        
        payload = {
            "text": text,
            "audio_encoding": audio_encoding
        }
        if voice_used:
            payload["voice_used"] = voice_used
        
        safe_text = text.replace("\n", " ").strip()
        last_exception = None
        
        # Retry logic for transient DNS/network failures
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if attempt == 1:
                        logger.info(
                            "Sending TTS request (voice=%s, chars=%d): %s",
                            voice_used or "default",
                            len(safe_text),
                            safe_text,
                        )
                    else:
                        logger.warning(
                            "Retrying TTS request (attempt %d/%d): %s",
                            attempt, self.max_retries, safe_text[:50]
                        )
                    
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    
                    # TTS API returns binary MP3 data
                    audio_bytes = response.content
                    if attempt > 1:
                        logger.info(
                            "TTS request succeeded on retry %d: %d bytes",
                            attempt, len(audio_bytes)
                        )
                    else:
                        logger.info(f"TTS synthesis completed: {len(audio_bytes)} bytes")
                    return audio_bytes
                    
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = e
                error_str = str(e)
                
                # Check if it's a DNS resolution error
                is_dns_error = (
                    "name resolution" in error_str.lower() or
                    "temporary failure" in error_str.lower() or
                    "errno -3" in error_str.lower() or
                    isinstance(e, (httpx.ConnectError, httpx.NetworkError))
                )
                
                if attempt < self.max_retries and is_dns_error:
                    logger.warning(
                        "TTS request failed (attempt %d/%d) with DNS/network error: %s. Retrying in %.1fs...",
                        attempt, self.max_retries, error_str, self.retry_delay
                    )
                    await asyncio.sleep(self.retry_delay)
                    # Exponential backoff for subsequent retries
                    self.retry_delay *= 1.5
                    continue
                else:
                    # Not a retryable error or max retries reached
                    if isinstance(e, httpx.TimeoutException):
                        logger.error(f"TTS API timeout after {self.timeout}s (attempt {attempt}/{self.max_retries})")
                        raise Exception(f"TTS service timeout after {self.timeout} seconds")
                    else:
                        logger.error(f"TTS API network error (attempt {attempt}/{self.max_retries}): {error_str}")
                        raise Exception(f"TTS service network error: {error_str}")
                    
            except httpx.HTTPStatusError as e:
                # HTTP errors (4xx, 5xx) are not retryable
                logger.error(f"TTS API error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"TTS service error: {e.response.status_code}")
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if it's a DNS resolution error
                is_dns_error = (
                    "name resolution" in error_str.lower() or
                    "temporary failure" in error_str.lower() or
                    "errno -3" in error_str.lower()
                )
                
                if attempt < self.max_retries and is_dns_error:
                    logger.warning(
                        "TTS request failed (attempt %d/%d) with DNS error: %s. Retrying in %.1fs...",
                        attempt, self.max_retries, error_str, self.retry_delay
                    )
                    await asyncio.sleep(self.retry_delay)
                    self.retry_delay *= 1.5
                    continue
                else:
                    logger.error(f"TTS API request failed (attempt {attempt}/{self.max_retries}): {error_str}")
                    raise
        
        # If we get here, all retries failed
        if last_exception:
            raise Exception(f"TTS service failed after {self.max_retries} attempts: {str(last_exception)}")
        else:
            raise Exception(f"TTS service failed after {self.max_retries} attempts")

