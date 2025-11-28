# LangGraph RAG System

This directory contains the LangGraph-based orchestration layer for the RAG system.

## Structure

```
rag_graph/
├── __init__.py           # Package exports
├── schemas.py            # Data schemas (dataclasses and TypedDict)
├── graph.py              # Graph builder functions
├── main.py               # Example usage
├── nodes/
│   ├── __init__.py
│   ├── ingestion_nodes.py  # Load, clean, chunk, embed, store nodes
│   └── query_nodes.py      # Embed query, retrieve, generate nodes
└── README.md
```

## Architecture

The RAG pipeline is implemented as a LangGraph workflow with two main flows:

### Ingestion Flow
```
load_documents → clean_text → chunk_documents → embed_chunks → store_embeddings
```

### Query Flow
```
embed_query → retrieve_chunks → generate_answer
```

## Usage

### Basic Usage

```python
from rag_graph.main import run_ingestion, run_query
import asyncio

# Run ingestion
async def main():
    # Build index
    state = await run_ingestion(
        data_path="data/raw",
        save_index_path="data/embeddings/index.faiss",
        save_chunks_path="data/embeddings/chunks.pkl"
    )
    
    # Query
    answer = await run_query(
        question="ما هي أنواع العقارات؟",
        index_path="data/embeddings/index.faiss",
        chunks_path="data/embeddings/chunks.pkl"
    )
    print(answer.text)

asyncio.run(main())
```

### Using the Graph Directly

```python
from rag_graph.graph import build_ingestion_graph, build_query_graph
from rag_graph.schemas import RAGState, Query
import asyncio

async def main():
    # Build ingestion graph
    ingestion_graph = build_ingestion_graph()
    
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
            'data_path': 'data/raw',
            'save_index_path': 'data/embeddings/index.faiss',
            'save_chunks_path': 'data/embeddings/chunks.pkl',
        },
        'errors': [],
        'vector_store_path': None,
        'chunks_path': None
    }
    
    final_state = await ingestion_graph.ainvoke(initial_state)
    print(f"Created {len(final_state['chunks'])} chunks")

asyncio.run(main())
```

## Nodes

### Ingestion Nodes

- **load_documents**: Loads documents from file or directory
- **clean_text**: Cleans and normalizes Arabic text
- **chunk_documents**: Splits documents into chunks
- **embed_chunks**: Generates embeddings for chunks
- **store_embeddings**: Stores embeddings in FAISS vector store

### Query Nodes

- **embed_query**: Embeds the user query
- **retrieve_chunks**: Retrieves relevant chunks from vector store
- **generate_answer**: Generates answer using LLM

## State Schema

The `RAGState` TypedDict contains:

- `documents`: List of loaded documents
- `cleaned_documents`: List of cleaned documents
- `chunks`: List of text chunks
- `embedded_chunks`: List of chunks with embeddings
- `query`: User query
- `embedded_query`: Query with embedding
- `retrieved_chunks`: Retrieved chunks with scores
- `answer`: Generated answer
- `config`: Configuration dictionary
- `errors`: List of error messages
- `vector_store_path`: Path to saved index
- `chunks_path`: Path to saved chunks

## Error Handling

Each node includes error handling and logs errors to the state's `errors` list. The graph continues execution even if individual nodes fail, allowing for graceful degradation.

## Async Support

All graph execution is async. Use `await graph.ainvoke(state)` or `await graph.astream(state)` for streaming.

