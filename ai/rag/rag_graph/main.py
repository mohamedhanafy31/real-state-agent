"""
Main script demonstrating LangGraph RAG pipeline usage
"""

import os
import asyncio
from pathlib import Path

from .graph import build_ingestion_graph, build_query_graph
from .schemas import RAGState, Query
from src.utils import get_logger

# Get logger (logging should be set up by main script or API)
logger = get_logger(__name__)


async def run_ingestion(data_path: str, 
                       save_index_path: str = "data/embeddings/index.faiss",
                       save_chunks_path: str = "data/embeddings/chunks.pkl",
                       **config):
    """
    Run the ingestion pipeline.
    
    Args:
        data_path: Path to documents
        save_index_path: Path to save FAISS index
        save_chunks_path: Path to save chunks
        **config: Additional configuration
    """
    logger.info("Starting ingestion pipeline")
    
    # Build ingestion graph
    graph = build_ingestion_graph()
    
    # Prepare initial state (TypedDict)
    from .schemas import Document, CleanedDocument, Chunk, EmbeddedChunk, Query, EmbeddedQuery, RetrievedChunk, Answer
    initial_state: RAGState = {
        'documents': [],
        'cleaned_documents': [],
        'chunks': [],
        'embedded_chunks': [],
        'query': None,
        'embedded_query': None,
        'retrieved_chunks': [],
        'answer': None,
        'config': {
            'data_path': data_path,
            'recursive': True,
            'save_index_path': save_index_path,
            'save_chunks_path': save_chunks_path,
            'chunk_min_size': config.get('chunk_min_size', 100),
            'chunk_max_size': config.get('chunk_max_size', 1000),
            'chunk_overlap': config.get('chunk_overlap', 50),
            'embedder_model_name': config.get('embedder_model_name', 'mohamed2811/Muffakir_Embedding_V2'),
            'device': config.get('device', None),
            'batch_size': config.get('batch_size', 32),
            'use_sentence_transformers': config.get('use_sentence_transformers', True),
            'index_type': config.get('index_type', 'flat'),
            **config
        },
        'errors': [],
        'vector_store_path': None,
        'chunks_path': None
    }
    
    # Run the graph
    try:
        final_state = await graph.ainvoke(initial_state)
        
        # Handle both dict and object state
        errors = final_state.get('errors', []) if isinstance(final_state, dict) else getattr(final_state, 'errors', [])
        if errors:
            logger.error(f"Ingestion completed with errors: {errors}")
        else:
            logger.info("Ingestion completed successfully")
            chunks = final_state.get('chunks', []) if isinstance(final_state, dict) else getattr(final_state, 'chunks', [])
            embedded_chunks = final_state.get('embedded_chunks', []) if isinstance(final_state, dict) else getattr(final_state, 'embedded_chunks', [])
            logger.info(f"Created {len(chunks)} chunks")
            logger.info(f"Embedded {len(embedded_chunks)} chunks")
        
        return final_state
    
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}", exc_info=True)
        raise


async def run_query(question: str,
                   index_path: str = "data/embeddings/index.faiss",
                   chunks_path: str = "data/embeddings/chunks.pkl",
                   embedder=None,
                   embedding_dim=None,
                   **config):
    """
    Run the query pipeline.
    
    Args:
        question: User question
        index_path: Path to FAISS index
        chunks_path: Path to chunks file
        embedder: Preloaded embedder instance (optional)
        embedding_dim: Embedding dimension (optional, inferred from embedder if provided)
        **config: Additional configuration
        
    Returns:
        Generated answer
    """
    logger.info(f"Starting query pipeline for: {question}")
    
    # Build query graph
    graph = build_query_graph()
    
    # Use provided embedder and dimension, or infer from config
    if embedder is not None:
        logger.info("Using preloaded embedder")
        if embedding_dim is None:
            embedding_dim = embedder.get_embedding_dim()
    else:
        # Load embedding dimension from config or use default
        # Embedding dimension will be auto-detected from model if not provided
        # Muffakir_Embedding_V2 has dimension 1024
        if embedding_dim is None:
            embedding_dim = config.get('embedding_dim', None)
            # If still None, we'll need to load the embedder to get the dimension
            if embedding_dim is None:
                from src.embeddings import AraModernBERTEmbedder
                from src.utils import get_config_value
                temp_embedder = AraModernBERTEmbedder(
                    model_name=get_config_value(config, 'embedding.model_name', 'mohamed2811/Muffakir_Embedding_V2'),
                    device=get_config_value(config, 'embedding.device', None),
                    use_sentence_transformers=get_config_value(config, 'embedding.use_sentence_transformers', True)
                )
                embedding_dim = temp_embedder.get_embedding_dim()
                logger.info(f"Auto-detected embedding dimension: {embedding_dim}")
    
    # Prepare initial state (TypedDict)
    from .schemas import Document, CleanedDocument, Chunk, EmbeddedChunk, Query, EmbeddedQuery, RetrievedChunk, Answer
    initial_state: RAGState = {
        'documents': [],
        'cleaned_documents': [],
        'chunks': [],
        'embedded_chunks': [],
        'query': Query(text=question),
        'embedded_query': None,
        'retrieved_chunks': [],
        'answer': None,
        'config': {
            'load_index_path': index_path,
            'load_chunks_path': chunks_path,
            'embedding_dim': embedding_dim,
            'embedder': embedder,  # Pass preloaded embedder if available
            'retrieval_k': config.get('retrieval_k', 5),
            'gemini_api_key': config.get('gemini_api_key') or os.getenv('GEMINI_API_KEY'),
            'gemini_model_name': config.get('gemini_model_name', 'gemini-2.0-flash'),
            'temperature': config.get('temperature', 0.7),
            'clean_query': config.get('clean_query', True),
            **config
        },
        'errors': [],
        'vector_store_path': index_path,
        'chunks_path': chunks_path
    }
    
    # Run the graph
    try:
        final_state = await graph.ainvoke(initial_state)
        
        # Handle both dict and object state
        errors = final_state.get('errors', []) if isinstance(final_state, dict) else getattr(final_state, 'errors', [])
        if errors:
            logger.error(f"Query completed with errors: {errors}")
            return None
        
        # Handle both dict and object state
        answer = final_state.get('answer') if isinstance(final_state, dict) else getattr(final_state, 'answer', None)
        if answer:
            logger.info("Query completed successfully")
            return answer
        else:
            logger.warning("No answer generated")
            return None
    
    except Exception as e:
        logger.error(f"Error during query: {str(e)}", exc_info=True)
        raise


async def main():
    """Main function demonstrating full workflow."""
    
    # Example 1: Run ingestion
    print("\n" + "="*50)
    print("Example 1: Running Ingestion Pipeline")
    print("="*50)
    
    data_path = "data/raw"
    if not Path(data_path).exists():
        print(f"Warning: {data_path} does not exist. Skipping ingestion.")
    else:
        try:
            final_state = await run_ingestion(
                data_path=data_path,
                save_index_path="data/embeddings/index.faiss",
                save_chunks_path="data/embeddings/chunks.pkl",
                device="cpu"  # Use CPU for testing
            )
            print(f"\nIngestion completed!")
            print(f"- Documents loaded: {len(final_state.documents)}")
            print(f"- Chunks created: {len(final_state.chunks)}")
            print(f"- Embeddings generated: {len(final_state.embedded_chunks)}")
        except Exception as e:
            print(f"Error during ingestion: {str(e)}")
    
    # Example 2: Run query
    print("\n" + "="*50)
    print("Example 2: Running Query Pipeline")
    print("="*50)
    
    if not os.getenv('GEMINI_API_KEY'):
        print("Warning: GEMINI_API_KEY not set. Skipping query example.")
    else:
        try:
            question = "ما هي أنواع العقارات المتاحة؟"
            answer = await run_query(
                question=question,
                index_path="data/embeddings/index.faiss",
                chunks_path="data/embeddings/chunks.pkl",
                retrieval_k=5,
                temperature=0.7
            )
            
            if answer:
                print(f"\nQuestion: {question}")
                print(f"\nAnswer: {answer.text}")
                print(f"\nContext chunks used: {len(answer.context_chunks)}")
                if answer.context_chunks:
                    print(f"Top chunk score: {answer.context_chunks[0].score:.4f}")
        except Exception as e:
            print(f"Error during query: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())

