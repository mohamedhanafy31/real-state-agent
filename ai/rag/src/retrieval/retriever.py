"""
Retrieval Module
Handles retrieval of relevant chunks from vector store.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class Retriever:
    """Retriever for searching top-k chunks."""
    
    def __init__(self, vector_store, embedder):
        """
        Initialize the retriever.
        
        Args:
            vector_store: Vector store instance (e.g., FAISSStore)
            embedder: Embedder instance for query embeddings
        """
        self.vector_store = vector_store
        self.embedder = embedder
    
    def retrieve(self, query: str, k: int = 5, 
                clean_query: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant chunks for a query.
        
        Args:
            query: Query text
            k: Number of chunks to retrieve
            clean_query: Whether to clean the query text
            
        Returns:
            List of retrieved chunks with scores and metadata
        """
        # Clean query if needed
        if clean_query:
            from ..ingestion import TextCleaner
            cleaner = TextCleaner()
            query = cleaner.clean(query)
        
        # Generate query embedding
        query_embedding = self.embedder.embed(query)
        
        # Convert to numpy if needed
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.array(query_embedding)
        
        # Search in vector store
        results = self.vector_store.search(query_embedding, k=k)
        
        return results

