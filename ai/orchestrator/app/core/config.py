"""
Configuration management for the orchestrator.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service URLs
    asr_api_url: str = os.getenv(
        "ASR_API_URL",
        "https://arabic-asr-api-22251281831.us-central1.run.app"
    )
    asr_streaming_ws_url: Optional[str] = os.getenv(
        "ASR_STREAMING_WS_URL",
        None
    )
    rag_api_url: str = os.getenv("RAG_API_URL", "http://localhost:8000")
    tts_api_url: str = os.getenv(
        "TTS_API_URL",
        "https://arabic-tts-api-22251281831.us-central1.run.app"
    )
    
    # Redis Configuration
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    
    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8040"))
    
    # Authentication
    jwt_secret: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    static_client_token: Optional[str] = os.getenv("STATIC_CLIENT_TOKEN", None)
    service_api_key: Optional[str] = os.getenv("SERVICE_API_KEY", None)
    client_token_ttl_seconds: int = int(os.getenv("CLIENT_TOKEN_TTL_SECONDS", "300"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")
    log_dir: str = os.getenv("LOG_DIR", "logs")
    
    # Limits
    max_audio_buffer_size: int = int(os.getenv("MAX_AUDIO_BUFFER_SIZE", "10485760"))  # 10MB
    max_session_duration: int = int(os.getenv("MAX_SESSION_DURATION", "3600"))  # 1 hour
    audio_chunk_timeout: int = int(os.getenv("AUDIO_CHUNK_TIMEOUT", "30"))  # seconds
    
    # API Timeouts
    asr_timeout: int = int(os.getenv("ASR_TIMEOUT", "30"))
    asr_streaming_connect_timeout: int = int(os.getenv("ASR_STREAMING_CONNECT_TIMEOUT", "10"))
    asr_streaming_result_timeout: int = int(os.getenv("ASR_STREAMING_RESULT_TIMEOUT", "15"))
    rag_timeout: int = int(os.getenv("RAG_TIMEOUT", "60"))
    tts_timeout: int = int(os.getenv("TTS_TIMEOUT", "30"))
    max_asr_audio_duration: int = int(os.getenv("MAX_ASR_AUDIO_DURATION", "20"))  # seconds
    
    # Retry Configuration
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_backoff_factor: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "1.5"))
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

