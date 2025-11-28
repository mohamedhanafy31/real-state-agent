"""
Streaming ASR client that bridges the orchestrator with the Google Cloud backed
ASR WebSocket endpoint. Provides incremental transcripts while audio chunks are
still being uploaded.
"""
import asyncio
import json
from collections import deque
from typing import Any, Deque, Dict, Optional

import websockets
from websockets import ConnectionClosed
from websockets.client import WebSocketClientProtocol

from app.core.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class StreamingASRUnavailable(Exception):
    """Raised when the streaming ASR endpoint is unreachable or disabled."""


class StreamingASRSession:
    """
    Wraps a single streaming ASR WebSocket connection.

    Responsible for sending configuration, relaying audio chunks and yielding
    server events (metadata + transcripts).
    """

    def __init__(
        self,
        websocket: WebSocketClientProtocol,
        language_code: str,
        sample_rate: int,
        encoding: str,
    ):
        self._ws = websocket
        self._language_code = language_code
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._pending_events: Deque[Dict[str, Any]] = deque()
        self._ready = asyncio.Event()
        self._closed = False

    async def initialize(self):
        """Send configuration payload and wait for ready metadata."""
        await self._send_json(
            {
                "language_code": self._language_code,
                "sample_rate_hertz": self._sample_rate,
                "encoding": self._encoding,
                "enable_interim_results": True,
            }
        )
        await self._wait_for_ready()

    async def _wait_for_ready(self):
        while not self._ready.is_set():
            data = await self._recv_json()
            if data is None:
                raise StreamingASRUnavailable("Streaming ASR connection closed before ready.")
            if data.get("type") == "metadata" and data.get("status") == "ready":
                logger.info("Streaming ASR session ready (lang=%s, sr=%s)", self._language_code, self._sample_rate)
                self._ready.set()
                break
            self._pending_events.append(data)

    async def send_audio(self, pcm_bytes: bytes):
        """Send raw PCM16 audio bytes to the ASR stream."""
        if self._closed or not pcm_bytes:
            return
        await self._ws.send(pcm_bytes)

    async def close(self):
        """Close the underlying WebSocket gracefully."""
        if self._closed:
            return
        self._closed = True
        try:
            await self._ws.close()
        except ConnectionClosed:
            pass

    async def _send_json(self, payload: Dict[str, Any]):
        await self._ws.send(json.dumps(payload))

    async def _recv_json(self) -> Optional[Dict[str, Any]]:
        try:
            frame = await self._ws.recv()
        except ConnectionClosed:
            return None

        if isinstance(frame, bytes):
            logger.debug("Streaming ASR session received unexpected binary frame (%d bytes)", len(frame))
            return None

        try:
            return json.loads(frame)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON from streaming ASR: %s", exc)
            return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._pending_events:
            return self._pending_events.popleft()

        data = await self._recv_json()
        if data is None:
            raise StopAsyncIteration
        return data


class StreamingASRClient:
    """Factory for creating streaming ASR sessions."""

    def __init__(self):
        self._ws_url = settings.asr_streaming_ws_url
        self._connect_timeout = settings.asr_streaming_connect_timeout
        self._max_ws_message = settings.max_audio_buffer_size * 2

    @property
    def is_enabled(self) -> bool:
        return bool(self._ws_url)

    async def create_session(
        self,
        *,
        language_code: str,
        sample_rate: int = 16000,
        encoding: str = "LINEAR16",
    ) -> StreamingASRSession:
        if not self.is_enabled:
            raise StreamingASRUnavailable("Streaming ASR disabled.")

        try:
            ws = await asyncio.wait_for(
                websockets.connect(
                    self._ws_url,
                    max_size=self._max_ws_message,
                    ping_interval=None,
                    ping_timeout=None,
                ),
                timeout=self._connect_timeout,
            )
        except Exception as exc:
            logger.error("Failed to connect to streaming ASR: %s", exc)
            raise StreamingASRUnavailable(str(exc)) from exc

        session = StreamingASRSession(ws, language_code, sample_rate, encoding)
        try:
            await asyncio.wait_for(session.initialize(), timeout=self._connect_timeout)
        except Exception as exc:
            await session.close()
            logger.error("Failed to initialize streaming ASR session: %s", exc)
            raise StreamingASRUnavailable(str(exc)) from exc
        return session

