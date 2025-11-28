# Complete RAG Pipeline Explanation

## 📚 Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Phase 1: Ingestion Pipeline](#phase-1-ingestion-pipeline)
4. [Phase 2: Query Pipeline](#phase-2-query-pipeline)
5. [Components Deep Dive](#components-deep-dive)
6. [Data Flow](#data-flow)
7. [State Management](#state-management)

---

## 🎯 Overview

The RAG (Retrieval-Augmented Generation) pipeline is built using **LangGraph**, a framework for building stateful, multi-actor applications with LLMs. The pipeline consists of two main phases:

1. **Ingestion Phase**: Processes documents and builds a searchable index
2. **Query Phase**: Answers user questions using the index and structured data

---

## 🏗️ Architecture

### LangGraph State Machine

The pipeline uses a **StateGraph** where:
- **Nodes** = Processing steps (functions)
- **Edges** = Data flow between nodes
- **State** = Shared data structure (`RAGState`) passed between nodes
- **Reducer** = Function that merges state updates from parallel nodes

```
┌─────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                  │
│                                                          │
│  Nodes (Processing Steps)                               │
│  ├─ load_documents                                      │
│  ├─ clean_text                                          │
│  ├─ chunk_documents                                     │
│  ├─ embed_chunks                                        │
│  ├─ store_embeddings                                    │
│  ├─ embed_query                                         │
│  ├─ retrieve_chunks                                     │
│  ├─ select_units                                        │
│  └─ generate_answer                                     │
│                                                          │
│  State: RAGState (TypedDict)                            │
│  ├─ documents: List[Document]                           │
│  ├─ cleaned_documents: List[CleanedDocument]            │
│  ├─ chunks: List[Chunk]                                 │
│  ├─ embedded_chunks: List[EmbeddedChunk]                │
│  ├─ query: Query                                        │
│  ├─ embedded_query: EmbeddedQuery                       │
│  ├─ retrieved_chunks: List[RetrievedChunk]              │
│  ├─ structured_units: List[Dict]                        │
│  ├─ answer: Answer                                      │
│  ├─ config: Dict                                        │
│  └─ errors: List[str]                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 📥 Phase 1: Ingestion Pipeline

**Purpose**: Transform raw documents into a searchable vector index

### Flow Diagram

```
┌─────────────────┐
│ Raw Documents   │
│ (PDF/DOCX/TXT)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 1. Load Docs    │ ◄─── DocumentLoader
│    • Read files │      • Supports: PDF, DOCX, TXT, MD
│    • Extract    │      • Returns: content + metadata
│      content    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Clean Text   │ ◄─── TextCleaner
│    • Remove     │      • remove_diacritics: true
│      diacritics │      • normalize_egyptian: true
│    • Normalize  │      • remove_tatweel: true
│      Arabic     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Chunk Docs   │ ◄─── ParagraphChunker
│    • Split into │      • min_chunk_size: 100
│      chunks     │      • max_chunk_size: 1000
│    • Add        │      • overlap: 50
│      metadata   │      • Preserves paragraph boundaries
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. Embed Chunks │ ◄─── AraModernBERTEmbedder
│    • Generate   │      • Model: mohamed2811/Muffakir_Embedding_V2
│      vectors    │      • Dimension: 1024
│    • Batch      │      • Batch size: 32
│      processing │      • Device: CUDA/CPU
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. Store Index  │ ◄─── FAISSStore
│    • Save to    │      • index.faiss: Vector index
│      FAISS      │      • chunks.pkl: Text + metadata
│    • Save       │      • Index type: FlatL2
│      chunks     │      • Normalized for cosine similarity
└─────────────────┘
```

### Step-by-Step Details

#### Node 1: `load_documents`
**Component**: `DocumentLoader`

**Process**:
1. Reads files from `data/raw/` directory
2. Supports: PDF, DOCX, TXT, MD
3. Extracts text content
4. Collects metadata (filename, size, path)

**Output**: `List[Document]` with content and metadata

**Example**:
```python
Document(
    content="شركة بانٍ للتطوير العقاري...",
    metadata={
        "file_name": "bany_profile.docx",
        "file_path": "data/raw/bany_profile.docx",
        "file_size": 42000
    }
)
```

#### Node 2: `clean_text`
**Component**: `TextCleaner`

**Process**:
1. Removes Arabic diacritics (تشكيل)
2. Normalizes Egyptian Arabic variations
3. Removes Tatweel (ـ) characters
4. Preserves original metadata

**Output**: `List[CleanedDocument]` with cleaned text

**Example**:
```
Input:  "شَرِكَةٌ بَانٍ لِلتَّطْوِيرِ"
Output: "شركة بانٍ للتطوير"
```

#### Node 3: `chunk_documents`
**Component**: `ParagraphChunker`

**Process**:
1. Splits documents into smaller chunks
2. Respects paragraph boundaries
3. Applies size constraints (100-1000 chars)
4. Adds overlap between chunks (50 chars)
5. Preserves metadata for each chunk

**Output**: `List[Chunk]` with text and metadata

**Example**:
```python
Chunk(
    text="شركة بانٍ للتطوير العقاري تُعد واحدة من أكبر...",
    metadata={
        "file_name": "bany_profile.docx",
        "chunk_index": 0,
        "chunk_size": 450
    }
)
```

#### Node 4: `embed_chunks`
**Component**: `AraModernBERTEmbedder`

**Process**:
1. Loads Arabic BERT model (Muffakir_Embedding_V2)
2. Processes chunks in batches (32 at a time)
3. Generates 1024-dimensional embeddings
4. Uses CUDA if available, falls back to CPU

**Output**: `List[EmbeddedChunk]` with embeddings

**Example**:
```python
EmbeddedChunk(
    chunk=Chunk(...),
    embedding=np.array([0.123, -0.456, ..., 0.789])  # 1024 dims
)
```

#### Node 5: `store_embeddings`
**Component**: `FAISSStore`

**Process**:
1. Creates FAISS index (IndexFlatL2)
2. Normalizes embeddings for cosine similarity
3. Adds embeddings to index
4. Saves index to `data/embeddings/index.faiss`
5. Saves chunks to `data/embeddings/chunks.pkl`

**Output**: Saved files on disk

**Files Created**:
- `index.faiss`: Binary FAISS index file
- `chunks.pkl`: Pickled list of chunk dictionaries

---

## 🔍 Phase 2: Query Pipeline

**Purpose**: Answer user questions using the index and structured data

### Flow Diagram

```
┌─────────────────┐
│  User Query     │
│  "ما هي أنواع   │
│   الشقق؟"       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 1. Embed Query  │ ◄─── AraModernBERTEmbedder
│    • Same model │      • Same embedding model
│      as chunks  │      • Clean query text
│    • Generate   │      • 1024-dim vector
│      vector     │
└────────┬────────┘
         │
         ├──────────────────────┐
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ 2a. Retrieve    │    │ 2b. Select      │
│     Chunks      │    │     Units       │
│                 │    │                 │
│ • Load FAISS    │    │ • Load CSV      │
│ • Similarity    │    │ • Generate      │
│   search        │    │   pandas code   │
│ • Top-K chunks  │    │ • Execute code  │
│   (k=5)         │    │ • Get matching  │
│                 │    │   units         │
└────────┬────────┘    └────────┬────────┘
         │                      │
         │    (Parallel)        │
         │                      │
         └──────────┬───────────┘
                    │
                    ▼
┌─────────────────┐
│ 3. Generate     │ ◄─── LLMGenerator (Gemini)
│    Answer       │      • Model: gemini-2.0-flash
│                 │      • Inputs:
│ • Combine:      │        - Query
│   - RAG chunks  │        - RAG context
│   - CSV units   │        - Structured units
│   - History     │        - Conversation history
│ • LLM generates │      • Temperature: 0.7
│   answer        │      • Streaming support
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Final Answer   │
│  "هناك عدة أنواع │
│   من الشقق..."  │
└─────────────────┘
```

### Step-by-Step Details

#### Node 1: `embed_query`
**Component**: `AraModernBERTEmbedder`

**Process**:
1. Cleans query text (same as documents)
2. Uses same embedding model as ingestion
3. Generates 1024-dimensional query embedding
4. Normalizes for cosine similarity

**Output**: `EmbeddedQuery` with query text and embedding

**Why Same Model?**: Ensures query and document embeddings are in the same vector space for accurate similarity search.

#### Node 2a: `retrieve_chunks` (Parallel Branch 1)
**Component**: `Retriever` + `FAISSStore`

**Process**:
1. Loads FAISS index from disk
2. Loads chunks.pkl file
3. Performs vector similarity search:
   - Query embedding vs. all chunk embeddings
   - Uses cosine similarity (L2 distance on normalized vectors)
4. Returns top-K most similar chunks (default: k=5)
5. Includes similarity scores

**Output**: `List[RetrievedChunk]` with chunks and scores

**Example**:
```python
RetrievedChunk(
    chunk=Chunk(text="...", metadata={...}),
    score=0.85,  # Similarity score (0-1)
    metadata={...}
)
```

#### Node 2b: `select_units` (Parallel Branch 2)
**Component**: `UnitSelector`

**Process**:
1. Loads CSV file (`data/11-15_sample25.csv`)
2. Analyzes user query
3. Generates pandas code using LLM (Gemini):
   - Code filters CSV based on query
   - Example: `df[df['Area'] == 150]`
4. Executes code safely (sandboxed)
5. Returns matching rows as dictionaries

**Output**: `List[Dict]` with structured unit data

**Example**:
```python
[
    {
        "Unit_Type": "Apartment",
        "Area": 150,
        "Price": 5000000,
        "Floor": "2nd"
    },
    ...
]
```

**Why Parallel?**: Both retrieval and selection can run simultaneously, reducing total query time.

#### Node 3: `generate_answer`
**Component**: `LLMGenerator` (Gemini API)

**Process**:
1. Builds comprehensive prompt with:
   - User question
   - Retrieved RAG chunks (context from documents)
   - Structured units (from CSV)
   - Conversation history (if available)
2. Sends to Gemini API
3. Generates answer in Egyptian Arabic
4. Supports streaming for real-time responses

**Prompt Structure**:
```
System: You are a helpful real estate assistant. Answer in Egyptian Arabic.

Context from Documents:
[Retrieved chunk 1]
[Retrieved chunk 2]
...

Structured Data (Units):
[Unit 1]
[Unit 2]
...

Conversation History:
User: [previous question]
Assistant: [previous answer]

User Question: [current question]
```

**Output**: `Answer` with generated text

---

## 🔧 Components Deep Dive

### 1. DocumentLoader
**Location**: `src/ingestion/loader.py`

**Capabilities**:
- PDF: Uses PyPDF2
- DOCX: Uses python-docx
- TXT/MD: Direct file reading
- Multiple encoding support (UTF-8, Arabic encodings)

### 2. TextCleaner
**Location**: `src/ingestion/cleaner.py`

**Operations**:
- Diacritic removal: `شَرِكَة` → `شركة`
- Egyptian normalization: `إيه` → `ايه`
- Tatweel removal: `كـتاب` → `كتاب`

### 3. ParagraphChunker
**Location**: `src/ingestion/chunker.py`

**Strategy**:
- Paragraph-aware splitting
- Size constraints (min: 100, max: 1000 chars)
- Overlap between chunks (50 chars)
- Preserves context across chunks

### 4. AraModernBERTEmbedder
**Location**: `src/embeddings/embedder.py`

**Model**: `mohamed2811/Muffakir_Embedding_V2`
- Arabic-optimized BERT
- 1024-dimensional embeddings
- Sentence-transformers compatible
- Batch processing support

### 5. FAISSStore
**Location**: `src/vector_store/faiss_store.py`

**Index Type**: `IndexFlatL2`
- L2 distance on normalized vectors = Cosine similarity
- Fast exact search
- Supports millions of vectors
- Persistent storage

### 6. Retriever
**Location**: `src/retrieval/retriever.py`

**Process**:
- Loads FAISS index
- Performs similarity search
- Returns top-K results with scores
- Handles empty results gracefully

### 7. UnitSelector
**Location**: `src/selector/unit_selector.py`

**Process**:
1. Analyzes query intent
2. Generates pandas filtering code
3. Executes code safely
4. Returns matching CSV rows

**Safety Features**:
- Blocks dangerous operations
- Validates code before execution
- Handles errors gracefully

### 8. LLMGenerator
**Location**: `src/generator/generator.py`

**Model**: Gemini 2.0 Flash
- Fast inference
- Arabic language support
- Streaming responses
- Conversation memory integration

---

## 📊 Data Flow

### State Transitions

```
Initial State
├─ documents: []
├─ cleaned_documents: []
├─ chunks: []
├─ embedded_chunks: []
├─ query: None
├─ embedded_query: None
├─ retrieved_chunks: []
├─ structured_units: []
├─ answer: None
└─ config: {...}

After load_documents
├─ documents: [Document, ...]  ← Updated
└─ ...

After clean_text
├─ cleaned_documents: [CleanedDocument, ...]  ← Updated
└─ ...

After chunk_documents
├─ chunks: [Chunk, ...]  ← Updated
└─ ...

After embed_chunks
├─ embedded_chunks: [EmbeddedChunk, ...]  ← Updated
└─ ...

After store_embeddings
└─ (Files saved to disk)

After embed_query
├─ query: Query(...)  ← Updated
├─ embedded_query: EmbeddedQuery(...)  ← Updated
└─ ...

After retrieve_chunks (parallel)
├─ retrieved_chunks: [RetrievedChunk, ...]  ← Updated
└─ ...

After select_units (parallel)
├─ structured_units: [Dict, ...]  ← Updated
└─ ...

After generate_answer
├─ answer: Answer(...)  ← Updated
└─ ...
```

### Reducer Function

When multiple nodes run in parallel (like `retrieve_chunks` and `select_units`), the reducer merges their state updates:

```python
def reducer(left: dict, right: dict) -> dict:
    result = left.copy()
    for key, value in right.items():
        if value is None:
            continue  # Skip None values
        elif isinstance(value, list):
            result[key] = value  # Replace lists
        elif isinstance(value, dict):
            result[key] = {**result[key], **value}  # Merge dicts
        else:
            result[key] = value  # Replace other values
    return result
```

---

## 🎛️ State Management

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
    structured_units: List[Dict[str, Any]]
    answer: Optional[Answer]
    
    # Configuration and metadata
    config: Dict[str, Any]
    errors: List[str]
    vector_store_path: Optional[str]
    chunks_path: Optional[str]
```

### Config Structure

```python
config = {
    # Paths
    'data_path': 'data/raw',
    'save_index_path': 'data/embeddings/index.faiss',
    'save_chunks_path': 'data/embeddings/chunks.pkl',
    
    # Embedding
    'embedder_model_name': 'mohamed2811/Muffakir_Embedding_V2',
    'embedding_dim': 1024,
    'device': 'cuda',
    
    # Chunking
    'chunk_min_size': 100,
    'chunk_max_size': 1000,
    'chunk_overlap': 50,
    
    # Retrieval
    'retrieval_k': 5,
    
    # Generator
    'gemini_api_key': '...',
    'gemini_model_name': 'gemini-2.0-flash',
    'temperature': 0.7,
    
    # Selector
    'csv_path': 'data/11-15_sample25.csv',
    
    # Other
    'clean_query': True,
    'recursive': True
}
```

---

## 🔄 Complete End-to-End Flow

### Example: User asks "ما هي أنواع الشقق المتاحة؟"

```
1. User Query Received
   └─> "ما هي أنواع الشقق المتاحة؟"

2. Embed Query
   └─> Query embedding: [0.123, -0.456, ..., 0.789] (1024 dims)

3. Parallel Execution:
   
   a) Retrieve Chunks:
      └─> Search FAISS index
      └─> Find top-5 similar chunks:
          - Chunk 1: "هناك عدة أنواع من الشقق..." (score: 0.92)
          - Chunk 2: "الشقق تشمل..." (score: 0.87)
          - ...
   
   b) Select Units:
      └─> Generate code: df[df['Unit_Type'].str.contains('Apartment')]
      └─> Execute on CSV
      └─> Get 10 matching units

4. Generate Answer:
   └─> Build prompt with:
       - Query: "ما هي أنواع الشقق المتاحة؟"
       - RAG context: [5 chunks]
       - Structured data: [10 units]
       - History: [previous messages]
   
   └─> Send to Gemini
   └─> Receive answer: "هناك عدة أنواع من الشقق المتاحة..."

5. Return Response:
   └─> Answer text
   └─> Metadata (chunks, units, scores)
```

---

## 🚀 Performance Optimizations

1. **Parallel Processing**: Retrieval and selection run simultaneously
2. **Batch Embedding**: Processes chunks in batches (32 at a time)
3. **CUDA Support**: Uses GPU for faster embedding generation
4. **Index Caching**: FAISS index loaded once and reused
5. **Streaming**: Real-time answer generation for better UX

---

## 🔍 Key Design Decisions

1. **Same Embedding Model**: Query and documents use the same model for accurate similarity
2. **Paragraph-Aware Chunking**: Preserves semantic boundaries
3. **Overlap Between Chunks**: Ensures context isn't lost at boundaries
4. **Dual Source**: Combines document RAG + structured CSV data
5. **Graceful Degradation**: System works even if selector fails
6. **State-Based Architecture**: LangGraph enables complex workflows

---

## 📝 Summary

The RAG pipeline is a sophisticated system that:

1. **Ingests** documents → Creates searchable vector index
2. **Queries** using dual sources:
   - Document-based RAG (semantic search)
   - Structured CSV data (code-based filtering)
3. **Generates** answers combining both sources
4. **Maintains** conversation context

All orchestrated through LangGraph's state machine architecture, enabling parallel processing, error handling, and extensibility.

---

**Last Updated**: 2025-11-25

