"""
RAG service client with SSE streaming support.
"""
import json
from typing import AsyncIterator, Dict, Any, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class RAGServiceError(Exception):
    """Custom exception for RAG service errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RAGClient:
    """Client for RAG API service with streaming support."""
    
    def __init__(self):
        rag_url = settings.rag_api_url.strip() if settings.rag_api_url else ""
        if not rag_url:
            raise ValueError("RAG_API_URL environment variable is not set or is empty")
        if not rag_url.startswith(("http://", "https://")):
            raise ValueError(
                f"RAG_API_URL must start with 'http://' or 'https://'. "
                f"Got: {rag_url[:50] if len(rag_url) > 50 else rag_url}"
            )
        self.base_url = rag_url.rstrip("/")
        self.timeout = settings.rag_timeout
        logger.info(f"RAGClient initialized with base_url: {self.base_url}")

    async def _request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Perform JSON HTTP requests against the RAG API."""
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            message = f"RAG service timeout after {self.timeout}s"
            logger.error(message)
            raise RAGServiceError(message, status_code=504) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body_snippet = exc.response.text[:500]
            message = f"RAG service responded with {status_code}: {body_snippet}"
            logger.error(message)
            raise RAGServiceError(message, status_code=status_code) from exc
        except httpx.RequestError as exc:
            message = f"Failed to reach RAG service: {exc}"
            logger.error(message)
            raise RAGServiceError(message, status_code=502) from exc

    async def list_documents(self) -> Dict[str, Any]:
        """Fetch the document list from the RAG API."""
        return await self._request_json("GET", "/documents")

    async def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str],
        rebuild_index: bool = True
    ) -> Dict[str, Any]:
        """Upload or overwrite a document in the RAG API."""
        files = {
            "file": (
                filename,
                content,
                content_type or "application/octet-stream",
            )
        }
        params = {"rebuild_index": "true" if rebuild_index else "false"}
        return await self._request_json(
            "POST",
            "/documents/upload",
            params=params,
            files=files,
        )

    async def delete_document(
        self,
        *,
        filename: str,
        remove_from_index: bool = True
    ) -> Dict[str, Any]:
        """Delete a document by name."""
        safe_name = quote(filename, safe="")
        params = {"remove_from_index": "true" if remove_from_index else "false"}
        return await self._request_json(
            "DELETE",
            f"/documents/{safe_name}",
            params=params,
        )

    async def clear_documents(
        self,
        *,
        clear_index: bool = True
    ) -> Dict[str, Any]:
        """Remove all documents (and optionally the FAISS index)."""
        params = {"clear_index": "true" if clear_index else "false"}
        return await self._request_json(
            "DELETE",
            "/documents",
            params=params,
        )
    
    async def query_stream(
        self,
        question: str,
        session_id: str,
        retrieval_k: int = 5,
        temperature: float = 0.7
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Query RAG service with streaming response.
        
        Args:
            question: User question
            session_id: Session identifier
            retrieval_k: Number of chunks to retrieve
            temperature: Generation temperature
            
        Yields:
            Dictionary with type and text/chunk data
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.base_url}/query/stream"
        
        payload = {
            "question": question,
            "session_id": session_id,
            "retrieval_k": retrieval_k,
            "temperature": temperature
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Starting RAG stream query: {question[:50]}...")
                
                async with client.stream("POST", url, json=payload) as response:
                    # Check status before reading stream
                    if response.status_code >= 400:
                        # For error responses, try to read the error message from the stream
                        error_body = ""
                        try:
                            async for line in response.aiter_lines():
                                error_body += line + "\n"
                                if len(error_body) > 1000:  # Limit error body size
                                    break
                        except Exception:
                            pass
                        
                        error_msg = error_body.strip()[:500] if error_body else f"HTTP {response.status_code}"
                        logger.error(f"RAG API error: {response.status_code} - {error_msg}")
                        raise Exception(f"RAG service error: {response.status_code} - {error_msg}")
                    
                    full_text = ""
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        # Parse SSE format: "data: {...}"
                        if line.startswith("data: "):
                            try:
                                data_str = line[6:]  # Remove "data: " prefix
                                data = json.loads(data_str)
                                
                                event_type = data.get("type")
                                
                                if event_type == "metadata":
                                    # Forward structured metadata (e.g., units with images)
                                    yield {
                                        "type": "metadata",
                                        **{k: v for k, v in data.items() if k != "type"}
                                    }
                                
                                elif event_type == "chunk":
                                    chunk_text = data.get("text", "")
                                    full_text += chunk_text
                                    yield {
                                        "type": "chunk",
                                        "text": chunk_text
                                    }
                                
                                elif event_type == "done":
                                    full_text = data.get("full_text", full_text)
                                    yield {
                                        "type": "done",
                                        "full_text": full_text
                                    }
                                    logger.info(f"RAG stream completed: {len(full_text)} chars")
                                    break
                                
                                elif event_type == "error":
                                    error_msg = data.get("message", "Unknown error")
                                    logger.error(f"RAG stream error: {error_msg}")
                                    yield {
                                        "type": "error",
                                        "message": error_msg
                                    }
                                    break
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE line: {line[:100]} - {e}")
                                continue
                
        except httpx.TimeoutException:
            logger.error(f"RAG API timeout after {self.timeout}s")
            raise Exception(f"RAG service timeout after {self.timeout} seconds")
        except httpx.HTTPStatusError as e:
            # This should not happen since we check status_code above, but handle it anyway
            error_detail = f"status {e.response.status_code}"
            try:
                # Try to read error response if it's not a streaming response
                if not hasattr(e.response, 'is_stream_consumed') or not e.response.is_stream_consumed:
                    error_detail = f"status {e.response.status_code}: {e.response.text[:500]}"
            except Exception:
                pass
            logger.error(f"RAG API error: {error_detail}")
            raise Exception(f"RAG service error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"RAG API request failed: {e}")
            raise Exception(f"Failed to reach RAG service: {e}")
        except Exception as e:
            logger.error(f"RAG API request failed: {e}")
            raise

