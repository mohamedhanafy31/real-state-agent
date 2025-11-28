"""
FastAPI Server for RAG System
Provides REST API endpoints for querying the RAG system.
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File, Query, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from the project root (ai/rag/)
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✓ Loaded environment variables from {env_path}")
    else:
        # Try loading from current directory
        load_dotenv()
except ImportError:
    print("⚠ python-dotenv not installed. Install it with: pip install python-dotenv")
    print("  Environment variables must be set manually.")

from rag_graph.main import run_ingestion, run_query
from src.utils import setup_run_logging, get_logger, get_run_logger, load_config, get_config_value
from src.embeddings import AraModernBERTEmbedder
from src.memory import get_memory

# Setup run-based logging for API
run_logger = setup_run_logging(
    run_name=f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    log_dir=os.getenv('LOG_DIR', 'logs'),
    level=os.getenv('LOG_LEVEL', 'INFO'),
    console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
    file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
)

logger = get_logger(__name__)

# Global embedder instance (loaded at startup)
_embedder: Optional[AraModernBERTEmbedder] = None
_embedding_dim: Optional[int] = None


def load_embedding_model():
    """Load the embedding model at startup."""
    global _embedder, _embedding_dim
    
    if _embedder is not None:
        logger.info("Embedding model already loaded")
        return _embedder
    
    try:
        logger.info("Loading embedding model at startup...")
        logger.info("Note: Model will be downloaded from HuggingFace if not cached (~/.cache/huggingface/hub/)")
        
        # Load config
        config = load_config("config/settings.yaml")
        
        # Get embedding configuration
        model_name = get_config_value(config, 'embedding.model_name', 'mohamed2811/Muffakir_Embedding_V2')
        device = get_config_value(config, 'embedding.device', None)
        batch_size = get_config_value(config, 'embedding.batch_size', 32)
        use_sentence_transformers = get_config_value(config, 'embedding.use_sentence_transformers', True)
        
        # Auto-detect device if not specified
        if device is None:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Check if model is cached before loading
        from pathlib import Path
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_cache_path = cache_dir / f"models--{model_name.replace('/', '--')}"
        is_cached = model_cache_path.exists() and any(model_cache_path.iterdir())
        
        if is_cached:
            logger.info(f"✓ Model found in cache: {model_cache_path}")
            logger.info("  Will load from cache (fast, no download)")
        else:
            logger.info(f"⚠ Model not found in cache")
            logger.info(f"  Will download from HuggingFace (first time only)")
            logger.info(f"  Cache location: {cache_dir}")
            logger.info(f"  This may take several minutes - please wait...")
        
        logger.info(f"Initializing embedder: model={model_name}, device={device}, batch_size={batch_size}")
        
        # Load embedder (this will download and load the model if not cached)
        _embedder = AraModernBERTEmbedder(
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            use_sentence_transformers=use_sentence_transformers
        )
        
        # Get embedding dimension
        _embedding_dim = _embedder.get_embedding_dim()
        
        if is_cached:
            logger.info(f"✓ Embedding model loaded from cache (dimension: {_embedding_dim})")
        else:
            logger.info(f"✓ Embedding model downloaded and loaded (dimension: {_embedding_dim})")
        
        return _embedder
    
    except Exception as e:
        logger.error(f"Failed to load embedding model: {str(e)}", exc_info=True)
        logger.warning("Embedding model will be loaded on-demand for queries")
        return None


def get_embedder() -> Optional[AraModernBERTEmbedder]:
    """Get the global embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = load_embedding_model()
    return _embedder


# Log API startup information
run_logger.log_run_info({
    'run_name': run_logger.run_name,
    'start_time': datetime.now().isoformat(),
    'log_directory': str(run_logger.log_dir.absolute()),
    'api_version': '1.0.0'
})

# Suppress watchfiles logging
import logging
logging.getLogger('watchfiles').setLevel(logging.WARNING)
logging.getLogger('watchfiles.main').setLevel(logging.WARNING)
logging.getLogger('watchdog').setLevel(logging.WARNING)

# Startup and shutdown events
def validate_gemini_api_key() -> tuple[bool, Optional[str]]:
    """
    Validate that Gemini API key is set and optionally test it.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        return False, "GEMINI_API_KEY environment variable is not set"
    
    if not api_key.strip():
        return False, "GEMINI_API_KEY is set but empty"
    
    # Optional: Test the API key by trying to initialize the client
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Try to list models (lightweight check)
        # Note: This might make an API call, so we'll just check if it's configured
        logger.info("✓ Gemini API key is set and appears valid")
        return True, None
    except ImportError:
        logger.warning("⚠ google-generativeai not installed - cannot validate API key")
        return True, None  # Assume valid if package not installed
    except Exception as e:
        logger.warning(f"⚠ Could not validate Gemini API key: {str(e)}")
        # Still return True as the key is set, validation might fail for other reasons
        return True, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - load resources at startup."""
    # Startup
    logger.info("="*60)
    logger.info("API Startup - Loading resources...")
    logger.info("="*60)
    
    # Check Gemini API key
    api_key_valid, api_key_error = validate_gemini_api_key()
    if api_key_valid:
        logger.info("✓ Gemini API key is configured")
    else:
        logger.error(f"✗ Gemini API key validation failed: {api_key_error}")
        logger.error("  The /query endpoint will not work without a valid API key")
        logger.error("  Set it with: export GEMINI_API_KEY='your-api-key'")
        logger.error("  Or add it to your .env file")
    
    # Load embedding model
    embedder = load_embedding_model()
    
    if embedder:
        logger.info("✓ Embedding model ready")
    else:
        logger.warning("⚠ Embedding model not loaded - will load on-demand")
    
    logger.info("="*60)
    logger.info("API ready to accept requests")
    logger.info("="*60)
    
    yield
    
    # Shutdown (cleanup if needed)
    logger.info("API shutting down...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="RAG Chatbot API",
    description="Retrieval-Augmented Generation API for Arabic real estate chatbot",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files for the web UI
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Mount images directory for serving unit images
images_path = Path(__file__).parent.parent / "data" / "generated_images"
if not images_path.exists():
    # Try alternative path
    images_path = Path(__file__).parent.parent.parent / "data" / "generated_images"
images_path.mkdir(parents=True, exist_ok=True)
if images_path.exists():
    app.mount("/images", StaticFiles(directory=str(images_path)), name="images")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default paths
DEFAULT_INDEX_PATH = "data/embeddings/index.faiss"
DEFAULT_CHUNKS_PATH = "data/embeddings/chunks.pkl"
DEFAULT_DATA_PATH = "data/raw"


def _normalize_raw_image_url(raw_url: str, request: Request) -> Optional[str]:
    """
    Normalize a raw image URL or path relative to the API host.
    """
    if not raw_url:
        return None
    
    raw_url = raw_url.strip()
    if not raw_url:
        return None
    
    if raw_url.startswith("http://") or raw_url.startswith("https://") or raw_url.startswith("data:"):
        return raw_url
    
    # Treat as relative path
    base_url = str(request.base_url).rstrip('/')
    if raw_url.startswith("/"):
        return f"{base_url}{raw_url}"
    return f"{base_url}/{raw_url}"


def get_image_url(image_path: str, request: Request) -> Optional[str]:
    """
    Convert image path from CSV to full URL.
    
    Args:
        image_path: Image path from CSV (e.g., "generated_images/Hawabay_07_B_7.png")
        request: FastAPI request object to get base URL
        
    Returns:
        Full URL to the image or None if path is invalid
    """
    if not image_path or not isinstance(image_path, str):
        return None
    
    # Extract filename from path (handles both "generated_images/file.png" and "file.png")
    filename = Path(image_path).name
    
    # Verify image exists
    images_dir = Path(__file__).parent.parent / "data" / "generated_images"
    if not images_dir.exists():
        images_dir = Path(__file__).parent.parent.parent / "data" / "generated_images"
    
    image_file = images_dir / filename
    if not image_file.exists():
        logger.warning(f"Image file not found: {image_file}")
        return None
    
    # Build full URL
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/images/{filename}"


def resolve_unit_image_url(unit: Dict[str, Any], request: Request) -> Optional[str]:
    """
    Resolve the best image URL for a structured unit.
    Preference order:
        1. Existing absolute/relative image_url/ImageURL/imageUrl fields
        2. Generated images referenced via ImagePath/image_path/imagePath columns
    """
    if not unit:
        return None
    
    for key in ("image_url", "ImageURL", "imageUrl"):
        raw = unit.get(key)
        normalized = _normalize_raw_image_url(raw, request)
        if normalized:
            return normalized
    
    for key in ("ImagePath", "image_path", "imagePath"):
        raw_path = unit.get(key)
        url = get_image_url(raw_path, request)
        if url:
            return url
    
    return None


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    question: str = Field(..., description="User question in Arabic or English")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    retrieval_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature for generation")
    include_context: bool = Field(False, description="Include retrieved chunks in response")


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    answer: str = Field(..., description="Generated answer")
    question: str = Field(..., description="Original question")
    context_chunks: Optional[List[Dict[str, Any]]] = Field(None, description="Retrieved context chunks")
    num_chunks: int = Field(..., description="Number of chunks used")
    top_score: Optional[float] = Field(None, description="Top similarity score")
    structured_units: Optional[List[Dict[str, Any]]] = Field(None, description="Selected units from CSV")
    num_structured_units: Optional[int] = Field(None, description="Number of structured units selected")
    unit_selector: Optional[Dict[str, Any]] = Field(None, description="Unit selector metadata (code, error, relevance_score)")
    unit_selector_relevance_score: Optional[float] = Field(None, description="Relevance score (0.0-1.0) indicating how well query matches CSV data")


class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint."""
    data_path: str = Field(DEFAULT_DATA_PATH, description="Path to documents directory")
    save_index_path: str = Field(DEFAULT_INDEX_PATH, description="Path to save FAISS index")
    save_chunks_path: str = Field(DEFAULT_CHUNKS_PATH, description="Path to save chunks")
    device: Optional[str] = Field("cuda", description="Device to use (cuda/cpu)")
    chunk_min_size: int = Field(100, description="Minimum chunk size")
    chunk_max_size: int = Field(1000, description="Maximum chunk size")
    chunk_overlap: int = Field(50, description="Chunk overlap size")


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint."""
    status: str = Field(..., description="Status of ingestion")
    message: str = Field(..., description="Status message")
    num_documents: Optional[int] = Field(None, description="Number of documents processed")
    num_chunks: Optional[int] = Field(None, description="Number of chunks created")
    num_embeddings: Optional[int] = Field(None, description="Number of embeddings generated")
    errors: Optional[List[str]] = Field(None, description="List of errors if any")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    index_exists: bool
    chunks_exist: bool
    gemini_api_key_set: bool


class DocumentInfo(BaseModel):
    """Document information model."""
    name: str
    path: str
    size: int
    modified: str


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    documents: List[DocumentInfo]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    status: str
    message: str
    filename: str
    path: str
    size: int


class DocumentInfo(BaseModel):
    """Document information model."""
    name: str
    path: str
    size: int
    modified: str


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    documents: List[DocumentInfo]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    status: str
    message: str
    filename: str
    path: str
    size: int


# Health Check Endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the API and system."""
    index_path = Path(DEFAULT_INDEX_PATH)
    chunks_path = Path(DEFAULT_CHUNKS_PATH)
    
    # Check if both index and chunks exist (both are required for index to be available)
    index_file_exists = index_path.exists()
    chunks_file_exists = chunks_path.exists()
    index_available = index_file_exists and chunks_file_exists
    
    # Validate API key
    api_key = os.getenv('GEMINI_API_KEY')
    api_key_set = bool(api_key and api_key.strip())
    
    return HealthResponse(
        status="healthy",
        index_exists=index_available,  # True only if BOTH files exist
        chunks_exist=chunks_file_exists,  # Keep separate for detailed info
        gemini_api_key_set=api_key_set
    )


@app.get("/health/detailed", response_model=Dict[str, Any])
async def health_detailed():
    """
    Detailed health check endpoint with more information.
    
    Returns:
        Detailed health information including system status
    """
    try:
        # Check if API key is set
        api_key_set = bool(os.getenv('GEMINI_API_KEY'))
        api_key_valid = False
        if api_key_set:
            try:
                from src.generator import LLMGenerator
                generator = LLMGenerator(api_key=os.getenv('GEMINI_API_KEY'))
                api_key_valid = True
            except:
                api_key_valid = False
        
        # Check if index exists
        index_path = Path(DEFAULT_INDEX_PATH)
        chunks_path = Path(DEFAULT_CHUNKS_PATH)
        index_exists = index_path.exists() and chunks_path.exists()
        
        # Get index stats if available
        index_stats = {}
        if index_exists:
            try:
                from src.vector_store import FAISSStore
                vector_store = FAISSStore(embedding_dim=_embedding_dim or 1024)
                vector_store.load(str(index_path), str(chunks_path))
                index_stats = {
                    "num_vectors": vector_store.index.ntotal if vector_store.index else 0,
                    "embedding_dim": _embedding_dim or 1024
                }
            except Exception as e:
                index_stats = {"error": str(e)}
        
        # Check if embedder is loaded
        embedder_loaded = _embedder is not None
        embedder_info = {}
        if embedder_loaded:
            embedder_info = {
                "model_name": _embedder.model_name,
                "device": _embedder.device,
                "embedding_dim": _embedding_dim,
                "is_sentence_transformer": _embedder.is_sentence_transformer
            }
        
        # Get data directory info
        data_path = Path(DEFAULT_DATA_PATH)
        data_info = {
            "exists": data_path.exists(),
            "num_files": len(list(data_path.glob("*"))) if data_path.exists() else 0
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "api_key": {
                "configured": api_key_set,
                "valid": api_key_valid
            },
            "index": {
                "available": index_exists,
                "index_path": str(index_path),
                "chunks_path": str(chunks_path),
                **index_stats
            },
            "embedder": {
                "loaded": embedder_loaded,
                **embedder_info
            },
            "data": data_info,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Error in detailed health check: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detailed health check failed: {str(e)}")


# Middleware to log requests (skip WebSocket collaboration attempts)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests."""
    # Skip logging WebSocket collaboration attempts from IDE extensions
    if "/api/ws/collaboration" in str(request.url.path):
        return await call_next(request)
    
    start_time = datetime.now()
    logger.info(f"Request: {request.method} {request.url.path} from {request.client.host}")
    
    response = await call_next(request)
    
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Response: {response.status_code} - Process time: {process_time:.3f}s")
    
    return response


# Query Endpoint
@app.post("/query/stream")
async def query_stream(request: QueryRequest, http_request: Request):
    """
    Stream query response using Server-Sent Events (SSE).
    
    Args:
        request: Query request containing question and parameters
        
    Returns:
        StreamingResponse with SSE events
    """
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable not set. Please set it to use the query endpoint."
        )
    
    index_path = Path(DEFAULT_INDEX_PATH)
    chunks_path = Path(DEFAULT_CHUNKS_PATH)
    
    if not index_path.exists() or not chunks_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Index not found. Please run ingestion first. Index path: {DEFAULT_INDEX_PATH}"
        )
    
    async def generate_stream():
        try:
            logger.info(f"Processing streaming query: {request.question}")
            
            # Get or create session ID
            session_id = request.session_id or "default"
            
            # Get memory instance
            memory = get_memory(max_messages=20)
            
            # Get conversation history BEFORE adding current message
            # (so we don't include the current question in history)
            conversation_history = memory.get_history_text(session_id, format_for_prompt=True)
            
            # Add user message to history (after getting history for prompt)
            memory.add_message(session_id, 'user', request.question)
            
            embedder = get_embedder()
            embedding_dim = _embedding_dim
            
            # Embed query and retrieve chunks
            from src.vector_store import FAISSStore
            from src.retrieval import Retriever
            import numpy as np
            
            # Embed the query
            query_embedding = embedder.embed(request.question)
            if isinstance(query_embedding, np.ndarray) and query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)
            
            # Load vector store and retrieve chunks
            vector_store = FAISSStore(embedding_dim=embedding_dim)
            vector_store.load(str(index_path), str(chunks_path))
            
            retriever = Retriever(vector_store, embedder)
            
            # Run retrieval and unit selection in parallel
            from concurrent.futures import ThreadPoolExecutor
            from src.selector import UnitSelector
            
            # Get CSV path from config or use default
            config = load_config("config/settings.yaml")
            csv_path = get_config_value(config, 'unit_selector.csv_path', None)
            
            # If not in config, try to find the CSV file
            if not csv_path:
                csv_path = Path("data/11-15_sample25.csv")
                if not csv_path.exists():
                    # Try relative to API file
                    csv_path = Path(__file__).parent.parent / "data" / "11-15_sample25.csv"
                    if not csv_path.exists():
                        # Try in parent directory
                        csv_path = Path(__file__).parent.parent.parent / "data" / "11-15_sample25.csv"
            
            csv_path = str(csv_path) if isinstance(csv_path, Path) else csv_path
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                retrieval_future = executor.submit(retriever.retrieve, request.question, request.retrieval_k)
                selector_future = executor.submit(
                    lambda: UnitSelector(
                        csv_path=csv_path,
                        api_key=os.getenv('GEMINI_API_KEY'),
                        model_name=get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
                    ).select_units(request.question)
                )
                
                results = retrieval_future.result()
                selector_result = selector_future.result()
            
            if not results:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No context found'})}\n\n"
                return
            
            # Get context texts
            context_texts = [r['chunk'] for r in results]
            
            # Get structured units from selector and add image URLs
            structured_units_raw = selector_result.rows if selector_result and selector_result.success else []
            relevance_score = selector_result.relevance_score if selector_result else None
            
            structured_units = []
            for unit in structured_units_raw:
                unit_with_image = unit.copy()
                image_url = resolve_unit_image_url(unit, http_request)
                if image_url:
                    unit_with_image['image_url'] = image_url
                structured_units.append(unit_with_image)
            
            # Initialize generator for streaming
            from src.generator import LLMGenerator
            generator = LLMGenerator(
                api_key=os.getenv('GEMINI_API_KEY'),
                model_name=get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
            )
            
            # Send metadata
            metadata = {
                'type': 'metadata',
                'num_chunks': len(context_texts),
                'top_score': results[0]['score'] if results else None,
                'session_id': session_id,
                'num_structured_units': len(structured_units),
                'structured_units': structured_units  # Include units with image URLs
            }
            if selector_result:
                metadata['unit_selector'] = {
                    'code': selector_result.code,
                    'error': selector_result.error
                }
                if selector_result.relevance_score is not None:
                    metadata['unit_selector_relevance_score'] = selector_result.relevance_score
            
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Stream the response
            full_text = ""
            for chunk in generator.generate_stream(
                prompt=request.question,
                context=context_texts,
                structured_data=structured_units,
                conversation_history=conversation_history if conversation_history else None,
                temperature=request.temperature
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            
            # Add assistant response to history
            memory.add_message(session_id, 'assistant', full_text)
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done', 'full_text': full_text, 'session_id': session_id})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming query: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request):
    """
    Query the RAG system with a question.
    
    Args:
        request: Query request containing question and parameters
        
    Returns:
        QueryResponse with generated answer and context
    """
    # Check if API key is set
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable not set. Please set it to use the query endpoint."
        )
    
    # Check if index exists
    index_path = Path(DEFAULT_INDEX_PATH)
    chunks_path = Path(DEFAULT_CHUNKS_PATH)
    
    if not index_path.exists() or not chunks_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Index not found. Please run ingestion first. Index path: {DEFAULT_INDEX_PATH}"
        )
    
    try:
        logger.info(f"Processing query: {request.question}")
        
        # Get or create session ID
        session_id = request.session_id or "default"
        
        # Get memory instance
        memory = get_memory(max_messages=20)
        
        # Get conversation history BEFORE adding current message
        # (so we don't include the current question in history)
        conversation_history = memory.get_history_text(session_id, format_for_prompt=True)
        
        # Add user message to history (after getting history for prompt)
        memory.add_message(session_id, 'user', request.question)
        
        # Get preloaded embedder and embedding dimension
        embedder = get_embedder()
        embedding_dim = _embedding_dim
        
        # Run query with preloaded embedder
        # Note: run_query doesn't support conversation_history yet, so we'll use direct generator
        from src.vector_store import FAISSStore
        from src.retrieval import Retriever
        from src.generator import LLMGenerator
        import numpy as np
        
        # Load vector store and retrieve chunks
        vector_store = FAISSStore(embedding_dim=embedding_dim)
        vector_store.load(str(index_path), str(chunks_path))
        
        retriever = Retriever(vector_store, embedder)
        
        # Run retrieval and unit selection in parallel
        from concurrent.futures import ThreadPoolExecutor
        from src.selector import UnitSelector
        
        # Get CSV path from config or use default
        config = load_config("config/settings.yaml")
        csv_path = get_config_value(config, 'unit_selector.csv_path', None)
        
        # If not in config, try to find the CSV file
        if not csv_path:
            csv_path = Path("data/11-15_sample25.csv")
            if not csv_path.exists():
                # Try relative to API file
                csv_path = Path(__file__).parent.parent / "data" / "11-15_sample25.csv"
                if not csv_path.exists():
                    # Try in parent directory
                    csv_path = Path(__file__).parent.parent.parent / "data" / "11-15_sample25.csv"
        
        csv_path = str(csv_path) if isinstance(csv_path, Path) else csv_path
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            retrieval_future = executor.submit(retriever.retrieve, request.question, request.retrieval_k)
            selector_future = executor.submit(
                lambda: UnitSelector(
                    csv_path=csv_path,
                    api_key=os.getenv('GEMINI_API_KEY'),
                    model_name=get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
                ).select_units(request.question)
            )
            
            results = retrieval_future.result()
            selector_result = selector_future.result()
        
        if not results:
            raise HTTPException(status_code=404, detail="No context found")
        
        context_texts = [r['chunk'] for r in results]
        
        # Get structured units from selector and add image URLs
        structured_units_raw = selector_result.rows if selector_result and selector_result.success else []
        
        # Check relevance score - only add images if score >= 0.5 (50%)
        relevance_score = selector_result.relevance_score if selector_result else None
        include_images = relevance_score is None or relevance_score >= 0.5
        
        # Add image URLs to structured units (only if relevance score is high enough)
        structured_units = []
        for unit in structured_units_raw:
            unit_with_image = unit.copy()
            # Only add image URL if relevance score is >= 0.5
            if include_images:
                image_path = unit.get('ImagePath') or unit.get('image_path') or unit.get('imagePath')
                if image_path:
                    image_url = get_image_url(image_path, http_request)
                    if image_url:
                        unit_with_image['image_url'] = image_url
            structured_units.append(unit_with_image)
        
        # Generate answer with conversation history and structured units
        generator = LLMGenerator(
            api_key=os.getenv('GEMINI_API_KEY'),
            model_name=get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
        )
        
        answer_text = generator.generate(
            prompt=request.question,
            context=context_texts,
            structured_data=structured_units,
            conversation_history=conversation_history if conversation_history else None,
            temperature=request.temperature
        )
        
        # Add assistant response to history
        memory.add_message(session_id, 'assistant', answer_text)
        
        # Create answer object
        from rag_graph.schemas import Answer, RetrievedChunk, Chunk
        retrieved_chunks = [
            RetrievedChunk(
                chunk=Chunk(text=r['chunk'], metadata=r.get('metadata', {})),
                score=r['score'],
                metadata=r.get('metadata', {})
            )
            for r in results
        ]
        
        answer = Answer(
            text=answer_text,
            context_chunks=retrieved_chunks,
            metadata={'session_id': session_id}
        )
        
        if not answer:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate answer. Check logs for details."
            )
        
        # Prepare response
        response_data = {
            "answer": answer.text,
            "question": request.question,
            "num_chunks": len(answer.context_chunks),
            "top_score": answer.context_chunks[0].score if answer.context_chunks else None
        }
        
        # Include context if requested
        if request.include_context:
            response_data["context_chunks"] = [
                {
                    "text": chunk.chunk.text,
                    "score": chunk.score,
                    "metadata": chunk.chunk.metadata
                }
                for chunk in answer.context_chunks
            ]
        
        # Include structured units if available
        if structured_units:
            response_data["structured_units"] = structured_units
            response_data["num_structured_units"] = len(structured_units)
            if selector_result:
                response_data["unit_selector"] = {
                    "code": selector_result.code,
                    "error": selector_result.error
                }
                if selector_result.relevance_score is not None:
                    response_data["unit_selector_relevance_score"] = selector_result.relevance_score
        
        return QueryResponse(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Ingestion Endpoint
@app.post("/ingest", response_model=IngestionResponse)
async def ingest(request: IngestionRequest, background_tasks: BackgroundTasks):
    """
    Ingest documents and build the RAG index.
    
    This endpoint processes documents, creates chunks, generates embeddings,
    and builds the FAISS index. It can run in the background for large datasets.
    
    Args:
        request: Ingestion request with paths and parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        IngestionResponse with status and statistics
    """
    data_path = Path(request.data_path)
    
    if not data_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Data path does not exist: {request.data_path}"
        )
    
    try:
        logger.info(f"Starting ingestion from: {request.data_path}")
        
        # Run ingestion
        final_state = await run_ingestion(
            data_path=str(data_path),
            save_index_path=request.save_index_path,
            save_chunks_path=request.save_chunks_path,
            device=request.device,
            chunk_min_size=request.chunk_min_size,
            chunk_max_size=request.chunk_max_size,
            chunk_overlap=request.chunk_overlap
        )
        
        # Check for errors
        if final_state.get('errors'):
            return IngestionResponse(
                status="completed_with_errors",
                message="Ingestion completed but with some errors",
                num_documents=len(final_state.get('documents', [])),
                num_chunks=len(final_state.get('chunks', [])),
                num_embeddings=len(final_state.get('embedded_chunks', [])),
                errors=final_state.get('errors')
            )
        
        return IngestionResponse(
            status="success",
            message="Ingestion completed successfully",
            num_documents=len(final_state.get('documents', [])),
            num_chunks=len(final_state.get('chunks', [])),
            num_embeddings=len(final_state.get('embedded_chunks', []))
        )
    
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Document Management Endpoints

@app.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """
    List all documents in the data/raw directory.
    
    Returns:
        List of documents with metadata
    """
    try:
        data_path = Path(DEFAULT_DATA_PATH)
        
        if not data_path.exists():
            return DocumentListResponse(documents=[], total=0)
        
        documents = []
        for file_path in data_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.txt', '.docx', '.md']:
                stat = file_path.stat()
                documents.append(DocumentInfo(
                    name=file_path.name,
                    path=str(file_path.relative_to(data_path)),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                ))
        
        # Sort by modified time (newest first)
        documents.sort(key=lambda x: x.modified, reverse=True)
        
        return DocumentListResponse(documents=documents, total=len(documents))
    
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    rebuild_index: bool = Query(True, description="Automatically rebuild index after upload")
):
    """
    Upload a document to the data/raw directory and optionally rebuild the index.
    
    Args:
        file: Uploaded file
        rebuild_index: If True, automatically rebuild the index after upload
        
    Returns:
        Upload response with file information
    """
    try:
        # Validate file extension
        allowed_extensions = ['.pdf', '.txt', '.docx', '.md']
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Ensure data directory exists
        data_path = Path(DEFAULT_DATA_PATH)
        data_path.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = data_path / file.filename
        content = await file.read()
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        file_size = len(content)
        
        logger.info(f"Document uploaded: {file.filename} ({file_size} bytes)")
        
        # Rebuild index if requested
        index_rebuilt = False
        if rebuild_index:
            try:
                logger.info(f"Rebuilding index after uploading {file.filename}...")
                final_state = await run_ingestion(
                    data_path=str(data_path),
                    save_index_path=DEFAULT_INDEX_PATH,
                    save_chunks_path=DEFAULT_CHUNKS_PATH,
                    device="cuda"  # Use CUDA if available
                )
                
                if final_state.get('errors'):
                    logger.warning(f"Index rebuilt with errors: {final_state.get('errors')}")
                else:
                    index_rebuilt = True
                    logger.info(f"Index rebuilt successfully: {len(final_state.get('chunks', []))} chunks")
            except Exception as e:
                logger.error(f"Error rebuilding index after upload: {str(e)}", exc_info=True)
                # Don't fail the upload if index rebuild fails
                logger.warning("Upload succeeded but index rebuild failed. You can rebuild manually.")
        
        message = "Document uploaded successfully"
        if rebuild_index:
            if index_rebuilt:
                message += " and index rebuilt"
            else:
                message += " (index rebuild attempted but may have issues)"
        
        return DocumentUploadResponse(
            status="success",
            message=message,
            filename=file.filename,
            path=str(file_path.relative_to(data_path)),
            size=file_size
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@app.post("/chat/clear")
async def clear_chat_history(session_id: Optional[str] = None):
    """
    Clear conversation history for a session.
    
    Args:
        session_id: Session ID (defaults to "default")
        
    Returns:
        Success message
    """
    try:
        session_id = session_id or "default"
        memory = get_memory()
        memory.clear_session(session_id)
        
        return {
            "status": "success",
            "message": f"Chat history cleared for session: {session_id}",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error clearing chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing chat history: {str(e)}")


@app.get("/chat/history")
async def get_chat_history(session_id: Optional[str] = None, limit: Optional[int] = None):
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID (defaults to "default")
        limit: Maximum number of messages to return
        
    Returns:
        Conversation history
    """
    try:
        session_id = session_id or "default"
        memory = get_memory()
        history = memory.get_history_dict(session_id)
        
        if limit:
            history = history[-limit:]
        
        return {
            "session_id": session_id,
            "messages": history,
            "total_messages": len(memory.get_history(session_id))
        }
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting chat history: {str(e)}")


# Unit Selector Test Endpoint
class SelectorTestRequest(BaseModel):
    """Request model for selector test endpoint."""
    question: str = Field(..., description="User question in Arabic or English")
    max_rows: int = Field(10, ge=1, le=50, description="Maximum number of units to return")


class SelectorTestResponse(BaseModel):
    """Response model for selector test endpoint."""
    success: bool
    question: str
    code: Optional[str] = None
    num_units: int = 0
    units: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[str] = None
    relevance_score: Optional[float] = Field(None, description="Relevance score (0.0-1.0) indicating how well query matches CSV data")


@app.post("/selector/test", response_model=SelectorTestResponse)
async def test_selector(request: SelectorTestRequest):
    """
    Test the UnitSelector component with a question.
    
    Args:
        request: Selector test request with question and max_rows
        
    Returns:
        SelectorTestResponse with generated code and matching units
    """
    if not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable not set."
        )
    
    try:
        from src.selector import UnitSelector
        from pathlib import Path
        
        # Get CSV path
        csv_path = Path("data/11-15_sample25.csv")
        if not csv_path.exists():
            csv_path = Path(__file__).parent.parent / "data" / "11-15_sample25.csv"
            if not csv_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"CSV file not found. Expected at: data/11-15_sample25.csv"
                )
        
        logger.info(f"Testing selector with question: {request.question}")
        
        # Initialize selector
        selector = UnitSelector(
            csv_path=str(csv_path),
            api_key=os.getenv('GEMINI_API_KEY'),
            model_name="gemini-2.0-flash",
            max_rows=request.max_rows
        )
        
        # Run selector
        result = selector.select_units(request.question)
        
        if result.success:
            return SelectorTestResponse(
                success=True,
                question=request.question,
                code=result.code,
                num_units=len(result.rows),
                units=result.rows,
                raw_response=result.raw_response,
                relevance_score=result.relevance_score
            )
        else:
            return SelectorTestResponse(
                success=False,
                question=request.question,
                code=result.code,
                num_units=0,
                units=[],
                error=result.error,
                raw_response=result.raw_response,
                relevance_score=result.relevance_score
            )
    
    except Exception as e:
        logger.error(f"Error testing selector: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.delete("/documents/{filename}")
async def delete_document(
    filename: str, 
    remove_from_index: bool = Query(True, description="Remove document chunks from FAISS index")
):
    """
    Delete a document from the data/raw directory and optionally remove its chunks from the FAISS index.
    
    Args:
        filename: Name of the file to delete
        remove_from_index: If True, also remove the document's chunks from FAISS index and chunks.pkl
        
    Returns:
        Deletion response
    """
    try:
        # Security: prevent path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = Path(DEFAULT_DATA_PATH) / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        
        chunks_removed = 0
        
        # Remove chunks from index if requested and index exists
        if remove_from_index:
            index_path = Path(DEFAULT_INDEX_PATH)
            chunks_path = Path(DEFAULT_CHUNKS_PATH)
            
            if index_path.exists() and chunks_path.exists():
                try:
                    logger.info(f"Removing chunks for document '{filename}' from index...")
                    
                    # Load the FAISS store
                    from src.vector_store import FAISSStore
                    embedder = get_embedder()
                    if embedder is None:
                        embedder = load_embedding_model()
                    
                    if embedder is None:
                        logger.warning("Could not load embedder, skipping index update")
                    else:
                        embedding_dim = embedder.get_embedding_dim()
                        vector_store = FAISSStore(embedding_dim=embedding_dim)
                        vector_store.load(str(index_path), str(chunks_path))
                        
                        # Find and remove chunks belonging to this document
                        original_chunk_count = len(vector_store.chunks)
                        filtered_chunks = []
                        
                        for chunk in vector_store.chunks:
                            chunk_metadata = chunk.get('metadata', {})
                            chunk_filename = chunk_metadata.get('file_name', '')
                            
                            # Keep chunks that don't belong to the deleted document
                            if chunk_filename != filename:
                                filtered_chunks.append(chunk)
                        
                        chunks_removed = original_chunk_count - len(filtered_chunks)
                        
                        if chunks_removed > 0:
                            logger.info(f"Found {chunks_removed} chunks to remove for document '{filename}'")
                            
                            # Rebuild the index with remaining chunks
                            if filtered_chunks:
                                # Re-embed the remaining chunks
                                texts = [chunk.get('text', '') for chunk in filtered_chunks]
                                logger.info(f"Re-embedding {len(texts)} remaining chunks...")
                                embeddings = embedder.embed(texts)
                                
                                # Create new FAISS store with filtered chunks
                                new_vector_store = FAISSStore(embedding_dim=embedding_dim)
                                new_vector_store.add(embeddings, filtered_chunks)
                                
                                # Save the updated index and chunks
                                new_vector_store.save(str(index_path), str(chunks_path))
                                logger.info(f"Updated index: removed {chunks_removed} chunks, {len(filtered_chunks)} chunks remaining")
                            else:
                                # No chunks left, remove index files
                                index_path.unlink(missing_ok=True)
                                chunks_path.unlink(missing_ok=True)
                                logger.info("No chunks remaining, removed index files")
                        else:
                            logger.info(f"No chunks found for document '{filename}' in index")
                
                except Exception as e:
                    logger.error(f"Error removing chunks from index: {str(e)}", exc_info=True)
                    # Continue with file deletion even if index update fails
                    logger.warning("File will still be deleted, but index may contain stale chunks")
        
        # Delete file
        file_path.unlink()
        
        logger.info(f"Document deleted: {filename}")
        
        response = {
            "status": "success",
            "message": f"Document '{filename}' deleted successfully"
        }
        
        if remove_from_index and chunks_removed > 0:
            response["chunks_removed"] = chunks_removed
            response["message"] += f" (removed {chunks_removed} chunks from index)"
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@app.delete("/documents")
async def clear_all_documents(
    clear_index: bool = Query(True, description="Also clear FAISS index and chunks")
):
    """
    Clear all documents from the data/raw directory and optionally clear the FAISS index.
    
    Args:
        clear_index: If True, also delete the FAISS index and chunks files
        
    Returns:
        Deletion response with count of deleted files
    """
    try:
        data_path = Path(DEFAULT_DATA_PATH)
        
        if not data_path.exists():
            return {
                "status": "success",
                "message": "No documents directory found",
                "files_deleted": 0,
                "index_cleared": False
            }
        
        # Get all files in the directory
        files = [f for f in data_path.iterdir() if f.is_file()]
        deleted_files = []
        
        # Delete all files
        for file_path in files:
            try:
                file_path.unlink()
                deleted_files.append(file_path.name)
                logger.info(f"Deleted file: {file_path.name}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path.name}: {str(e)}")
        
        index_cleared = False
        
        # Clear index if requested
        if clear_index:
            index_path = Path(DEFAULT_INDEX_PATH)
            chunks_path = Path(DEFAULT_CHUNKS_PATH)
            
            try:
                if index_path.exists():
                    index_path.unlink()
                    logger.info(f"Deleted FAISS index: {index_path}")
                
                if chunks_path.exists():
                    chunks_path.unlink()
                    logger.info(f"Deleted chunks file: {chunks_path}")
                
                index_cleared = True
            except Exception as e:
                logger.error(f"Error clearing index: {str(e)}", exc_info=True)
        
        logger.info(f"Cleared all documents: {len(deleted_files)} files deleted")
        
        return {
            "status": "success",
            "message": f"Cleared {len(deleted_files)} document(s)" + 
                      (f" and cleared FAISS index" if index_cleared else ""),
            "files_deleted": len(deleted_files),
            "deleted_files": deleted_files,
            "index_cleared": index_cleared
        }
    
    except Exception as e:
        logger.error(f"Error clearing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing documents: {str(e)}")


# Root endpoint - serve the web UI
@app.get("/")
async def root():
    """Serve the web UI."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "name": "RAG Chatbot API",
        "version": "1.0.0",
        "description": "Retrieval-Augmented Generation API for Arabic real estate chatbot",
        "endpoints": {
            "health": "/health",
            "query": "/query",
            "ingest": "/ingest",
            "documents": "/documents",
            "selector_test": "/selector/test",
            "docs": "/docs"
        },
        "ui": "/static/index.html",
        "selector_test_ui": "/static/selector_test.html"
    }


# Selector test UI endpoint
@app.get("/selector/test/ui")
async def selector_test_ui():
    """Serve the selector test HTML page."""
    selector_test_path = static_path / "selector_test.html"
    if selector_test_path.exists():
        return FileResponse(selector_test_path)
    raise HTTPException(status_code=404, detail="Selector test UI not found")


# ============================================================================
# Orchestrator WebSocket Endpoints
# ============================================================================

@app.websocket("/orchestrator/voice-stream")
async def voice_stream_endpoint(websocket: WebSocket, session_id: str = None):
    """
    WebSocket endpoint for voice streaming.
    
    Flow: Audio Input → ASR → RAG → TTS → Audio Output
    
    Client sends:
    - Binary audio chunks (bytes)
    - Control messages: {"type": "start"|"stop"|"ping"}
    
    Server sends:
    - {"type": "recording_started"}
    - {"type": "recording_stopped"}
    - {"type": "asr_processing"}
    - {"type": "partial_transcript", "text": "...", "confidence": 0.95}
    - {"type": "final_transcript", "text": "...", "confidence": 0.95}
    - {"type": "rag_processing"}
    - {"type": "rag_partial", "text": "..."}
    - {"type": "rag_final", "text": "..."}
    - {"type": "tts_processing"}
    - {"type": "audio_chunk", "chunk_index": 0, "audio_base64": "...", "format": "mp3"}
    - {"type": "audio_complete", "total_chunks": 3}
    - {"type": "error", "message": "..."}
    """
    import sys
    from pathlib import Path
    # Add parent directory to path to access orchestrator
    orchestrator_path = Path(__file__).parent.parent.parent / "orchestrator"
    if str(orchestrator_path) not in sys.path:
        sys.path.insert(0, str(orchestrator_path.parent))
    from orchestrator.voice_orchestrator import VoiceOrchestrator
    
    orchestrator = VoiceOrchestrator()
    await orchestrator.handle_voice_stream(websocket, session_id=session_id)


@app.websocket("/orchestrator/text-stream")
async def text_stream_endpoint(websocket: WebSocket, session_id: str = None):
    """
    WebSocket endpoint for text streaming.
    
    Flow: Text Input → RAG → TTS → Audio Output
    
    Client sends:
    - {"type": "query", "text": "..."}
    - {"type": "ping"}
    
    Server sends:
    - {"type": "rag_processing"}
    - {"type": "rag_partial", "text": "..."}
    - {"type": "rag_final", "text": "..."}
    - {"type": "tts_processing"}
    - {"type": "audio_chunk", "chunk_index": 0, "audio_base64": "...", "format": "mp3"}
    - {"type": "audio_complete", "total_chunks": 3}
    - {"type": "error", "message": "..."}
    """
    import sys
    from pathlib import Path
    # Add parent directory to path to access orchestrator
    orchestrator_path = Path(__file__).parent.parent.parent / "orchestrator"
    if str(orchestrator_path) not in sys.path:
        sys.path.insert(0, str(orchestrator_path.parent))
    from orchestrator.text_orchestrator import TextOrchestrator
    
    orchestrator = TextOrchestrator()
    await orchestrator.handle_text_stream(websocket, session_id=session_id)


@app.get("/orchestrator/test")
async def orchestrator_test_page():
    """Serve the orchestrator test HTML page."""
    import sys
    from pathlib import Path
    
    # Find test HTML file
    orchestrator_path = Path(__file__).parent.parent.parent / "orchestrator"
    test_html_path = orchestrator_path / "test_orchestrator.html"
    
    if test_html_path.exists():
        return FileResponse(test_html_path, media_type="text/html")
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Test page not found at {test_html_path}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Suppress watchfiles logging in uvicorn
    logging.getLogger('watchfiles').setLevel(logging.WARNING)
    logging.getLogger('watchfiles.main').setLevel(logging.WARNING)
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    
    # Get configuration from environment or use defaults
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "true").lower() == "true"  # Default to True for development
    
    logger.info(f"Starting FastAPI server on {host}:{port}")
    logger.info(f"Reload enabled: {reload}")
    
    uvicorn.run(
        "app.api:app",  # Use string format for reload to work properly
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        log_config=None  # Use our custom logging configuration
    )
