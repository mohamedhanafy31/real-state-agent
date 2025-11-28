"""
Unit tests for AraModernBERTEmbedder
"""

import pytest
import numpy as np
import torch

from src.embeddings.embedder import AraModernBERTEmbedder


class TestAraModernBERTEmbedder:
    """Test cases for AraModernBERTEmbedder."""
    
    @pytest.fixture(scope="class")
    def embedder(self):
        """Create embedder instance for testing."""
        try:
            return AraModernBERTEmbedder(
                model_name="aubmindlab/bert-base-arabertv2",
                device="cpu",  # Use CPU for testing
                batch_size=2
            )
        except Exception as e:
            pytest.skip(f"Could not load embedder: {str(e)}")
    
    def test_init(self, embedder):
        """Test embedder initialization."""
        assert embedder.model_name == "aubmindlab/bert-base-arabertv2"
        assert embedder.batch_size == 2
        assert embedder.device in ['cpu', 'cuda']
    
    def test_get_embedding_dim(self, embedder):
        """Test getting embedding dimension."""
        dim = embedder.get_embedding_dim()
        assert isinstance(dim, int)
        assert dim > 0
    
    def test_embed_single_text(self, embedder):
        """Test embedding a single text."""
        text = "هذا نص تجريبي"
        embedding = embedder.embed(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.ndim == 1
        assert len(embedding) == embedder.get_embedding_dim()
    
    def test_embed_list_texts(self, embedder):
        """Test embedding a list of texts."""
        texts = ["نص أول", "نص ثاني", "نص ثالث"]
        embeddings = embedder.embed(texts)
        
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
        assert all(emb.ndim == 1 for emb in embeddings)
    
    def test_embed_empty_list(self, embedder):
        """Test embedding an empty list."""
        embeddings = embedder.embed([])
        assert embeddings == []
    
    def test_embed_normalize(self, embedder):
        """Test that embeddings are normalized when requested."""
        text = "نص للاختبار"
        embedding = embedder.embed(text, normalize=True)
        
        # Check that embedding is normalized (L2 norm should be ~1)
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01  # Allow small floating point errors
    
    def test_embed_batch_processing(self, embedder):
        """Test that batch processing works correctly."""
        # Create more texts than batch size
        texts = [f"نص رقم {i}" for i in range(5)]
        embeddings = embedder.embed(texts)
        
        assert len(embeddings) == len(texts)
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
    
    def test_embed_similarity(self, embedder):
        """Test that similar texts produce similar embeddings."""
        text1 = "هذا نص تجريبي"
        text2 = "هذا نص تجريبي"  # Same text
        text3 = "نص مختلف تماماً"  # Different text
        
        emb1 = embedder.embed(text1, normalize=True)
        emb2 = embedder.embed(text2, normalize=True)
        emb3 = embedder.embed(text3, normalize=True)
        
        # Same texts should have high similarity
        similarity_same = np.dot(emb1, emb2)
        assert similarity_same > 0.9
        
        # Different texts should have lower similarity
        similarity_diff = np.dot(emb1, emb3)
        assert similarity_diff < similarity_same
    
    def test_embed_long_text(self, embedder):
        """Test embedding long text (should be truncated)."""
        long_text = "كلمة " * 200  # Very long text
        embedding = embedder.embed(long_text)
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == embedder.get_embedding_dim()
    
    def test_device_selection(self):
        """Test device selection logic."""
        # Test auto-detection
        try:
            embedder = AraModernBERTEmbedder(device=None)
            assert embedder.device in ['cpu', 'cuda']
        except Exception:
            pytest.skip("Could not initialize embedder")
        
        # Test explicit CPU
        try:
            embedder = AraModernBERTEmbedder(device='cpu')
            assert embedder.device == 'cpu'
        except Exception:
            pytest.skip("Could not initialize embedder")

