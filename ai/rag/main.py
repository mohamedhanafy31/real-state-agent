"""
Main entry point for LangGraph RAG system
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars

from rag_graph.main import run_ingestion, run_query
from src.utils import setup_run_logging, get_logger, get_run_logger

# Setup run-based logging
run_logger = setup_run_logging(
    run_name=f"main_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    log_dir=os.getenv('LOG_DIR', 'logs'),
    level=os.getenv('LOG_LEVEL', 'INFO'),
    console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
    file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
)

logger = get_logger(__name__)

# Log run information
run_logger.log_run_info({
    'run_name': run_logger.run_name,
    'start_time': datetime.now().isoformat(),
    'log_directory': str(run_logger.log_dir.absolute()),
    'log_files': {k: str(v) for k, v in run_logger.get_log_paths().items()}
})


async def main():
    """Main function for running RAG pipeline."""
    
    print("="*60)
    print("LangGraph RAG System")
    print("="*60)
    
    # Check if index exists
    index_path = Path("data/embeddings/index.faiss")
    chunks_path = Path("data/embeddings/chunks.pkl")
    
    # Step 1: Build index if it doesn't exist
    if not index_path.exists() or not chunks_path.exists():
        print("\n[Step 1] Building index from documents...")
        data_path = "data/raw"
        
        if not Path(data_path).exists():
            print(f"Error: {data_path} does not exist!")
            print("Please place your documents in the data/raw/ directory.")
            return
        
        try:
            final_state = await run_ingestion(
                data_path=data_path,
                save_index_path=str(index_path),
                save_chunks_path=str(chunks_path),
                device="cuda"  # Use CUDA if available, falls back to CPU
            )
            
            if final_state.errors:
                print(f"\nErrors occurred: {final_state.errors}")
                return
            
            print(f"\n✓ Index built successfully!")
            print(f"  - Documents: {len(final_state.documents)}")
            print(f"  - Chunks: {len(final_state.chunks)}")
            print(f"  - Embeddings: {len(final_state.embedded_chunks)}")
        
        except Exception as e:
            logger.error(f"Error building index: {str(e)}", exc_info=True)
            return
    else:
        print("\n[Step 1] Index already exists, skipping ingestion.")
    
    # Step 2: Query the system
    print("\n[Step 2] Querying the system...")
    
    import os
    if not os.getenv('GEMINI_API_KEY'):
        print("Warning: GEMINI_API_KEY not set. Cannot generate answers.")
        print("Set it with: export GEMINI_API_KEY='your-key'")
        print("\nYou can still test the retrieval without generation.")
        print("Skipping query step.")
        return
    
    # Example queries
    queries = [
        "ما هي أنواع العقارات المتاحة؟",
        "ما هي الخدمات المقدمة؟",
    ]
    
    for query_text in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query_text}")
        print('='*60)
        
        try:
            answer = await run_query(
                question=query_text,
                index_path=str(index_path),
                chunks_path=str(chunks_path),
                retrieval_k=5,
                temperature=0.7
            )
            
            if answer:
                print(f"\nAnswer:\n{answer.text}")
                print(f"\nContext: {len(answer.context_chunks)} chunks retrieved")
                if answer.context_chunks:
                    print(f"Top similarity: {answer.context_chunks[0].score:.4f}")
            else:
                print("No answer generated.")
        
        except Exception as e:
            logger.error(f"Error querying: {str(e)}", exc_info=True)
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())

