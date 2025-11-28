"""
RAG Pipeline Module
Orchestrates the complete RAG system workflow.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..ingestion import DocumentLoader, TextCleaner, ParagraphChunker
from ..embeddings import AraModernBERTEmbedder
from ..vector_store import FAISSStore
from ..retrieval import Retriever
from ..generator import LLMGenerator
from ..selector import UnitSelector
from ..utils import load_config, get_config_value

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Complete RAG pipeline orchestrator."""
    
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        Initialize the RAG pipeline.
        
        Args:
            config_path: Path to configuration YAML file
            **kwargs: Override config values (e.g., embedder_model_name, gemini_api_key)
        """
        # Load configuration
        config = load_config(config_path) if config_path else {}
        
        # Get configuration values with overrides
        embedder_model_name = kwargs.get('embedder_model_name') or \
            get_config_value(config, 'embedding.model_name', 'mohamed2811/Muffakir_Embedding_V2')
        device = kwargs.get('device') or \
            get_config_value(config, 'embedding.device', None)
        batch_size = kwargs.get('batch_size') or \
            get_config_value(config, 'embedding.batch_size', 32)
        
        chunk_min_size = kwargs.get('chunk_min_size') or \
            get_config_value(config, 'chunking.min_chunk_size', 100)
        chunk_max_size = kwargs.get('chunk_max_size') or \
            get_config_value(config, 'chunking.max_chunk_size', 1000)
        chunk_overlap = kwargs.get('chunk_overlap') or \
            get_config_value(config, 'chunking.overlap', 50)
        
        retrieval_k = kwargs.get('retrieval_k') or \
            get_config_value(config, 'retrieval.k', 5)
        
        gemini_api_key = kwargs.get('gemini_api_key') or \
            get_config_value(config, 'generator.api_key', None)
        gemini_model_name = kwargs.get('gemini_model_name') or \
            get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
        
        index_type = kwargs.get('index_type') or \
            get_config_value(config, 'vector_store.index_type', 'flat')
        
        project_root = Path(__file__).resolve().parents[2]
        unit_selector_csv = kwargs.get('unit_selector_csv') or \
            get_config_value(
                config,
                'unit_selector.csv_path',
                str(project_root / 'data' / '11-15_sample25.csv'),
            )
        unit_selector_max_rows = kwargs.get('unit_selector_max_rows') or \
            get_config_value(config, 'unit_selector.max_rows', 10)

        # Initialize components
        self.loader = DocumentLoader()
        self.cleaner = TextCleaner()
        self.chunker = ParagraphChunker(
            min_chunk_size=chunk_min_size,
            max_chunk_size=chunk_max_size,
            overlap=chunk_overlap
        )
        self.embedder = AraModernBERTEmbedder(
            model_name=embedder_model_name,
            device=device,
            batch_size=batch_size
        )
        
        # Initialize vector store with embedding dimension
        embedding_dim = self.embedder.get_embedding_dim()
        self.vector_store = FAISSStore(embedding_dim=embedding_dim, index_type=index_type)
        
        # Initialize retriever
        self.retriever = Retriever(self.vector_store, self.embedder)
        
        # Initialize generator
        self.generator = LLMGenerator(
            api_key=gemini_api_key,
            model_name=gemini_model_name
        )

        self.unit_selector = UnitSelector(
            csv_path=unit_selector_csv,
            api_key=gemini_api_key,
            model_name=gemini_model_name,
            max_rows=unit_selector_max_rows,
        )
        
        self.retrieval_k = retrieval_k
        self.config = config
        
        logger.info("RAG Pipeline initialized")
    
    def build_index(self, data_path: str, recursive: bool = True,
                   save_index_path: Optional[str] = None,
                   save_chunks_path: Optional[str] = None):
        """
        Build the RAG index from files.
        
        Args:
            data_path: Path to file or directory
            recursive: Whether to search directories recursively
            save_index_path: Optional path to save FAISS index
            save_chunks_path: Optional path to save chunks data
        """
        logger.info(f"Building index from: {data_path}")
        
        # Load files
        data_path = Path(data_path)
        if data_path.is_file():
            files = [self.loader.load_file(str(data_path))]
        else:
            files = self.loader.load_directory(str(data_path), recursive=recursive)
        
        logger.info(f"Loaded {len(files)} files")
        
        # Process files: clean, chunk, embed
        all_chunks = []
        all_texts = []
        
        for file_data in files:
            content = file_data['content']
            metadata = file_data['metadata']
            
            # Clean text
            cleaned_content = self.cleaner.clean(content)
            
            # Chunk text
            chunks = self.chunker.chunk(cleaned_content, metadata=metadata)
            all_chunks.extend(chunks)
            all_texts.extend([chunk['text'] for chunk in chunks])
        
        logger.info(f"Created {len(all_chunks)} chunks")
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        embeddings = self.embedder.embed(all_texts)
        
        # Convert to numpy array if needed
        if isinstance(embeddings, list):
            embeddings = np.array(embeddings)
        
        # Add to vector store
        logger.info("Adding embeddings to index...")
        self.vector_store.add(embeddings, all_chunks)
        
        # Save if paths provided
        if save_index_path and save_chunks_path:
            self.vector_store.save(save_index_path, save_chunks_path)
            logger.info("Index saved successfully")
        
        logger.info("Index building completed")
    
    def load_index(self, index_path: str, chunks_path: str):
        """
        Load a pre-built index.
        
        Args:
            index_path: Path to FAISS index file
            chunks_path: Path to chunks data file
        """
        logger.info("Loading index...")
        self.vector_store.load(index_path, chunks_path)
        logger.info("Index loaded successfully")
    
    def query(self, question: str, k: Optional[int] = None,
             temperature: float = 0.7, return_context: bool = False) -> Dict[str, Any]:
        """
        Query the RAG system.
        
        Args:
            question: User question
            k: Number of chunks to retrieve (defaults to self.retrieval_k)
            temperature: Generation temperature
            return_context: Whether to return retrieved context
            
        Returns:
            Dictionary with 'answer' and optionally 'context'
        """
        k = k or self.retrieval_k
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            retrieval_future = executor.submit(self.retriever.retrieve, question, k)
            selector_future = executor.submit(self.unit_selector.select_units, question)
            results = retrieval_future.result()
            selector_result = selector_future.result()

        structured_rows = selector_result.rows if selector_result else []
        
        # Extract context texts
        context_texts = [result['chunk'] for result in results]
        
        # Generate answer
        answer = self.generator.generate(
            prompt=question,
            context=context_texts,
            structured_data=structured_rows,
            temperature=temperature
        )
        
        response = {'answer': answer}
        
        if return_context:
            response['context'] = results

        if selector_result:
            response['structured_units'] = structured_rows
            response['unit_selector'] = {
                'code': selector_result.code,
                'error': selector_result.error,
            }
        
        return response
    
    def query_stream(self, question: str, k: Optional[int] = None,
                    temperature: float = 0.7):
        """
        Query with streaming response.
        
        Args:
            question: User question
            k: Number of chunks to retrieve
            temperature: Generation temperature
            
        Yields:
            Response chunks as they are generated
        """
        k = k or self.retrieval_k
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            retrieval_future = executor.submit(self.retriever.retrieve, question, k)
            selector_future = executor.submit(self.unit_selector.select_units, question)
            results = retrieval_future.result()
            selector_result = selector_future.result()

        context_texts = [result['chunk'] for result in results]
        structured_rows = selector_result.rows if selector_result else []
        
        # Generate streaming answer
        for chunk in self.generator.generate_stream(
            prompt=question,
            context=context_texts,
            structured_data=structured_rows,
            temperature=temperature
        ):
            yield chunk

