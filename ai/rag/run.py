#!/usr/bin/env python3
"""
Run script for RAG Chatbot System
Provides a convenient entry point to run different components of the system.
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """Run the FastAPI server."""
    import uvicorn
    from src.utils import setup_run_logging, get_logger
    from datetime import datetime
    
    # Setup logging
    run_logger = setup_run_logging(
        run_name=f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        log_dir=os.getenv('LOG_DIR', 'logs'),
        level=os.getenv('LOG_LEVEL', 'INFO'),
        console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
        file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
    )
    
    logger = get_logger(__name__)
    logger.info(f"Starting FastAPI server on {host}:{port}")
    logger.info(f"Reload enabled: {reload}")
    
    uvicorn.run(
        "app.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )


async def run_main():
    """Run the main RAG pipeline."""
    from main import main
    await main()


def run_ingestion(data_path: str = "data/raw", **kwargs):
    """Run only the ingestion pipeline."""
    async def _run():
        from rag_graph.main import run_ingestion
        from src.utils import setup_run_logging, get_logger, get_run_logger
        from datetime import datetime
        
        # Setup logging
        run_logger = setup_run_logging(
            run_name=f"ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            log_dir=os.getenv('LOG_DIR', 'logs'),
            level=os.getenv('LOG_LEVEL', 'INFO'),
            console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
            file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
        )
        
        logger = get_logger(__name__)
        logger.info(f"Starting ingestion from: {data_path}")
        
        # Log run info
        run_logger.log_run_info({
            'run_type': 'ingestion',
            'data_path': data_path,
            'start_time': datetime.now().isoformat()
        })
        
        # Run ingestion
        final_state = await run_ingestion(
            data_path=data_path,
            save_index_path=kwargs.get('save_index_path', 'data/embeddings/index.faiss'),
            save_chunks_path=kwargs.get('save_chunks_path', 'data/embeddings/chunks.pkl'),
            device=kwargs.get('device', 'cuda'),
            chunk_min_size=kwargs.get('chunk_min_size', 100),
            chunk_max_size=kwargs.get('chunk_max_size', 1000),
            chunk_overlap=kwargs.get('chunk_overlap', 50)
        )
        
        if final_state.get('errors'):
            logger.error(f"Ingestion completed with errors: {final_state.get('errors')}")
            return 1
        
        logger.info("Ingestion completed successfully")
        logger.info(f"Documents: {len(final_state.get('documents', []))}")
        logger.info(f"Chunks: {len(final_state.get('chunks', []))}")
        logger.info(f"Embeddings: {len(final_state.get('embedded_chunks', []))}")
        return 0
    
    return asyncio.run(_run())


def run_query(question: str, **kwargs):
    """Run a single query."""
    async def _run():
        from rag_graph.main import run_query
        from src.utils import setup_run_logging, get_logger
        from datetime import datetime
        
        # Setup logging
        run_logger = setup_run_logging(
            run_name=f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            log_dir=os.getenv('LOG_DIR', 'logs'),
            level=os.getenv('LOG_LEVEL', 'INFO'),
            console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
            file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
        )
        
        logger = get_logger(__name__)
        logger.info(f"Processing query: {question}")
        
        # Check API key
        if not os.getenv('GEMINI_API_KEY'):
            logger.error("GEMINI_API_KEY not set. Cannot generate answers.")
            print("Error: GEMINI_API_KEY environment variable not set.")
            print("Set it with: export GEMINI_API_KEY='your-key'")
            return 1
        
        # Run query
        answer = await run_query(
            question=question,
            index_path=kwargs.get('index_path', 'data/embeddings/index.faiss'),
            chunks_path=kwargs.get('chunks_path', 'data/embeddings/chunks.pkl'),
            retrieval_k=kwargs.get('retrieval_k', 5),
            temperature=kwargs.get('temperature', 0.7)
        )
        
        if not answer:
            logger.error("Failed to generate answer")
            return 1
        
        print("\n" + "="*60)
        print(f"Question: {question}")
        print("="*60)
        print(f"\nAnswer:\n{answer.text}")
        print(f"\nContext: {len(answer.context_chunks)} chunks retrieved")
        if answer.context_chunks:
            print(f"Top similarity: {answer.context_chunks[0].score:.4f}")
        print("="*60 + "\n")
        
        return 0
    
    return asyncio.run(_run())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RAG Chatbot System - Run different components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run API server
  python run.py api
  
  # Run API server on custom port
  python run.py api --port 8080
  
  # Run main pipeline
  python run.py main
  
  # Run ingestion only
  python run.py ingest --data-path data/raw
  
  # Run a query
  python run.py query "ما هي أنواع العقارات المتاحة؟"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # API command
    api_parser = subparsers.add_parser('api', help='Run FastAPI server')
    api_parser.add_argument('--host', default=os.getenv('HOST', '0.0.0.0'), help='Host to bind to')
    api_parser.add_argument('--port', type=int, default=int(os.getenv('PORT', 8000)), help='Port to bind to')
    api_parser.add_argument('--no-reload', action='store_true', help='Disable auto-reload')
    
    # Main command
    main_parser = subparsers.add_parser('main', help='Run main RAG pipeline')
    
    # Ingestion command
    ingest_parser = subparsers.add_parser('ingest', help='Run ingestion pipeline only')
    ingest_parser.add_argument('--data-path', default='data/raw', help='Path to documents')
    ingest_parser.add_argument('--index-path', default='data/embeddings/index.faiss', help='Path to save index')
    ingest_parser.add_argument('--chunks-path', default='data/embeddings/chunks.pkl', help='Path to save chunks')
    ingest_parser.add_argument('--device', default='cuda', help='Device to use (cuda/cpu)')
    ingest_parser.add_argument('--chunk-min-size', type=int, default=100, help='Minimum chunk size')
    ingest_parser.add_argument('--chunk-max-size', type=int, default=1000, help='Maximum chunk size')
    ingest_parser.add_argument('--chunk-overlap', type=int, default=50, help='Chunk overlap')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Run a single query')
    query_parser.add_argument('question', help='Question to ask')
    query_parser.add_argument('--index-path', default='data/embeddings/index.faiss', help='Path to index')
    query_parser.add_argument('--chunks-path', default='data/embeddings/chunks.pkl', help='Path to chunks')
    query_parser.add_argument('--retrieval-k', type=int, default=5, help='Number of chunks to retrieve')
    query_parser.add_argument('--temperature', type=float, default=0.7, help='Temperature for generation')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'api':
            run_api(
                host=args.host,
                port=args.port,
                reload=not args.no_reload
            )
        elif args.command == 'main':
            asyncio.run(run_main())
        elif args.command == 'ingest':
            return run_ingestion(
                data_path=args.data_path,
                save_index_path=args.index_path,
                save_chunks_path=args.chunks_path,
                device=args.device,
                chunk_min_size=args.chunk_min_size,
                chunk_max_size=args.chunk_max_size,
                chunk_overlap=args.chunk_overlap
            )
        elif args.command == 'query':
            return run_query(
                question=args.question,
                index_path=args.index_path,
                chunks_path=args.chunks_path,
                retrieval_k=args.retrieval_k,
                temperature=args.temperature
            )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\nError: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

