"""
FAISS Vector Store Module
Efficient similarity search using FAISS index.
"""

import faiss
import numpy as np
import pickle
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FAISSStore:
    """FAISS-based vector store for similarity search."""
    
    def __init__(self, embedding_dim: int, index_type: str = "flat"):
        """
        Initialize the FAISS store.
        
        Args:
            embedding_dim: Dimension of embeddings
            index_type: Type of FAISS index ('flat' or 'ivf')
        """
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.index = None
        self.chunks = []  # Store chunk texts and metadata
        self._build_index()
    
    def _build_index(self):
        """Build the FAISS index."""
        if self.index_type == "flat":
            # L2 distance index (for cosine similarity, normalize embeddings)
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        elif self.index_type == "ivf":
            # IVF index for faster search on large datasets
            quantizer = faiss.IndexFlatL2(self.embedding_dim)
            self.index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, 100)
        else:
            raise ValueError(f"Unsupported index type: {self.index_type}")
    
    def add(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]]):
        """
        Add embeddings and corresponding chunks to the index.
        
        Args:
            embeddings: Numpy array of embeddings (n_samples, embedding_dim)
            chunks: List of chunk dictionaries
        """
        if len(embeddings) != len(chunks):
            raise ValueError("Number of embeddings must match number of chunks")
        
        if embeddings.shape[1] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {embeddings.shape[1]}"
            )
        
        # Convert to float32 (required by FAISS)
        embeddings = embeddings.astype('float32')
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Train index if needed (for IVF)
        if self.index_type == "ivf" and not self.index.is_trained:
            logger.info("Training IVF index...")
            self.index.train(embeddings)
        
        # Add to index
        self.index.add(embeddings)
        self.chunks.extend(chunks)
        
        logger.info(f"Added {len(embeddings)} embeddings to index. Total: {self.index.ntotal}")
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query embedding (1, embedding_dim) or (embedding_dim,)
            k: Number of results to return
            
        Returns:
            List of dictionaries with 'chunk', 'score', and 'metadata' keys
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Index is empty")
            return []
        
        # Reshape if needed
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        query_dim = query_embedding.shape[1]
        if query_dim != self.embedding_dim:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {query_dim}. This usually happens when the embedding model was changed. "
                f"Please rebuild the index with: python run.py ingest"
            )
        
        # Also check against actual FAISS index dimension (in case of mismatch)
        if self.index is not None and query_dim != self.index.d:
            raise ValueError(
                f"FAISS index dimension mismatch: Query embedding has dimension {query_dim}, "
                f"but index was built with dimension {self.index.d}. "
                f"The index was likely built with a different embedding model. "
                f"Please rebuild the index with: python run.py ingest"
            )
        
        # Convert to float32 and normalize
        query_embedding = query_embedding.astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # Search
        k = min(k, self.index.ntotal)
        try:
            distances, indices = self.index.search(query_embedding, k)
        except AssertionError as e:
            # FAISS throws AssertionError when dimensions don't match
            raise ValueError(
                f"FAISS dimension mismatch error: Query embedding dimension ({query_dim}) "
                f"does not match index dimension ({self.index.d}). "
                f"This happens when the embedding model was changed after building the index. "
                f"Solution: Rebuild the index with the current embedding model:\n"
                f"  python run.py ingest\n"
                f"Or delete the old index and rebuild:\n"
                f"  rm -rf data/embeddings/* && python run.py ingest"
            ) from e
        
        # Convert distances to similarity scores (1 - normalized distance for cosine)
        # Since we're using L2 on normalized vectors, distance = 2 - 2*cosine_similarity
        # So cosine_similarity = 1 - distance/2
        similarities = 1 - (distances[0] / 2)
        
        # Build results
        results = []
        for idx, similarity in zip(indices[0], similarities):
            if idx < len(self.chunks):
                chunk_data = self.chunks[idx]
                results.append({
                    'chunk': chunk_data.get('text', ''),
                    'score': float(similarity),
                    'metadata': chunk_data.get('metadata', {})
                })
        
        return results
    
    def save(self, index_path: str, chunks_path: str):
        """
        Save the index and chunks to disk.
        
        Args:
            index_path: Path to save FAISS index
            chunks_path: Path to save chunks data
        """
        if self.index is None:
            raise ValueError("No index to save")
        
        # Save FAISS index
        faiss.write_index(self.index, index_path)
        logger.info(f"Saved FAISS index to {index_path}")
        
        # Save chunks
        with open(chunks_path, 'wb') as f:
            pickle.dump(self.chunks, f)
        logger.info(f"Saved chunks to {chunks_path}")
    
    def load(self, index_path: str, chunks_path: str):
        """
        Load the index and chunks from disk.
        
        Args:
            index_path: Path to FAISS index file
            chunks_path: Path to chunks data file
        """
        # Load FAISS index
        if not Path(index_path).exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")
        
        self.index = faiss.read_index(index_path)
        logger.info(f"Loaded FAISS index from {index_path}")
        
        # Load chunks
        if not Path(chunks_path).exists():
            raise FileNotFoundError(f"Chunks file not found: {chunks_path}")
        
        with open(chunks_path, 'rb') as f:
            self.chunks = pickle.load(f)
        logger.info(f"Loaded {len(self.chunks)} chunks from {chunks_path}")
    
    def get_index_size(self) -> int:
        """Get the number of items in the index."""
        return self.index.ntotal if self.index else 0

