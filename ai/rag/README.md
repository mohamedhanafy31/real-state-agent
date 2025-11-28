# Real Estate Chatbot - RAG System

A Retrieval-Augmented Generation (RAG) system for Arabic real estate chatbot, built with modern NLP tools and optimized for Egyptian dialect Arabic.

## Project Structure

```
rag_project/
│
├── data/
│   ├── raw/               # Original documents (PDF, TXT, HTML…)
│   ├── processed/         # Cleaned + chunked text
│   └── embeddings/        # Saved embedding files (FAISS index, chunks)
│
├── src/
│   ├── ingestion/
│   │   ├── loader.py      # Document loading logic
│   │   ├── cleaner.py     # Text cleaning logic
│   │   └── chunker.py     # Splitting text into chunks
│   │
│   ├── embeddings/
│   │   └── embedder.py    # Embedding model wrapper (AraModernBERT)
│   │
│   ├── vector_store/
│   │   └── faiss_store.py # FAISS index logic
│   │
│   ├── retrieval/
│   │   └── retriever.py   # Search top-k chunks
│   │
│   ├── generator/
│   │   └── llm_generator.py # LLM answer generation (Gemini API)
│   │
│   ├── pipeline/
│   │   └── rag_pipeline.py   # The main orchestrator
│   │
│   └── utils/
│       └── helpers.py     # Shared functions (configs, logging…)
│
├── config/
│   └── settings.yaml       # Chunk size, embedding model, FAISS params
│
├── app/
│   ├── api.py              # FastAPI server (optional)
│   └── ui.py               # CLI or simple UI (optional)
│
├── notebooks/
│   └── exploration.ipynb   # Testing and development playground
│
├── requirements.txt
└── README.md
```

## Features

- **Document Loading**: Supports PDF, TXT, DOCX, and MD files
- **Arabic Text Processing**: Specialized cleaning and normalization for Egyptian dialect
- **Paragraph-based Chunking**: Intelligent text splitting with configurable overlap
- **Arabic Embeddings**: Uses Muffakir_Embedding_V2 (mohamed2811/Muffakir_Embedding_V2) with CUDA support
- **FAISS Vector Store**: Efficient similarity search with cosine similarity
- **Gemini API Integration**: Google's Gemini for answer generation
- **Configuration Management**: YAML-based configuration system

## Installation

1. **Clone the repository** (if applicable)

2. **Create a conda environment**:
```bash
conda create -n rag python=3.9
conda activate rag
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
# GEMINI_API_KEY=your-gemini-api-key

# Or export directly
export GEMINI_API_KEY="your-gemini-api-key"
```

## Configuration

Edit `config/settings.yaml` to customize:

- Embedding model and device (CUDA/CPU)
- Chunking parameters (min/max size, overlap)
- Retrieval settings (number of chunks to retrieve)
- LLM generator settings (model, temperature)
- Data paths

## Usage

### Basic Usage

```python
from src import RAGPipeline
from src.utils import setup_logging

# Setup logging
setup_logging(level="INFO")

# Initialize pipeline
pipeline = RAGPipeline(config_path="config/settings.yaml")

# Build index from documents
pipeline.build_index(
    data_path="data/raw",
    recursive=True,
    save_index_path="data/embeddings/index.faiss",
    save_chunks_path="data/embeddings/chunks.pkl"
)

# Query the system
response = pipeline.query(
    question="ما هي أنواع العقارات المتاحة؟",
    k=5,
    return_context=True
)

print(response['answer'])
```

### Load Existing Index

```python
pipeline = RAGPipeline(config_path="config/settings.yaml")
pipeline.load_index(
    "data/embeddings/index.faiss",
    "data/embeddings/chunks.pkl"
)
```

### Streaming Response

```python
for chunk in pipeline.query_stream(question="سؤال"):
    print(chunk, end='', flush=True)
```

## Components

### 1. Ingestion (`src/ingestion/`)

- **DocumentLoader**: Loads various file formats
- **TextCleaner**: Arabic text preprocessing and Egyptian dialect normalization
- **ParagraphChunker**: Paragraph-based text chunking

### 2. Embeddings (`src/embeddings/`)

- **AraModernBERTEmbedder**: Generates Arabic text embeddings using BERT models with CUDA support

### 3. Vector Store (`src/vector_store/`)

- **FAISSStore**: FAISS-based vector storage and similarity search

### 4. Retrieval (`src/retrieval/`)

- **Retriever**: Retrieves top-k relevant chunks for queries

### 5. Generator (`src/generator/`)

- **LLMGenerator**: Generates answers using Gemini API

### 6. Pipeline (`src/pipeline/`)

- **RAGPipeline**: Main orchestrator that combines all components

## Example

See `example_usage.py` for a complete working example.

## Requirements

- Python 3.9+
- PyTorch (with CUDA support recommended)
- Transformers
- FAISS (CPU or GPU version)
- Google Generative AI SDK
- PyYAML
- PyPDF2
- python-docx

## Notes

- The system automatically detects and uses CUDA if available
- Make sure to set the `GEMINI_API_KEY` environment variable
- Arabic text cleaning includes Egyptian dialect normalization
- The system uses paragraph-based chunking for better semantic coherence

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]

