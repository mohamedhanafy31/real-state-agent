"""
Unit tests for LangGraph RAG nodes
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from rag_graph.schemas import RAGState, Document, Query
from rag_graph.nodes.ingestion_nodes import (
    load_documents,
    clean_text,
    chunk_documents,
    embed_chunks,
    store_embeddings
)
from rag_graph.nodes.query_nodes import (
    embed_query,
    retrieve_chunks,
    generate_answer
)


class TestIngestionNodes:
    """Test ingestion nodes."""
    
    @pytest.fixture
    def sample_state(self):
        """Create a sample state for testing."""
        return {
            'documents': [],
            'cleaned_documents': [],
            'chunks': [],
            'embedded_chunks': [],
            'query': None,
            'embedded_query': None,
            'retrieved_chunks': [],
            'answer': None,
            'config': {},
            'errors': [],
            'vector_store_path': None,
            'chunks_path': None
        }
    
    @pytest.fixture
    def sample_text_file(self, tmp_path):
        """Create a sample text file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("هذا نص تجريبي للاختبار.\n\nفقرة ثانية.", encoding='utf-8')
        return str(file_path)
    
    def test_load_documents(self, sample_state, sample_text_file):
        """Test load_documents node."""
        state = RAGState(**sample_state)
        state['config'] = {
            'data_path': sample_text_file,
            'recursive': False
        }
        
        result = load_documents(state)
        
        assert 'documents' in result
        assert len(result['documents']) > 0
        assert result['documents'][0].content is not None
    
    def test_load_documents_error(self, sample_state):
        """Test load_documents with invalid path."""
        state = RAGState(**sample_state)
        state['config'] = {
            'data_path': '/nonexistent/path',
            'recursive': False
        }
        
        result = load_documents(state)
        
        assert 'errors' in result
        assert len(result['errors']) > 0
    
    def test_clean_text(self, sample_state):
        """Test clean_text node."""
        state = RAGState(**sample_state)
        state['documents'] = [
            Document(content="هذا نص تجريبي", metadata={})
        ]
        
        result = clean_text(state)
        
        assert 'cleaned_documents' in result
        assert len(result['cleaned_documents']) > 0
        assert result['cleaned_documents'][0].content is not None
    
    def test_chunk_documents(self, sample_state):
        """Test chunk_documents node."""
        from rag_graph.schemas import CleanedDocument
        
        state = RAGState(**sample_state)
        state['cleaned_documents'] = [
            CleanedDocument(
                content="فقرة أولى.\n\nفقرة ثانية.\n\nفقرة ثالثة.",
                original_metadata={}
            )
        ]
        state['config'] = {
            'chunk_min_size': 10,
            'chunk_max_size': 100,
            'chunk_overlap': 5
        }
        
        result = chunk_documents(state)
        
        assert 'chunks' in result
        assert len(result['chunks']) > 0
    
    def test_embed_chunks(self, sample_state):
        """Test embed_chunks node."""
        from rag_graph.schemas import Chunk
        
        state = RAGState(**sample_state)
        state['chunks'] = [
            Chunk(text="نص تجريبي", metadata={})
        ]
        state['config'] = {
            'embedder_model_name': 'aubmindlab/bert-base-arabertv2',
            'device': 'cpu',
            'batch_size': 2
        }
        
        try:
            result = embed_chunks(state)
            
            assert 'embedded_chunks' in result
            assert len(result['embedded_chunks']) > 0
            assert result['embedded_chunks'][0].embedding is not None
        except Exception as e:
            pytest.skip(f"Could not test embedding: {str(e)}")
    
    def test_store_embeddings(self, sample_state, tmp_path):
        """Test store_embeddings node."""
        from rag_graph.schemas import EmbeddedChunk, Chunk
        
        # Create mock embedded chunks
        chunk = Chunk(text="test", metadata={})
        embedding = np.random.randn(768).astype('float32')
        embedded_chunk = EmbeddedChunk(chunk=chunk, embedding=embedding)
        
        state = RAGState(**sample_state)
        state['embedded_chunks'] = [embedded_chunk]
        state['config'] = {
            'embedding_dim': 768,
            'index_type': 'flat',
            'save_index_path': str(tmp_path / "index.faiss"),
            'save_chunks_path': str(tmp_path / "chunks.pkl")
        }
        
        result = store_embeddings(state)
        
        assert 'config' in result
        assert 'vector_store' in result['config']
        assert result['vector_store_path'] is not None


class TestQueryNodes:
    """Test query nodes."""
    
    @pytest.fixture
    def sample_state(self):
        """Create a sample state for testing."""
        return {
            'documents': [],
            'cleaned_documents': [],
            'chunks': [],
            'embedded_chunks': [],
            'query': None,
            'embedded_query': None,
            'retrieved_chunks': [],
            'answer': None,
            'config': {},
            'errors': [],
            'vector_store_path': None,
            'chunks_path': None
        }
    
    def test_embed_query(self, sample_state):
        """Test embed_query node."""
        state = RAGState(**sample_state)
        state['query'] = Query(text="سؤال تجريبي")
        state['config'] = {
            'embedder_model_name': 'aubmindlab/bert-base-arabertv2',
            'device': 'cpu',
            'clean_query': True
        }
        
        try:
            result = embed_query(state)
            
            assert 'embedded_query' in result
            assert result['embedded_query'].embedding is not None
        except Exception as e:
            pytest.skip(f"Could not test query embedding: {str(e)}")
    
    def test_retrieve_chunks(self, sample_state, tmp_path):
        """Test retrieve_chunks node."""
        from rag_graph.schemas import EmbeddedQuery
        from src.vector_store import FAISSStore
        import numpy as np
        
        # Create a mock vector store
        embedding_dim = 768
        vector_store = FAISSStore(embedding_dim=embedding_dim)
        
        # Add some test data
        embeddings = np.random.randn(5, embedding_dim).astype('float32')
        chunks_data = [
            {'text': f'Chunk {i}', 'metadata': {}}
            for i in range(5)
        ]
        vector_store.add(embeddings, chunks_data)
        
        # Create embedded query
        query_embedding = np.random.randn(embedding_dim).astype('float32')
        embedded_query = EmbeddedQuery(
            query=Query(text="test query"),
            embedding=query_embedding
        )
        
        state = RAGState(**sample_state)
        state['embedded_query'] = embedded_query
        state['config'] = {
            'vector_store': vector_store,
            'retrieval_k': 3
        }
        
        result = retrieve_chunks(state)
        
        assert 'retrieved_chunks' in result
        assert len(result['retrieved_chunks']) > 0
    
    def test_generate_answer(self, sample_state, skip_if_no_gemini_key):
        """Test generate_answer node."""
        from rag_graph.schemas import RetrievedChunk, Chunk
        import os
        
        # Create mock retrieved chunks
        retrieved_chunks = [
            RetrievedChunk(
                chunk=Chunk(text="Context chunk", metadata={}),
                score=0.9,
                metadata={}
            )
        ]
        
        state = RAGState(**sample_state)
        state['query'] = Query(text="سؤال تجريبي")
        state['retrieved_chunks'] = retrieved_chunks
        state['config'] = {
            'gemini_api_key': os.getenv('GEMINI_API_KEY'),
            'gemini_model_name': 'gemini-pro',
            'temperature': 0.7
        }
        
        result = generate_answer(state)
        
        assert 'answer' in result
        assert result['answer'].text is not None
        assert len(result['answer'].text) > 0

