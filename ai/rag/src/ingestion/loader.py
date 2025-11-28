"""
Document Loader Module
Supports loading various file types: PDF, TXT, DOCX, etc.
"""

import os
from typing import List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Loads content from various file formats."""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.txt', '.docx', '.doc', '.md'}
    
    def load_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load a file and return its content with metadata.
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            Dictionary with 'content' and 'metadata' keys
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        
        if extension not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {extension}")
        
        metadata = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': extension,
            'file_size': file_path.stat().st_size
        }
        
        try:
            if extension == '.pdf':
                content = self._load_pdf(file_path)
            elif extension == '.txt' or extension == '.md':
                content = self._load_text(file_path)
            elif extension in ['.docx', '.doc']:
                content = self._load_docx(file_path)
            else:
                raise ValueError(f"Unsupported file type: {extension}")
            
            return {
                'content': content,
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise
    
    def _load_pdf(self, file_path: Path) -> str:
        """Load content from PDF file."""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF loading. Install it with: pip install PyPDF2")
        
        content = []
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                content.append(page.extract_text())
        
        return '\n'.join(content)
    
    def _load_text(self, file_path: Path) -> str:
        """Load content from text file."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1256']  # cp1256 for Arabic
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        raise ValueError(f"Could not decode file {file_path} with any supported encoding")
    
    def _load_docx(self, file_path: Path) -> str:
        """Load content from DOCX file."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required for DOCX loading. Install it with: pip install python-docx")
        
        doc = Document(file_path)
        content = []
        for paragraph in doc.paragraphs:
            content.append(paragraph.text)
        
        return '\n'.join(content)
    
    def load_directory(self, directory_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Load all supported files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: Whether to search recursively
            
        Returns:
            List of loaded file dictionaries
        """
        directory_path = Path(directory_path)
        if not directory_path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        files = []
        pattern = '**/*' if recursive else '*'
        
        for file_path in directory_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                try:
                    files.append(self.load_file(str(file_path)))
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {str(e)}")
                    continue
        
        return files

