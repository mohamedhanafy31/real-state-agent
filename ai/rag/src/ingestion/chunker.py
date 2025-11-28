"""
Paragraph-based File Chunker Module
Splits documents into paragraph-based chunks for RAG.
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ParagraphChunker:
    """Chunks text based on paragraphs."""
    
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 1000,
                 overlap: int = 50):
        """
        Initialize the chunker.
        
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        
        # Pattern to split paragraphs (handles Arabic and English)
        self.paragraph_pattern = re.compile(r'\n\s*\n+')
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Split text into paragraph-based chunks.
        
        Args:
            text: Input text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with 'text' and 'metadata' keys
        """
        if not text or not text.strip():
            return []
        
        # Split into paragraphs
        paragraphs = self.paragraph_pattern.split(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return []
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            para_size = len(paragraph)
            
            # If single paragraph exceeds max size, split it
            if para_size > self.max_chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append(self._create_chunk(chunk_text, metadata, len(chunks)))
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph
                sub_chunks = self._split_large_paragraph(paragraph)
                for sub_chunk in sub_chunks:
                    chunks.append(self._create_chunk(sub_chunk, metadata, len(chunks)))
            
            # If adding this paragraph would exceed max size, save current chunk
            elif current_size + para_size + 2 > self.max_chunk_size:  # +2 for \n\n
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append(self._create_chunk(chunk_text, metadata, len(chunks)))
                
                # Start new chunk with overlap if enabled
                if self.overlap > 0 and current_chunk:
                    overlap_text = self._get_overlap_text(current_chunk, self.overlap)
                    current_chunk = [overlap_text, paragraph] if overlap_text else [paragraph]
                    current_size = len('\n\n'.join(current_chunk))
                else:
                    current_chunk = [paragraph]
                    current_size = para_size
            
            # Add paragraph to current chunk
            else:
                current_chunk.append(paragraph)
                current_size += para_size + 2  # +2 for \n\n
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(self._create_chunk(chunk_text, metadata, len(chunks)))
        
        return chunks
    
    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """Split a paragraph that exceeds max_chunk_size."""
        chunks = []
        
        # Try to split on sentence boundaries first
        sentences = re.split(r'[.!?]\s+', paragraph)
        
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sent_size = len(sentence)
            
            if current_size + sent_size + 1 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sent_size
            else:
                current_chunk.append(sentence)
                current_size += sent_size + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # If still too large, split by character count
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.max_chunk_size:
                final_chunks.append(chunk)
            else:
                # Split by character count
                for i in range(0, len(chunk), self.max_chunk_size - self.overlap):
                    sub_chunk = chunk[i:i + self.max_chunk_size]
                    if sub_chunk.strip():
                        final_chunks.append(sub_chunk.strip())
        
        return final_chunks
    
    def _get_overlap_text(self, chunks: List[str], overlap_size: int) -> str:
        """Get overlap text from the end of chunks."""
        if not chunks:
            return ""
        
        last_chunk = chunks[-1]
        if len(last_chunk) <= overlap_size:
            return last_chunk
        
        # Get last overlap_size characters
        overlap = last_chunk[-overlap_size:]
        
        # Try to start from word boundary
        words = overlap.split()
        if len(words) > 1:
            # Skip first word if it's partial
            return ' '.join(words[1:])
        
        return overlap
    
    def _create_chunk(self, text: str, metadata: Optional[Dict[str, Any]], 
                     chunk_index: int) -> Dict[str, Any]:
        """Create a chunk dictionary."""
        chunk_metadata = {
            'chunk_index': chunk_index,
            'chunk_size': len(text),
            'char_count': len(text),
            'word_count': len(text.split())
        }
        
        if metadata:
            chunk_metadata.update(metadata)
        
        return {
            'text': text,
            'metadata': chunk_metadata
        }
    
    def chunk_batch(self, texts: List[str], 
                   metadatas: Optional[List[Dict[str, Any]]] = None) -> List[List[Dict[str, Any]]]:
        """Chunk a batch of texts."""
        if metadatas is None:
            metadatas = [None] * len(texts)
        
        return [self.chunk(text, metadata) for text, metadata in zip(texts, metadatas)]

