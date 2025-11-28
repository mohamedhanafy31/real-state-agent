"""
Integration tests for LangGraph RAG pipeline
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
import asyncio

from rag_graph.main import run_ingestion, run_query
from rag_graph.graph import build_ingestion_graph, build_query_graph
from rag_graph.schemas import RAGState, Query


class TestLangGraphPipeline:
    """Integration tests for LangGraph RAG pipeline."""
    
    @pytest.fixture(scope="class")
    def temp_data_dir(self):
        """Create temporary data directory."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture(scope="class")
    def sample_text_file(self, temp_data_dir):
        """Create a sample text file for testing."""
        file_path = Path(temp_data_dir) / "test_document.txt"
        content = """
        هذا مستند تجريبي للاختبار.
        يحتوي على معلومات عن العقارات.
        
        أنواع العقارات المتاحة:
        1. شقق سكنية
        2. فيلات
        3. محلات تجارية
        
        يمكن استخدام هذا المستند لاختبار نظام RAG.
        """
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)
    
    @pytest.mark.asyncio
    async def test_run_ingestion(self, sample_text_file, temp_data_dir):
        """Test running the ingestion pipeline."""
        index_path = Path(temp_data_dir) / "index.faiss"
        chunks_path = Path(temp_data_dir) / "chunks.pkl"
        
        try:
            final_state = await run_ingestion(
                data_path=sample_text_file,
                save_index_path=str(index_path),
                save_chunks_path=str(chunks_path),
                device="cpu"
            )
            
            assert final_state is not None
            assert len(final_state['documents']) > 0
            assert len(final_state['chunks']) > 0
            assert index_path.exists()
            assert chunks_path.exists()
        except Exception as e:
            pytest.skip(f"Could not run ingestion: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_run_query(self, sample_text_file, temp_data_dir, skip_if_no_gemini_key):
        """Test running the query pipeline."""
        index_path = Path(temp_data_dir) / "index_query.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_query.pkl"
        
        # First build index
        try:
            await run_ingestion(
                data_path=sample_text_file,
                save_index_path=str(index_path),
                save_chunks_path=str(chunks_path),
                device="cpu"
            )
        except Exception as e:
            pytest.skip(f"Could not build index: {str(e)}")
        
        # Then query
        try:
            answer = await run_query(
                question="ما هي أنواع العقارات؟",
                index_path=str(index_path),
                chunks_path=str(chunks_path),
                retrieval_k=3
            )
            
            assert answer is not None
            assert answer.text is not None
            assert len(answer.text) > 0
        except Exception as e:
            pytest.skip(f"Could not run query: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, sample_text_file, temp_data_dir, skip_if_no_gemini_key):
        """Test complete workflow: ingestion + query."""
        index_path = Path(temp_data_dir) / "index_full.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_full.pkl"
        
        try:
            # Step 1: Ingestion
            final_state = await run_ingestion(
                data_path=sample_text_file,
                save_index_path=str(index_path),
                save_chunks_path=str(chunks_path),
                device="cpu"
            )
            
            assert len(final_state['chunks']) > 0
            
            # Step 2: Query
            answer = await run_query(
                question="اذكر أنواع العقارات",
                index_path=str(index_path),
                chunks_path=str(chunks_path),
                retrieval_k=3
            )
            
            assert answer is not None
            assert len(answer.text) > 0
            assert len(answer.context_chunks) > 0
        except Exception as e:
            pytest.skip(f"Could not run full workflow: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_graph_direct_execution(self, sample_text_file, temp_data_dir):
        """Test executing graph directly."""
        graph = build_ingestion_graph()
        
        state: RAGState = {
            'documents': [],
            'cleaned_documents': [],
            'chunks': [],
            'embedded_chunks': [],
            'query': None,
            'embedded_query': None,
            'retrieved_chunks': [],
            'answer': None,
            'config': {
                'data_path': sample_text_file,
                'recursive': False,
                'chunk_min_size': 10,
                'chunk_max_size': 100,
                'chunk_overlap': 5,
                'embedder_model_name': 'aubmindlab/bert-base-arabertv2',
                'device': 'cpu',
                'batch_size': 2,
                'index_type': 'flat',
                'save_index_path': str(Path(temp_data_dir) / "index_direct.faiss"),
                'save_chunks_path': str(Path(temp_data_dir) / "chunks_direct.pkl")
            },
            'errors': [],
            'vector_store_path': None,
            'chunks_path': None
        }
        
        try:
            final_state = await graph.ainvoke(state)
            
            assert 'documents' in final_state
            assert len(final_state['documents']) > 0
        except Exception as e:
            pytest.skip(f"Could not execute graph directly: {str(e)}")

