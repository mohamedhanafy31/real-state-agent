"""
Ingestion nodes for LangGraph RAG pipeline
"""

import logging
from typing import Dict, Any
from pathlib import Path

from ..schemas import RAGState, Document, CleanedDocument, Chunk, EmbeddedChunk
from src.ingestion import DocumentLoader, TextCleaner, ParagraphChunker
from src.embeddings import AraModernBERTEmbedder
from src.vector_store import FAISSStore

logger = logging.getLogger(__name__)


def load_documents(state: RAGState) -> Dict[str, Any]:
    """
    Load documents from file or directory.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with loaded documents
    """
    logger.info("Node: load_documents - Starting document loading")
    
    try:
        data_path = state['config'].get('data_path')
        recursive = state['config'].get('recursive', True)
        
        if not data_path:
            error_msg = "data_path not specified in config"
            logger.error(error_msg)
            return {"errors": state.errors + [error_msg]}
        
        loader = DocumentLoader()
        data_path_obj = Path(data_path)
        
        if data_path_obj.is_file():
            files = [loader.load_file(str(data_path_obj))]
        else:
            files = loader.load_directory(str(data_path_obj), recursive=recursive)
        
        documents = [
            Document(content=file_data['content'], metadata=file_data['metadata'])
            for file_data in files
        ]
        
        logger.info(f"Node: load_documents - Loaded {len(documents)} documents")
        
        return {
            "documents": documents,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error loading documents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def clean_text(state: RAGState) -> Dict[str, Any]:
    """
    Clean and normalize text in documents.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with cleaned documents
    """
    logger.info("Node: clean_text - Starting text cleaning")
    
    try:
        if not state.get('documents'):
            error_msg = "No documents to clean"
            logger.warning(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        cleaner = TextCleaner()
        cleaned_documents = []
        
        for doc in state.get('documents', []):
            cleaned_content = cleaner.clean(doc.content)
            cleaned_doc = CleanedDocument(
                content=cleaned_content,
                original_metadata=doc.metadata
            )
            cleaned_documents.append(cleaned_doc)
        
        logger.info(f"Node: clean_text - Cleaned {len(cleaned_documents)} documents")
        
        return {
            "cleaned_documents": cleaned_documents,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error cleaning text: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def chunk_documents(state: RAGState) -> Dict[str, Any]:
    """
    Chunk documents into smaller pieces.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with chunks
    """
    logger.info("Node: chunk_documents - Starting document chunking")
    
    try:
        if not state.get('cleaned_documents'):
            error_msg = "No cleaned documents to chunk"
            logger.warning(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get chunking config
        min_size = state['config'].get('chunk_min_size', 100)
        max_size = state['config'].get('chunk_max_size', 1000)
        overlap = state['config'].get('chunk_overlap', 50)
        
        chunker = ParagraphChunker(
            min_chunk_size=min_size,
            max_chunk_size=max_size,
            overlap=overlap
        )
        
        all_chunks = []
        for cleaned_doc in state.get('cleaned_documents', []):
            chunk_data = chunker.chunk(
                cleaned_doc.content,
                metadata=cleaned_doc.original_metadata
            )
            
            chunks = [
                Chunk(text=chunk['text'], metadata=chunk['metadata'])
                for chunk in chunk_data
            ]
            all_chunks.extend(chunks)
        
        logger.info(f"Node: chunk_documents - Created {len(all_chunks)} chunks")
        
        return {
            "chunks": all_chunks,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error chunking documents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def embed_chunks(state: RAGState) -> Dict[str, Any]:
    """
    Generate embeddings for chunks.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with embedded chunks
    """
    logger.info("Node: embed_chunks - Starting chunk embedding")
    
    try:
        if not state.get('chunks'):
            error_msg = "No chunks to embed"
            logger.warning(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get embedding config
        model_name = state['config'].get('embedder_model_name', 'mohamed2811/Muffakir_Embedding_V2')
        device = state['config'].get('device', None)
        batch_size = state['config'].get('batch_size', 32)
        use_sentence_transformers = state['config'].get('use_sentence_transformers', True)
        
        embedder = AraModernBERTEmbedder(
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            use_sentence_transformers=use_sentence_transformers
        )
        
        # Extract texts for embedding
        texts = [chunk.text for chunk in state.get('chunks', [])]
        
        # Generate embeddings
        embeddings = embedder.embed(texts)
        
        # Convert to numpy array if needed
        import numpy as np
        if isinstance(embeddings, list):
            embeddings = np.array(embeddings)
        
        # Create embedded chunks
        embedded_chunks = [
            EmbeddedChunk(chunk=chunk, embedding=emb)
            for chunk, emb in zip(state.get('chunks', []), embeddings)
        ]
        
        logger.info(f"Node: embed_chunks - Embedded {len(embedded_chunks)} chunks")
        
        # Store embedder in config for later use
        updated_config = state['config'].copy()
        updated_config['embedder'] = embedder
        updated_config['embedding_dim'] = embedder.get_embedding_dim()
        
        return {
            "embedded_chunks": embedded_chunks,
            "config": updated_config,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error embedding chunks: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def store_embeddings(state: RAGState) -> Dict[str, Any]:
    """
    Store embeddings in vector store.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with vector store paths
    """
    logger.info("Node: store_embeddings - Starting embedding storage")
    
    try:
        if not state.get('embedded_chunks'):
            error_msg = "No embedded chunks to store"
            logger.warning(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get or create vector store
        embedding_dim = state['config'].get('embedding_dim')
        if not embedding_dim:
            error_msg = "embedding_dim not found in config"
            logger.error(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        index_type = state['config'].get('index_type', 'flat')
        vector_store = FAISSStore(embedding_dim=embedding_dim, index_type=index_type)
        
        # Prepare embeddings and chunks for storage
        import numpy as np
        embeddings = np.array([ec.embedding for ec in state.get('embedded_chunks', [])])
        chunks_data = [
            {'text': ec.chunk.text, 'metadata': ec.chunk.metadata}
            for ec in state.get('embedded_chunks', [])
        ]
        
        # Add to vector store
        vector_store.add(embeddings, chunks_data)
        
        # Save if paths provided
        index_path = state['config'].get('save_index_path')
        chunks_path = state['config'].get('save_chunks_path')
        
        if index_path and chunks_path:
            vector_store.save(index_path, chunks_path)
            logger.info(f"Node: store_embeddings - Saved index to {index_path}")
        
        # Store vector store in config for query use
        updated_config = state['config'].copy()
        updated_config['vector_store'] = vector_store
        
        return {
            "config": updated_config,
            "vector_store_path": index_path,
            "chunks_path": chunks_path,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error storing embeddings: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}

