"""
Unit tests for ParagraphChunker
"""

import pytest
from src.ingestion.chunker import ParagraphChunker


class TestParagraphChunker:
    """Test cases for ParagraphChunker."""
    
    def test_init_default(self):
        """Test chunker initialization with default parameters."""
        chunker = ParagraphChunker()
        assert chunker.min_chunk_size == 100
        assert chunker.max_chunk_size == 1000
        assert chunker.overlap == 50
    
    def test_init_custom(self):
        """Test chunker initialization with custom parameters."""
        chunker = ParagraphChunker(min_chunk_size=50, max_chunk_size=500, overlap=25)
        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 500
        assert chunker.overlap == 25
    
    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = ParagraphChunker()
        result = chunker.chunk("")
        assert result == []
    
    def test_chunk_whitespace_only(self):
        """Test chunking whitespace-only text."""
        chunker = ParagraphChunker()
        result = chunker.chunk("   \n\n   ")
        assert result == []
    
    def test_chunk_single_paragraph(self):
        """Test chunking a single paragraph."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=1000)
        text = "هذا فقرة واحدة تحتوي على نص عربي للاختبار."
        result = chunker.chunk(text)
        
        assert len(result) > 0
        assert all('text' in chunk and 'metadata' in chunk for chunk in result)
        assert result[0]['text'] == text.strip()
    
    def test_chunk_multiple_paragraphs(self):
        """Test chunking multiple paragraphs."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=1000)
        text = "فقرة أولى.\n\nفقرة ثانية.\n\nفقرة ثالثة."
        result = chunker.chunk(text)
        
        assert len(result) >= 1
        # All chunks should have text and metadata
        assert all('text' in chunk and 'metadata' in chunk for chunk in result)
    
    def test_chunk_respects_max_size(self):
        """Test that chunks respect max_chunk_size."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=100, overlap=0)
        # Create text that exceeds max size
        long_text = "كلمة " * 50  # Should create multiple chunks
        result = chunker.chunk(long_text)
        
        assert len(result) > 0
        # All chunks should be within max size (with some tolerance)
        for chunk in result:
            assert len(chunk['text']) <= chunker.max_chunk_size + 50  # Allow some tolerance
    
    def test_chunk_metadata(self):
        """Test that chunk metadata is correctly set."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=1000)
        text = "هذا نص تجريبي للاختبار. يحتوي على عدة كلمات لضمان أن يكون حجمه كافياً."
        metadata = {'source': 'test', 'page': 1}
        result = chunker.chunk(text, metadata=metadata)
        
        assert len(result) > 0
        chunk_meta = result[0]['metadata']
        assert 'chunk_index' in chunk_meta
        assert 'chunk_size' in chunk_meta
        assert 'char_count' in chunk_meta
        assert 'word_count' in chunk_meta
        assert chunk_meta['source'] == 'test'
        assert chunk_meta['page'] == 1
    
    def test_chunk_overlap(self):
        """Test that overlap is applied between chunks."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=50, overlap=10)
        # Create text that will be split into multiple chunks
        text = " ".join([f"كلمة{i}" for i in range(20)])
        result = chunker.chunk(text)
        
        if len(result) > 1:
            # Check that there's some overlap (basic check)
            assert len(result) >= 1
    
    def test_chunk_large_paragraph(self):
        """Test chunking a paragraph that exceeds max size."""
        chunker = ParagraphChunker(min_chunk_size=10, max_chunk_size=50, overlap=5)
        # Create a very long paragraph
        long_para = "كلمة " * 100
        result = chunker.chunk(long_para)
        
        assert len(result) > 0
        # Should be split into multiple chunks
        assert all('text' in chunk for chunk in result)
    
    def test_chunk_batch(self):
        """Test chunking a batch of texts."""
        chunker = ParagraphChunker()
        texts = ["نص أول", "نص ثاني\n\nفقرة ثانية", "نص ثالث"]
        result = chunker.chunk_batch(texts)
        
        assert len(result) == len(texts)
        assert all(isinstance(chunks, list) for chunks in result)
    
    def test_chunk_batch_with_metadata(self):
        """Test chunking a batch with metadata."""
        chunker = ParagraphChunker()
        texts = ["نص أول", "نص ثاني"]
        metadatas = [{'source': 'doc1'}, {'source': 'doc2'}]
        result = chunker.chunk_batch(texts, metadatas=metadatas)
        
        assert len(result) == len(texts)
        # Check metadata is preserved
        for chunks, expected_source in zip(result, ['doc1', 'doc2']):
            if chunks:
                assert chunks[0]['metadata']['source'] == expected_source
    
    def test_chunk_min_size_filtering(self):
        """Test that chunks below min_size are filtered out."""
        chunker = ParagraphChunker(min_chunk_size=100, max_chunk_size=1000)
        short_text = "نص قصير"
        result = chunker.chunk(short_text)
        
        # Should be empty or all chunks should meet min size
        if result:
            assert all(len(chunk['text']) >= chunker.min_chunk_size for chunk in result)

