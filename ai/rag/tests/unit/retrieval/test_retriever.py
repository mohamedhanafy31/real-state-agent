"""
Unit tests for Retriever
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock

from src.retrieval.retriever import Retriever


class TestRetriever:
    """Test cases for Retriever."""
    
    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = Mock()
        store.search = Mock(return_value=[
            {'chunk': 'Chunk 1', 'score': 0.9, 'metadata': {}},
            {'chunk': 'Chunk 2', 'score': 0.8, 'metadata': {}},
        ])
        return store
    
    @pytest.fixture
    def mock_embedder(self):
        """Create a mock embedder."""
        embedder = Mock()
        embedder.embed = Mock(return_value=np.random.randn(768))
        return embedder
    
    @pytest.fixture
    def retriever(self, mock_vector_store, mock_embedder):
        """Create retriever instance."""
        return Retriever(mock_vector_store, mock_embedder)
    
    def test_init(self, mock_vector_store, mock_embedder):
        """Test retriever initialization."""
        retriever = Retriever(mock_vector_store, mock_embedder)
        assert retriever.vector_store == mock_vector_store
        assert retriever.embedder == mock_embedder
    
    def test_retrieve(self, retriever, mock_embedder, mock_vector_store):
        """Test basic retrieval."""
        query = "test query"
        results = retriever.retrieve(query, k=2)
        
        # Check that embedder was called
        mock_embedder.embed.assert_called_once()
        
        # Check that vector store search was called
        mock_vector_store.search.assert_called_once()
        
        # Check results
        assert len(results) == 2
        assert all('chunk' in r for r in results)
        assert all('score' in r for r in results)
    
    def test_retrieve_with_cleaning(self, retriever, mock_embedder, mock_vector_store):
        """Test retrieval with query cleaning."""
        query = "test query"
        retriever.retrieve(query, k=2, clean_query=True)
        
        # Embedder should be called with cleaned query
        mock_embedder.embed.assert_called_once()
        call_args = mock_embedder.embed.call_args[0][0]
        assert isinstance(call_args, str)
    
    def test_retrieve_without_cleaning(self, retriever, mock_embedder, mock_vector_store):
        """Test retrieval without query cleaning."""
        query = "test query"
        retriever.retrieve(query, k=2, clean_query=False)
        
        # Embedder should be called with original query
        mock_embedder.embed.assert_called_once()
        call_args = mock_embedder.embed.call_args[0][0]
        assert call_args == query
    
    def test_retrieve_k_parameter(self, retriever, mock_vector_store):
        """Test that k parameter is passed correctly."""
        query = "test query"
        retriever.retrieve(query, k=5)
        
        # Check that search was called with correct k
        call_args = mock_vector_store.search.call_args
        assert call_args[1]['k'] == 5
    
    def test_retrieve_empty_results(self, mock_vector_store, mock_embedder):
        """Test retrieval when vector store returns empty results."""
        mock_vector_store.search.return_value = []
        retriever = Retriever(mock_vector_store, mock_embedder)
        
        results = retriever.retrieve("query", k=5)
        assert results == []
    
    def test_retrieve_embedding_conversion(self, mock_vector_store, mock_embedder):
        """Test that embeddings are converted to numpy arrays."""
        # Return a list instead of numpy array
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
        retriever = Retriever(mock_vector_store, mock_embedder)
        
        # Should still work (conversion happens in retriever)
        results = retriever.retrieve("query", k=2)
        assert len(results) == 2

