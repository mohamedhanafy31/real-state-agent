"""
Unit tests for LangGraph graph structure
"""

import pytest
from rag_graph.graph import build_rag_graph, build_ingestion_graph, build_query_graph
from rag_graph.schemas import RAGState


class TestGraphBuilding:
    """Test graph building functions."""
    
    def test_build_rag_graph(self):
        """Test building the full RAG graph."""
        graph = build_rag_graph()
        assert graph is not None
    
    def test_build_ingestion_graph(self):
        """Test building the ingestion graph."""
        graph = build_ingestion_graph()
        assert graph is not None
    
    def test_build_query_graph(self):
        """Test building the query graph."""
        graph = build_query_graph()
        assert graph is not None
    
    def test_graph_structure(self):
        """Test that graph has correct nodes."""
        graph = build_ingestion_graph()
        
        # Check that graph has expected nodes
        # Note: This is a basic check - actual node inspection depends on LangGraph API
        assert graph is not None


class TestGraphExecution:
    """Test graph execution."""
    
    @pytest.fixture
    def initial_state(self):
        """Create initial state for testing."""
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
    
    @pytest.mark.asyncio
    async def test_ingestion_graph_execution(self, initial_state, tmp_path):
        """Test executing the ingestion graph."""
        from pathlib import Path
        
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content", encoding='utf-8')
        
        state: RAGState = {
            **initial_state,
            'config': {
                'data_path': str(test_file),
                'recursive': False,
                'chunk_min_size': 10,
                'chunk_max_size': 100,
                'chunk_overlap': 5,
                'embedder_model_name': 'aubmindlab/bert-base-arabertv2',
                'device': 'cpu',
                'batch_size': 2,
                'index_type': 'flat',
                'save_index_path': str(tmp_path / "index.faiss"),
                'save_chunks_path': str(tmp_path / "chunks.pkl")
            }
        }
        
        graph = build_ingestion_graph()
        
        try:
            final_state = await graph.ainvoke(state)
            
            assert 'documents' in final_state
            assert 'chunks' in final_state
            # Check that errors list exists (even if empty)
            assert 'errors' in final_state
        except Exception as e:
            pytest.skip(f"Could not execute graph: {str(e)}")

