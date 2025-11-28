"""
Example usage of the RAG system
"""

import logging
from src import RAGPipeline
from src.utils import setup_logging

# Setup logging
setup_logging(level="INFO")

def main():
    # Initialize RAG pipeline with config file
    # Make sure to set GEMINI_API_KEY environment variable
    pipeline = RAGPipeline(
        config_path="config/settings.yaml",
        # You can override config values here if needed
        # device="cuda",
        # gemini_api_key="your-api-key"
    )
    
    # Option 1: Build index from files
    print("Building index from files...")
    pipeline.build_index(
        data_path="data/raw",  # Path to your data directory or file
        recursive=True,
        save_index_path="data/embeddings/index.faiss",
        save_chunks_path="data/embeddings/chunks.pkl"
    )
    
    # Option 2: Load existing index
    # pipeline.load_index("data/embeddings/index.faiss", "data/embeddings/chunks.pkl")
    
    # Query the system
    question = "ما هي أنواع العقارات المتاحة؟"
    print(f"\nQuestion: {question}")
    
    response = pipeline.query(
        question=question,
        k=5,
        temperature=0.7,
        return_context=True
    )
    
    print(f"\nAnswer: {response['answer']}")
    print(f"\nRetrieved {len(response['context'])} context chunks")
    
    # Streaming query example
    print("\n\nStreaming response:")
    for chunk in pipeline.query_stream(question):
        print(chunk, end='', flush=True)
    print()

if __name__ == "__main__":
    main()
