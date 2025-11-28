"""
Query nodes for LangGraph RAG pipeline
"""

import logging
from typing import Dict, Any
import numpy as np

from ..schemas import RAGState, EmbeddedQuery, RetrievedChunk, Answer
from src.ingestion import TextCleaner
from src.generator import LLMGenerator
from src.selector import UnitSelector

logger = logging.getLogger(__name__)


def embed_query(state: RAGState) -> Dict[str, Any]:
    """
    Embed the user query.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with embedded query
    """
    logger.info("Node: embed_query - Starting query embedding")
    
    try:
        if not state.get('query'):
            error_msg = "No query to embed"
            logger.error(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get embedder from config or create new one
        embedder = state['config'].get('embedder')
        if not embedder:
            # Create new embedder
            model_name = state['config'].get('embedder_model_name', 'mohamed2811/Muffakir_Embedding_V2')
            device = state['config'].get('device', None)
            use_sentence_transformers = state['config'].get('use_sentence_transformers', True)
            
            from src.embeddings import AraModernBERTEmbedder
            embedder = AraModernBERTEmbedder(
                model_name=model_name, 
                device=device,
                use_sentence_transformers=use_sentence_transformers
            )
        
        # Clean query if needed
        query_text = state['query'].text
        if state['config'].get('clean_query', True):
            cleaner = TextCleaner()
            query_text = cleaner.clean(query_text)
        
        # Generate embedding
        embedding = embedder.embed(query_text)
        
        # Convert to numpy if needed
        if isinstance(embedding, list):
            embedding = np.array(embedding)
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        embedded_query = EmbeddedQuery(query=state['query'], embedding=embedding[0])
        
        logger.info("Node: embed_query - Query embedded successfully")
        
        return {
            "embedded_query": embedded_query,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error embedding query: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def retrieve_chunks(state: RAGState) -> Dict[str, Any]:
    """
    Retrieve relevant chunks from vector store.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with retrieved chunks
    """
    logger.info("Node: retrieve_chunks - Starting chunk retrieval")
    
    try:
        if not state.get('embedded_query'):
            error_msg = "No embedded query for retrieval"
            logger.error(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get vector store from config or load from path
        vector_store = state['config'].get('vector_store')
        
        if not vector_store:
            # Try to load from path
            index_path = state.get('vector_store_path') or state['config'].get('load_index_path')
            chunks_path = state.get('chunks_path') or state['config'].get('load_chunks_path')
            
            if index_path and chunks_path:
                from src.vector_store import FAISSStore
                embedding_dim = state['config'].get('embedding_dim')
                if not embedding_dim:
                    error_msg = "embedding_dim required to load vector store"
                    logger.error(error_msg)
                    return {"errors": state.get('errors', []) + [error_msg]}
                
                vector_store = FAISSStore(embedding_dim=embedding_dim)
                vector_store.load(index_path, chunks_path)
                logger.info(f"Node: retrieve_chunks - Loaded vector store from {index_path}")
            else:
                error_msg = "Vector store not available and no paths provided"
                logger.error(error_msg)
                return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get retrieval config
        k = state['config'].get('retrieval_k', 5)
        
        # Retrieve chunks
        query_embedding = state['embedded_query'].embedding.reshape(1, -1)
        results = vector_store.search(query_embedding, k=k)
        
        # Convert to RetrievedChunk objects
        from ..schemas import Chunk
        retrieved_chunks = [
            RetrievedChunk(
                chunk=Chunk(text=r['chunk'], metadata=r['metadata']),
                score=r['score'],
                metadata=r['metadata']
            )
            for r in results
        ]
        
        logger.info(f"Node: retrieve_chunks - Retrieved {len(retrieved_chunks)} chunks")
        
        return {
            "retrieved_chunks": retrieved_chunks,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error retrieving chunks: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def generate_answer(state: RAGState) -> Dict[str, Any]:
    """
    Generate answer using LLM with retrieved context.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with generated answer
    """
    logger.info("Node: generate_answer - Starting answer generation")
    
    try:
        if not state.get('query'):
            error_msg = "No query for answer generation"
            logger.error(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        if not state.get('retrieved_chunks'):
            logger.warning("No retrieved chunks for context")
        
        # Get generator config
        api_key = state['config'].get('gemini_api_key')
        model_name = state['config'].get('gemini_model_name', 'gemini-2.0-flash')
        temperature = state['config'].get('temperature', 0.7)
        
        # Create generator
        generator = LLMGenerator(api_key=api_key, model_name=model_name)
        
        # Prepare context
        context_texts = [rc.chunk.text for rc in state.get('retrieved_chunks', [])]
        
        # Get structured units from CSV selector
        structured_units = state.get('structured_units', [])
        
        # Generate answer with both RAG context and structured units
        answer_text = generator.generate(
            prompt=state['query'].text,
            context=context_texts,
            structured_data=structured_units,
            temperature=temperature
        )
        
        # Create answer object
        retrieved_chunks = state.get('retrieved_chunks', [])
        answer = Answer(
            text=answer_text,
            context_chunks=retrieved_chunks,
            metadata={
                'model': model_name,
                'temperature': temperature,
                'num_context_chunks': len(retrieved_chunks),
                'num_structured_units': len(structured_units)
            }
        )
        
        logger.info("Node: generate_answer - Answer generated successfully")
        
        return {
            "answer": answer,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error generating answer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"errors": state.get('errors', []) + [error_msg]}


def select_units(state: RAGState) -> Dict[str, Any]:
    """
    Select relevant units from CSV using LLM-generated pandas code.
    Runs in parallel with retrieve_chunks.
    
    Args:
        state: Current RAG state
        
    Returns:
        Updated state with structured_units
    """
    logger.info("Node: select_units - Starting unit selection from CSV")
    
    try:
        if not state.get('query'):
            error_msg = "No query for unit selection"
            logger.error(error_msg)
            return {"errors": state.get('errors', []) + [error_msg]}
        
        # Get CSV path from config
        csv_path = state['config'].get('csv_path', 'data/11-15_sample25.csv')
        api_key = state['config'].get('gemini_api_key')
        model_name = state['config'].get('gemini_model_name', 'gemini-2.0-flash')
        
        # Create unit selector
        selector = UnitSelector(
            csv_path=csv_path,
            api_key=api_key,
            model_name=model_name
        )
        
        # Select units based on query
        query_text = state['query'].text
        selected_units = selector.select_units(query_text)
        
        logger.info(f"Node: select_units - Selected {len(selected_units)} units")
        
        return {
            "structured_units": selected_units,
            "errors": state.get('errors', [])
        }
    
    except Exception as e:
        error_msg = f"Error selecting units: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Don't fail the whole pipeline if unit selection fails
        return {
            "structured_units": [],
            "errors": state.get('errors', []) + [error_msg]
        }

