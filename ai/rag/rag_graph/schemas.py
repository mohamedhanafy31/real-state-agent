"""
Data schemas for LangGraph RAG nodes
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TypedDict
import numpy as np


@dataclass
class Document:
    """Represents a loaded document."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanedDocument:
    """Represents a cleaned document."""
    content: str
    original_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """Represents a text chunk."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedChunk:
    """Represents a chunk with its embedding."""
    chunk: Chunk
    embedding: np.ndarray


@dataclass
class Query:
    """Represents a user query."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedQuery:
    """Represents a query with its embedding."""
    query: Query
    embedding: np.ndarray


@dataclass
class RetrievedChunk:
    """Represents a retrieved chunk with similarity score."""
    chunk: Chunk
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Answer:
    """Represents a generated answer."""
    text: str
    context_chunks: List[RetrievedChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGState(TypedDict):
    """State object for LangGraph RAG workflow."""
    # Ingestion state
    documents: List[Document]
    cleaned_documents: List[CleanedDocument]
    chunks: List[Chunk]
    embedded_chunks: List[EmbeddedChunk]
    
    # Query state
    query: Optional[Query]
    embedded_query: Optional[EmbeddedQuery]
    retrieved_chunks: List[RetrievedChunk]
    structured_units: List[Dict[str, Any]]  # Units from CSV selector
    answer: Optional[Answer]
    
    # Configuration and metadata
    config: Dict[str, Any]
    errors: List[str]
    vector_store_path: Optional[str]
    chunks_path: Optional[str]

