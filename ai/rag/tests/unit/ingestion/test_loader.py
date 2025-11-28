"""
Unit tests for DocumentLoader
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from src.ingestion.loader import DocumentLoader


class TestDocumentLoader:
    """Test cases for DocumentLoader."""
    
    def test_init(self):
        """Test loader initialization."""
        loader = DocumentLoader()
        assert loader.supported_extensions == {'.pdf', '.txt', '.docx', '.doc', '.md'}
    
    def test_load_text_file(self, sample_txt_file):
        """Test loading a text file."""
        loader = DocumentLoader()
        result = loader.load_file(sample_txt_file)
        
        assert 'content' in result
        assert 'metadata' in result
        assert result['metadata']['file_extension'] == '.txt'
        assert result['metadata']['file_name'] == 'test.txt'
        assert len(result['content']) > 0
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        loader = DocumentLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file("nonexistent_file.txt")
    
    def test_load_unsupported_file(self, temp_dir):
        """Test loading an unsupported file type."""
        loader = DocumentLoader()
        file_path = Path(temp_dir) / "test.xyz"
        file_path.write_text("test content")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            loader.load_file(str(file_path))
    
    def test_load_directory(self, temp_dir, sample_text):
        """Test loading files from a directory."""
        loader = DocumentLoader()
        
        # Create multiple test files
        (Path(temp_dir) / "file1.txt").write_text(sample_text, encoding='utf-8')
        (Path(temp_dir) / "file2.txt").write_text(sample_text, encoding='utf-8')
        (Path(temp_dir) / "file3.md").write_text(sample_text, encoding='utf-8')
        (Path(temp_dir) / "ignore.xyz").write_text("ignore", encoding='utf-8')
        
        files = loader.load_directory(temp_dir, recursive=False)
        
        assert len(files) == 3  # Should load .txt and .md files
        assert all('content' in f and 'metadata' in f for f in files)
    
    def test_load_directory_recursive(self, temp_dir, sample_text):
        """Test loading files recursively from a directory."""
        loader = DocumentLoader()
        
        # Create nested structure
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        
        (Path(temp_dir) / "file1.txt").write_text(sample_text, encoding='utf-8')
        (subdir / "file2.txt").write_text(sample_text, encoding='utf-8')
        
        files = loader.load_directory(temp_dir, recursive=True)
        assert len(files) == 2
        
        files = loader.load_directory(temp_dir, recursive=False)
        assert len(files) == 1
    
    def test_load_docx_file(self, test_docx_path):
        """Test loading a DOCX file."""
        loader = DocumentLoader()
        
        # Skip if file doesn't exist
        if not Path(test_docx_path).exists():
            pytest.skip(f"Test DOCX file not found: {test_docx_path}")
        
        try:
            result = loader.load_file(test_docx_path)
            assert 'content' in result
            assert 'metadata' in result
            assert result['metadata']['file_extension'] == '.docx'
        except ImportError:
            pytest.skip("python-docx not installed")
    
    def test_load_directory_invalid_path(self):
        """Test loading from invalid directory path."""
        loader = DocumentLoader()
        with pytest.raises(ValueError, match="Not a directory"):
            loader.load_directory("nonexistent_directory")
    
    def test_file_metadata(self, sample_txt_file):
        """Test that file metadata is correctly extracted."""
        loader = DocumentLoader()
        result = loader.load_file(sample_txt_file)
        
        metadata = result['metadata']
        assert 'file_path' in metadata
        assert 'file_name' in metadata
        assert 'file_extension' in metadata
        assert 'file_size' in metadata
        assert metadata['file_size'] > 0

