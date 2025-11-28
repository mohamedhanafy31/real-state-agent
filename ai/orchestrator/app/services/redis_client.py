"""
Redis client for state management and message queuing.
"""
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Redis client for session state management."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self._connection_pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=False,  # We'll handle encoding/decoding manually
                max_connections=50
            )
            self.redis = redis.Redis(connection_pool=self._connection_pool)
            # Test connection
            await self.redis.ping()
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.redis = None
            self._connection_pool = None
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
        if self._connection_pool:
            try:
                await self._connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting Redis pool: {e}")
        if self.redis or self._connection_pool:
            logger.info("Disconnected from Redis")
    
    def _session_key(self, session_id: str) -> str:
        """Generate session state key."""
        return f"session:{session_id}"
    
    def _audio_chunks_key(self, session_id: str) -> str:
        """Generate audio chunks key."""
        return f"audio_chunks:{session_id}"
    
    async def set_session_state(self, session_id: str, state: Dict[str, Any], ttl: int = 3600):
        """
        Set session state in Redis.
        
        Args:
            session_id: Session identifier
            state: State dictionary
            ttl: Time to live in seconds
        """
        if not self.redis:
            logger.debug("Redis not connected, skipping session state storage")
            return
        
        key = self._session_key(session_id)
        await self.redis.setex(
            key,
            ttl,
            json.dumps(state, ensure_ascii=False)
        )
    
    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session state from Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            State dictionary or None if not found
        """
        if not self.redis:
            logger.debug("Redis not connected, returning None for session state")
            return None
        
        key = self._session_key(session_id)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def delete_session_state(self, session_id: str):
        """
        Delete session state from Redis.
        
        Args:
            session_id: Session identifier
        """
        if not self.redis:
            logger.debug("Redis not connected, skipping session state deletion")
            return
        
        key = self._session_key(session_id)
        await self.redis.delete(key)
    
    async def add_audio_chunk(self, session_id: str, seq: int, chunk: bytes):
        """
        Add audio chunk to Redis list.
        
        Args:
            session_id: Session identifier
            seq: Sequence number
            chunk: Audio chunk bytes
        """
        if not self.redis:
            logger.debug("Redis not connected, skipping audio chunk storage")
            return
        
        key = self._audio_chunks_key(session_id)
        # Store as hash: seq -> chunk (base64 encoded)
        chunk_b64 = chunk.hex()  # Use hex encoding for binary data
        await self.redis.hset(key, str(seq), chunk_b64)
        await self.redis.expire(key, settings.audio_chunk_timeout)
    
    async def get_audio_chunks(self, session_id: str) -> List[bytes]:
        """
        Get all audio chunks for a session, sorted by sequence number.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of audio chunks in sequence order
        """
        if not self.redis:
            logger.debug("Redis not connected, returning empty audio chunks list")
            return []
        
        key = self._audio_chunks_key(session_id)
        chunks_dict = await self.redis.hgetall(key)
        
        if not chunks_dict:
            return []
        
        # Sort by sequence number and decode
        chunks = []
        for seq in sorted(chunks_dict.keys(), key=int):
            chunk_hex = chunks_dict[seq]
            chunk = bytes.fromhex(chunk_hex.decode() if isinstance(chunk_hex, bytes) else chunk_hex)
            chunks.append(chunk)
        
        return chunks
    
    async def clear_audio_chunks(self, session_id: str):
        """
        Clear all audio chunks for a session.
        
        Args:
            session_id: Session identifier
        """
        if not self.redis:
            logger.debug("Redis not connected, skipping audio chunks clearing")
            return
        
        key = self._audio_chunks_key(session_id)
        await self.redis.delete(key)


# Global Redis client instance
redis_client = RedisClient()

