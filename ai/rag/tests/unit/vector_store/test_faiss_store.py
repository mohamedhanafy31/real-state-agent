"""
Unit tests for FAISSStore
"""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path

from src.vector_store.faiss_store import FAISSStore


class TestFAISSStore:
    """Test cases for FAISSStore."""
    
    @pytest.fixture
    def embedding_dim(self):
        """Embedding dimension for testing."""
        return 768
    
    @pytest.fixture
    def store(self, embedding_dim):
        """Create FAISS store instance."""
        return FAISSStore(embedding_dim=embedding_dim, index_type="flat")
    
    @pytest.fixture
    def sample_embeddings(self, embedding_dim):
        """Create sample embeddings."""
        np.random.seed(42)
        return np.random.randn(10, embedding_dim).astype('float32')
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks."""
        return [
            {'text': f'Chunk {i}', 'metadata': {'index': i}}
            for i in range(10)
        ]
    
    def test_init(self, embedding_dim):
        """Test store initialization."""
        store = FAISSStore(embedding_dim=embedding_dim)
        assert store.embedding_dim == embedding_dim
        assert store.index is not None
        assert store.chunks == []
    
    def test_init_ivf(self, embedding_dim):
        """Test initialization with IVF index."""
        store = FAISSStore(embedding_dim=embedding_dim, index_type="ivf")
        assert store.index_type == "ivf"
        assert store.index is not None
    
    def test_init_invalid_type(self, embedding_dim):
        """Test initialization with invalid index type."""
        with pytest.raises(ValueError, match="Unsupported index type"):
            FAISSStore(embedding_dim=embedding_dim, index_type="invalid")
    
    def test_add_embeddings(self, store, sample_embeddings, sample_chunks):
        """Test adding embeddings to the store."""
        store.add(sample_embeddings, sample_chunks)
        
        assert store.get_index_size() == len(sample_embeddings)
        assert len(store.chunks) == len(sample_chunks)
    
    def test_add_embeddings_dimension_mismatch(self, store, sample_chunks):
        """Test adding embeddings with wrong dimension."""
        wrong_embeddings = np.random.randn(5, 512).astype('float32')
        
        with pytest.raises(ValueError, match="dimension mismatch"):
            store.add(wrong_embeddings, sample_chunks[:5])
    
    def test_add_embeddings_length_mismatch(self, store, sample_embeddings, sample_chunks):
        """Test adding embeddings with mismatched chunk count."""
        with pytest.raises(ValueError, match="Number of embeddings must match"):
            store.add(sample_embeddings, sample_chunks[:5])
    
    def test_search(self, store, sample_embeddings, sample_chunks):
        """Test searching the store."""
        store.add(sample_embeddings, sample_chunks)
        
        # Create a query embedding
        query = sample_embeddings[0].reshape(1, -1)
        results = store.search(query, k=3)
        
        assert len(results) == 3
        assert all('chunk' in r for r in results)
        assert all('score' in r for r in results)
        assert all('metadata' in r for r in results)
        # First result should be the same as query (high similarity)
        assert results[0]['score'] > 0.9
    
    def test_search_empty_index(self, store):
        """Test searching an empty index."""
        query = np.random.randn(1, store.embedding_dim).astype('float32')
        results = store.search(query, k=5)
        
        assert results == []
    
    def test_search_k_larger_than_index(self, store, sample_embeddings, sample_chunks):
        """Test searching with k larger than index size."""
        store.add(sample_embeddings, sample_chunks)
        
        query = sample_embeddings[0].reshape(1, -1)
        results = store.search(query, k=100)  # More than available
        
        assert len(results) == len(sample_embeddings)
    
    def test_search_similarity_scores(self, store, sample_embeddings, sample_chunks):
        """Test that similarity scores are reasonable."""
        store.add(sample_embeddings, sample_chunks)
        
        query = sample_embeddings[0].reshape(1, -1)
        results = store.search(query, k=5)
        
        # Scores should be between 0 and 1 (cosine similarity)
        assert all(0 <= r['score'] <= 1 for r in results)
        # Results should be sorted by score (descending)
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_save_and_load(self, store, sample_embeddings, sample_chunks, temp_dir):
        """Test saving and loading the store."""
        store.add(sample_embeddings, sample_chunks)
        
        index_path = Path(temp_dir) / "index.faiss"
        chunks_path = Path(temp_dir) / "chunks.pkl"
        
        # Save
        store.save(str(index_path), str(chunks_path))
        assert index_path.exists()
        assert chunks_path.exists()
        
        # Create new store and load
        new_store = FAISSStore(embedding_dim=store.embedding_dim)
        new_store.load(str(index_path), str(chunks_path))
        
        assert new_store.get_index_size() == store.get_index_size()
        assert len(new_store.chunks) == len(store.chunks)
        
        # Test that loaded store works
        query = sample_embeddings[0].reshape(1, -1)
        results = new_store.search(query, k=3)
        assert len(results) == 3
    
    def test_load_nonexistent_file(self, store, temp_dir):
        """Test loading non-existent files."""
        index_path = Path(temp_dir) / "nonexistent.faiss"
        chunks_path = Path(temp_dir) / "nonexistent.pkl"
        
        with pytest.raises(FileNotFoundError):
            store.load(str(index_path), str(chunks_path))
    
    def test_get_index_size(self, store, sample_embeddings, sample_chunks):
        """Test getting index size."""
        assert store.get_index_size() == 0
        
        store.add(sample_embeddings, sample_chunks)
        assert store.get_index_size() == len(sample_embeddings)
    
    def test_query_embedding_shape(self, store, sample_embeddings, sample_chunks):
        """Test that query embedding shape is handled correctly."""
        store.add(sample_embeddings, sample_chunks)
        
        # Test 1D array
        query_1d = sample_embeddings[0]
        results_1d = store.search(query_1d, k=3)
        assert len(results_1d) == 3
        
        # Test 2D array
        query_2d = sample_embeddings[0].reshape(1, -1)
        results_2d = store.search(query_2d, k=3)
        assert len(results_2d) == 3

