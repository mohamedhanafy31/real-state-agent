# RAG System - Complete Overview

## 🎯 System Purpose

A **Retrieval-Augmented Generation (RAG)** system for an Arabic real estate chatbot that combines:
- **Document-based RAG**: Semantic search through uploaded documents (PDF, DOCX, TXT, MD)
- **Structured Data Selector**: LLM-generated pandas code to query CSV data
- **LLM Generation**: Google Gemini API for answer generation in Egyptian Arabic

---

## 🏗️ Architecture Overview

### Technology Stack
- **LangGraph**: State machine orchestration for the RAG pipeline
- **LangChain**: LLM/embedding integrations
- **FastAPI**: REST API server with streaming support
- **FAISS**: Vector similarity search (GPU-accelerated)
- **Sentence-Transformers**: Arabic BERT embeddings (Muffakir_Embedding_V2)
- **Gemini API**: LLM for answer generation and code generation
- **PyTorch**: Deep learning framework with CUDA support

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG System Architecture                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐
│  FastAPI     │  ← REST API + Web UI
│  (app/api.py)│
└──────┬───────┘
       │
       ├──► LangGraph Pipeline (rag_graph/)
       │    ├── Ingestion Graph
       │    └── Query Graph
       │
       ├──► Components (src/)
       │    ├── ingestion/     (Loader, Cleaner, Chunker)
       │    ├── embeddings/    (AraModernBERTEmbedder)
       │    ├── vector_store/  (FAISSStore)
       │    ├── retrieval/     (Retriever)
       │    ├── selector/      (UnitSelector - CSV query)
       │    ├── generator/     (LLMGenerator - Gemini)
       │    └── memory/        (ChatMemory - Session history)
       │
       └──► Data Storage
            ├── data/raw/          (Uploaded documents)
            ├── data/embeddings/   (FAISS index + chunks.pkl)
            └── data/11-15_sample25.csv (Structured unit data)
```

---

## 📊 System Flow

### Phase 1: Ingestion Pipeline (Building the Index)

**Purpose**: Transform raw documents into a searchable vector index

**Flow**:
```
Documents (PDF/DOCX/TXT/MD)
    ↓
[1] load_documents
    └─► DocumentLoader
        • Reads files from data/raw/
        • Extracts text + metadata
        • Returns: List[Document]
    ↓
[2] clean_text
    └─► TextCleaner
        • Removes Arabic diacritics (تشكيل)
        • Normalizes Egyptian Arabic
        • Removes Tatweel (ـ)
        • Returns: List[CleanedDocument]
    ↓
[3] chunk_documents
    └─► ParagraphChunker
        • Splits into chunks (100-1000 chars)
        • Paragraph-aware splitting
        • 50 char overlap between chunks
        • Returns: List[Chunk]
    ↓
[4] embed_chunks
    └─► AraModernBERTEmbedder
        • Model: mohamed2811/Muffakir_Embedding_V2
        • 1024-dimensional embeddings
        • Batch processing (32 chunks/batch)
        • CUDA/CPU support
        • Returns: List[EmbeddedChunk]
    ↓
[5] store_embeddings
    └─► FAISSStore
        • Creates FAISS index (IndexFlatL2)
        • Normalizes for cosine similarity
        • Saves: index.faiss + chunks.pkl
        • Returns: Saved file paths
```

**Output Files**:
- `data/embeddings/index.faiss`: Binary FAISS vector index
- `data/embeddings/chunks.pkl`: Pickled chunk texts and metadata

---

### Phase 2: Query Pipeline (Answering Questions)

**Purpose**: Answer user questions using the index and structured data

**Flow**:
```
User Query (Arabic/English)
    ↓
[1] embed_query
    └─► AraModernBERTEmbedder
        • Same model as ingestion
        • Cleans query text
        • Generates 1024-dim embedding
        • Returns: EmbeddedQuery
    ↓
    ├──────────────────────┐
    │                      │
    ▼                      ▼
[2a] retrieve_chunks   [2b] select_units
    └─► Retriever          └─► UnitSelector
        • Load FAISS index     • Load CSV file
        • Vector similarity    • Generate pandas code (Gemini)
        • Top-K chunks (k=5)   • Execute code safely
        • Returns:              • Returns:
          List[RetrievedChunk]    List[Dict] (unit data)
    │                      │
    │    (Parallel)        │
    └──────────┬───────────┘
               │
               ▼
[3] generate_answer
    └─► LLMGenerator (Gemini)
        • Builds prompt with:
          - User question
          - RAG context (retrieved chunks)
          - Structured units (from CSV)
          - Conversation history
        • Generates answer (Egyptian Arabic)
        • Streaming support (SSE)
        • Returns: Answer
    ↓
Final Response
```

**Key Features**:
- **Parallel Processing**: Retrieval and unit selection run simultaneously
- **Dual Source**: Combines document RAG + structured CSV data
- **Conversation Memory**: Maintains chat history per session
- **Streaming**: Real-time answer generation

---

## 🔧 Component Details

### 1. Document Loader (`src/ingestion/loader.py`)
- **Supports**: PDF, DOCX, TXT, MD files
- **Features**: Recursive directory loading, metadata extraction
- **Output**: `Document` objects with content + metadata

### 2. Text Cleaner (`src/ingestion/cleaner.py`)
- **Operations**:
  - Removes Arabic diacritics: `شَرِكَة` → `شركة`
  - Normalizes Egyptian Arabic: `إيه` → `ايه`
  - Removes Tatweel: `كـتاب` → `كتاب`
- **Purpose**: Standardize text for better embedding quality

### 3. Paragraph Chunker (`src/ingestion/chunker.py`)
- **Strategy**: Paragraph-aware splitting
- **Parameters**:
  - Min size: 100 chars
  - Max size: 1000 chars
  - Overlap: 50 chars
- **Purpose**: Preserve semantic boundaries while creating searchable chunks

### 4. Arabic Embedder (`src/embeddings/embedder.py`)
- **Model**: `mohamed2811/Muffakir_Embedding_V2`
- **Type**: Sentence-transformers compatible Arabic BERT
- **Dimensions**: 1024
- **Features**:
  - CUDA acceleration (auto-detects GPU)
  - Batch processing (32 items/batch)
  - Caching (loaded once at API startup)

### 5. FAISS Vector Store (`src/vector_store/faiss_store.py`)
- **Index Type**: `IndexFlatL2` (exact search)
- **Similarity**: Cosine similarity (via L2 on normalized vectors)
- **Features**:
  - Persistent storage (save/load)
  - Fast similarity search
  - Supports millions of vectors

### 6. Retriever (`src/retrieval/retriever.py`)
- **Process**:
  1. Loads FAISS index from disk
  2. Loads chunks.pkl
  3. Performs vector similarity search
  4. Returns top-K most similar chunks with scores

### 7. Unit Selector (`src/selector/unit_selector.py`)
- **Purpose**: Query structured CSV data using LLM-generated pandas code
- **Process**:
  1. Analyzes user query
  2. Generates pandas filtering code using Gemini
  3. Executes code in sandboxed environment
  4. Returns matching CSV rows as dictionaries
- **Safety Features**:
  - Blocks dangerous operations (eval, exec, file I/O)
  - Validates code before execution
  - Handles errors gracefully
  - Relevance scoring (filters non-CSV queries)
- **Example Generated Code**:
  ```python
  selected_units = df[df['Area'] == 150].head(50)
  ```

### 8. LLM Generator (`src/generator/llm_generator.py`)
- **Model**: Gemini 2.0 Flash
- **Features**:
  - Egyptian Arabic generation
  - Streaming responses (SSE)
  - Conversation context integration
  - Temperature control (default: 0.7)

### 9. Chat Memory (`src/memory/chat_memory.py`)
- **Type**: BufferWindowMemory
- **Features**:
  - Session-based storage
  - Max 20 messages per session
  - In-memory storage (per API instance)

---

## 📁 Project Structure

```
ai/rag/
├── app/
│   ├── api.py              # FastAPI server (main entry point)
│   ├── ui.py               # CLI interface
│   └── static/
│       ├── index.html      # Web UI
│       └── selector_test.html
│
├── rag_graph/              # LangGraph pipeline
│   ├── graph.py            # Graph builder
│   ├── main.py             # Pipeline runners
│   ├── schemas.py          # Data schemas (RAGState, etc.)
│   └── nodes/
│       ├── ingestion_nodes.py  # Ingestion pipeline nodes
│       └── query_nodes.py      # Query pipeline nodes
│
├── src/                    # Core components
│   ├── ingestion/
│   │   ├── loader.py       # DocumentLoader
│   │   ├── cleaner.py      # TextCleaner
│   │   └── chunker.py      # ParagraphChunker
│   │
│   ├── embeddings/
│   │   └── embedder.py     # AraModernBERTEmbedder
│   │
│   ├── vector_store/
│   │   └── faiss_store.py  # FAISSStore
│   │
│   ├── retrieval/
│   │   └── retriever.py    # Retriever
│   │
│   ├── selector/
│   │   └── unit_selector.py # UnitSelector
│   │
│   ├── generator/
│   │   └── llm_generator.py # LLMGenerator
│   │
│   ├── memory/
│   │   └── chat_memory.py  # ChatMemory
│   │
│   └── utils/
│       ├── helpers.py      # Config utilities
│       └── logger.py       # Logging setup
│
├── config/
│   └── settings.yaml       # Configuration file
│
├── data/
│   ├── raw/                # Uploaded documents
│   ├── embeddings/         # FAISS index + chunks
│   └── 11-15_sample25.csv  # Structured unit data
│
├── main.py                 # CLI entry point
├── run.py                  # Run script (api/ingest/query)
├── requirements.txt        # Dependencies
└── README.md               # Documentation
```

---

## 🔄 State Management (LangGraph)

### RAGState Structure

```python
class RAGState(TypedDict):
    # Ingestion state
    documents: List[Document]
    cleaned_documents: List[CleanedDocument]
    chunks: List[Chunk]
    embedded_chunks: List[EmbeddedChunk]
    
    # Query state
    query: Optional[Query]
    embedded_query: Optional[EmbeddedQuery]
    retrieved_chunks: List[RetrievedChunk]
    structured_units: List[Dict[str, Any]]  # From CSV selector
    answer: Optional[Answer]
    
    # Configuration and metadata
    config: Dict[str, Any]
    errors: List[str]
    vector_store_path: Optional[str]
    chunks_path: Optional[str]
```

### State Reducer

When multiple nodes run in parallel (e.g., `retrieve_chunks` and `select_units`), the reducer merges their state updates:
- Lists are replaced (nodes return complete lists)
- Dicts are merged
- Other values are replaced

---

## 🌐 API Endpoints

### Health & Status
- `GET /health` - Quick health check
- `GET /health/detailed` - Detailed system status

### Document Management
- `GET /documents` - List all documents
- `POST /documents/upload` - Upload document (auto-rebuilds index)
- `DELETE /documents/{filename}` - Delete document
- `DELETE /documents` - Clear all documents

### Index Management
- `POST /ingest` - Build/rebuild FAISS index

### Query
- `POST /query` - Query system (non-streaming)
- `POST /query/stream` - Query system (streaming SSE)

### Chat Management
- `POST /chat/clear` - Clear conversation history
- `GET /chat/history` - Get conversation history

### Selector Testing
- `POST /selector/test` - Test UnitSelector independently
- `GET /selector/test/ui` - Selector test UI

---

## ⚙️ Configuration

Key settings in `config/settings.yaml`:

```yaml
embedding:
  model_name: "mohamed2811/Muffakir_Embedding_V2"
  device: "cuda"  # Auto-detects if null
  batch_size: 32

chunking:
  min_chunk_size: 100
  max_chunk_size: 1000
  overlap: 50

retrieval:
  k: 5  # Number of chunks to retrieve

generator:
  model_name: "gemini-2.0-flash"
  temperature: 0.7

memory:
  max_messages: 20
```

**Environment Variables**:
- `GEMINI_API_KEY` - Required for query and selector
- `HOST`, `PORT` - API server settings
- `LOG_DIR`, `LOG_LEVEL` - Logging configuration

---

## 🚀 Usage Examples

### 1. Start API Server
```bash
cd ai/rag
python run.py api
# Or: python -m uvicorn app.api:app --reload
```

### 2. Build Index
```bash
# Via API
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"data_path": "data/raw"}'

# Via CLI
python run.py ingest --data-path data/raw
```

### 3. Query System
```bash
# Via API
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ما هي أنواع الشقق المتاحة؟",
    "session_id": "user123"
  }'

# Via CLI
python run.py query "ما هي أنواع الشقق المتاحة؟"
```

### 4. Upload Document
```bash
curl -X POST "http://localhost:8000/documents/upload?rebuild_index=true" \
  -F "file=@document.pdf"
```

---

## 🔍 Key Design Decisions

1. **Same Embedding Model**: Query and documents use the same model for accurate similarity
2. **Paragraph-Aware Chunking**: Preserves semantic boundaries
3. **Overlap Between Chunks**: Ensures context isn't lost at boundaries
4. **Dual Source**: Combines document RAG + structured CSV data
5. **Parallel Processing**: Retrieval and selection run simultaneously
6. **Graceful Degradation**: System works even if selector fails
7. **State-Based Architecture**: LangGraph enables complex workflows
8. **Relevance Scoring**: UnitSelector filters non-CSV queries automatically

---

## 📝 Data Flow Example

**User Query**: "ما هي أنواع الشقق المتاحة؟" (What types of apartments are available?)

1. **Query Embedding**: Query → 1024-dim vector
2. **Parallel Execution**:
   - **RAG Retrieval**: Search FAISS → Top 5 document chunks
   - **CSV Selector**: Generate pandas code → Filter CSV → Get matching units
3. **Answer Generation**:
   - Build prompt with: query + RAG chunks + CSV units + history
   - Send to Gemini
   - Generate answer in Egyptian Arabic
4. **Response**: Return answer + metadata (chunks, units, scores)

---

## 🎯 Performance Optimizations

1. **Model Caching**: Embedding model loaded once at API startup
2. **Batch Processing**: Chunks embedded in batches (32 at a time)
3. **CUDA Support**: GPU acceleration for embeddings
4. **Index Caching**: FAISS index loaded on-demand and reused
5. **Parallel Processing**: Retrieval and selection run simultaneously
6. **Streaming**: Real-time answer generation for better UX

---

## 🔐 Security Features

1. **Code Sandboxing**: UnitSelector blocks dangerous operations
2. **Input Validation**: API endpoints validate inputs
3. **Error Handling**: Graceful error handling throughout
4. **Relevance Filtering**: Low-relevance queries return empty results

---

## 📚 Additional Resources

- `README.md` - Installation and basic usage
- `RAG_PIPELINE_EXPLAINED.md` - Detailed pipeline explanation
- `API_DOCUMENTATION.md` - Complete API reference
- `SYSTEM_FLOW.txt` - ASCII flow diagrams

---

**Last Updated**: 2025-01-27

