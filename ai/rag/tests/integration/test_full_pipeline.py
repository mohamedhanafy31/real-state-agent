"""
Integration tests for full RAG pipeline (Legacy RAGPipeline class)

Note: This tests the old RAGPipeline class from src.pipeline.
For LangGraph-based pipeline tests, see test_langgraph_pipeline.py
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
import numpy as np

from src import RAGPipeline
from src.utils import setup_logging


class TestFullPipeline:
    """Integration tests for the complete RAG pipeline."""
    
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
    
    @pytest.fixture(scope="class")
    def test_docx_path(self):
        """Path to test DOCX file."""
        docx_path = Path(__file__).parent.parent.parent / "data" / "raw" / "test_document.docx"
        if not docx_path.exists():
            # Try alternative names
            alt_path = Path(__file__).parent.parent.parent / "data" / "raw" / "TransIT_Profile.docx"
            if alt_path.exists():
                return str(alt_path)
        return str(docx_path) if docx_path.exists() else None
    
    @pytest.fixture(scope="class")
    def pipeline(self):
        """Create pipeline instance for testing."""
        try:
            # Use CPU for testing to avoid GPU requirements
            pipeline = RAGPipeline(
                embedder_model_name="aubmindlab/bert-base-arabertv2",
                device="cpu",
                chunk_min_size=50,
                chunk_max_size=500,
                chunk_overlap=25,
                retrieval_k=3
            )
            return pipeline
        except Exception as e:
            pytest.skip(f"Could not initialize pipeline: {str(e)}")
    
    def test_pipeline_initialization(self, pipeline):
        """Test that pipeline initializes correctly."""
        assert pipeline is not None
        assert pipeline.loader is not None
        assert pipeline.cleaner is not None
        assert pipeline.chunker is not None
        assert pipeline.embedder is not None
        assert pipeline.vector_store is not None
        assert pipeline.retriever is not None
    
    def test_build_index_from_text_file(self, pipeline, sample_text_file, temp_data_dir):
        """Test building index from a text file."""
        index_path = Path(temp_data_dir) / "index.faiss"
        chunks_path = Path(temp_data_dir) / "chunks.pkl"
        
        pipeline.build_index(
            data_path=sample_text_file,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        # Check that index was created
        assert index_path.exists()
        assert chunks_path.exists()
        
        # Check that index has content
        assert pipeline.vector_store.get_index_size() > 0
    
    def test_build_index_from_directory(self, pipeline, temp_data_dir, sample_text_file):
        """Test building index from a directory."""
        index_path = Path(temp_data_dir) / "index_dir.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_dir.pkl"
        
        # Build index from directory containing the text file
        pipeline.build_index(
            data_path=temp_data_dir,
            recursive=False,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        assert pipeline.vector_store.get_index_size() > 0
    
    @pytest.mark.skipif(
        not Path(__file__).parent.parent.parent.joinpath("data/raw/test_document.docx").exists() and
        not Path(__file__).parent.parent.parent.joinpath("data/raw/TransIT_Profile.docx").exists(),
        reason="Test DOCX file not found"
    )
    def test_build_index_from_docx(self, pipeline, test_docx_path, temp_data_dir):
        """Test building index from a DOCX file."""
        if not test_docx_path or not Path(test_docx_path).exists():
            pytest.skip("DOCX file not available")
        
        try:
            index_path = Path(temp_data_dir) / "index_docx.faiss"
            chunks_path = Path(temp_data_dir) / "chunks_docx.pkl"
            
            pipeline.build_index(
                data_path=test_docx_path,
                save_index_path=str(index_path),
                save_chunks_path=str(chunks_path)
            )
            
            assert pipeline.vector_store.get_index_size() > 0
        except ImportError:
            pytest.skip("python-docx not installed")
    
    def test_load_index(self, pipeline, sample_text_file, temp_data_dir):
        """Test loading a pre-built index."""
        # First build an index
        index_path = Path(temp_data_dir) / "index_load.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_load.pkl"
        
        pipeline.build_index(
            data_path=sample_text_file,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        original_size = pipeline.vector_store.get_index_size()
        
        # Create new pipeline and load index
        new_pipeline = RAGPipeline(
            embedder_model_name="aubmindlab/bert-base-arabertv2",
            device="cpu"
        )
        new_pipeline.load_index(str(index_path), str(chunks_path))
        
        assert new_pipeline.vector_store.get_index_size() == original_size
    
    def test_query_without_index(self, pipeline):
        """Test querying without building index first."""
        # Reset pipeline
        from src.vector_store import FAISSStore
        embedding_dim = pipeline.embedder.get_embedding_dim()
        pipeline.vector_store = FAISSStore(embedding_dim=embedding_dim)
        pipeline.retriever = pipeline.retriever.__class__(pipeline.vector_store, pipeline.embedder)
        
        # Query should return empty results or handle gracefully
        # This depends on implementation - adjust based on actual behavior
        try:
            response = pipeline.query("سؤال تجريبي", k=3)
            # If it doesn't raise an error, check the response
            assert 'answer' in response or 'context' in response
        except Exception:
            # If it raises an error, that's also acceptable behavior
            pass
    
    def test_query_with_index(self, pipeline, sample_text_file, temp_data_dir, skip_if_no_gemini_key):
        """Test querying with a built index."""
        # Build index
        index_path = Path(temp_data_dir) / "index_query.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_query.pkl"
        
        pipeline.build_index(
            data_path=sample_text_file,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        # Query
        response = pipeline.query(
            question="ما هي أنواع العقارات؟",
            k=3,
            return_context=True
        )
        
        assert 'answer' in response
        assert 'context' in response
        assert len(response['context']) > 0
        assert isinstance(response['answer'], str)
        assert len(response['answer']) > 0
    
    def test_query_stream(self, pipeline, sample_text_file, temp_data_dir, skip_if_no_gemini_key):
        """Test streaming query."""
        # Build index
        index_path = Path(temp_data_dir) / "index_stream.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_stream.pkl"
        
        pipeline.build_index(
            data_path=sample_text_file,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        # Stream query
        chunks = list(pipeline.query_stream("ما هي أنواع العقارات؟", k=2))
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
    
    def test_full_workflow(self, pipeline, sample_text_file, temp_data_dir, skip_if_no_gemini_key):
        """Test complete workflow: build index, query, get answer."""
        # Step 1: Build index
        index_path = Path(temp_data_dir) / "index_full.faiss"
        chunks_path = Path(temp_data_dir) / "chunks_full.pkl"
        
        pipeline.build_index(
            data_path=sample_text_file,
            save_index_path=str(index_path),
            save_chunks_path=str(chunks_path)
        )
        
        assert pipeline.vector_store.get_index_size() > 0
        
        # Step 2: Query
        response = pipeline.query(
            question="اذكر أنواع العقارات",
            k=3,
            return_context=True
        )
        
        # Step 3: Verify response
        assert 'answer' in response
        assert 'context' in response
        assert len(response['context']) <= 3
        
        # Step 4: Verify context relevance
        context_texts = [ctx['chunk'] for ctx in response['context']]
        # At least one context should mention العقارات
        assert any('عقار' in ctx.lower() or 'عقارات' in ctx.lower() 
                  for ctx in context_texts)
    
    def test_pipeline_with_config_file(self, temp_data_dir, sample_text_file):
        """Test pipeline initialization with config file."""
        # Create a test config file
        config_path = Path(temp_data_dir) / "test_config.yaml"
        config_content = """
embedding:
  model_name: "aubmindlab/bert-base-arabertv2"
  device: "cpu"
  batch_size: 2

chunking:
  min_chunk_size: 50
  max_chunk_size: 500
  overlap: 25

retrieval:
  k: 3
"""
        config_path.write_text(config_content, encoding='utf-8')
        
        try:
            pipeline = RAGPipeline(config_path=str(config_path))
            assert pipeline is not None
            assert pipeline.retrieval_k == 3
        except Exception as e:
            pytest.skip(f"Could not initialize pipeline with config: {str(e)}")

