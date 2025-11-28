# RAG System - Complete Flow & API Endpoints Documentation

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Complete Flow](#complete-flow)
3. [API Endpoints](#api-endpoints)
4. [Data Flow Diagram](#data-flow-diagram)

---

## 🎯 System Overview

The RAG (Retrieval-Augmented Generation) system combines:
- **Document-based RAG**: Searches through uploaded documents (PDF, DOCX, TXT, MD)
- **Structured Data Selector**: Queries CSV data using LLM-generated pandas code
- **LLM Generator**: Generates answers using Gemini API with both sources

---

## 🔄 Complete Flow

### Phase 1: Document Ingestion (Building the Index)

```
1. Upload Documents
   ↓
2. Documents saved to data/raw/
   ↓
3. Build Index (Ingestion)
   ├─ Load documents from data/raw/
   ├─ Clean text (remove diacritics, normalize)
   ├─ Chunk documents (split into smaller pieces)
   ├─ Generate embeddings (using Arabic BERT model)
   └─ Save to FAISS index + chunks.pkl
```

**Files Created:**
- `data/embeddings/index.faiss` - FAISS vector index
- `data/embeddings/chunks.pkl` - Chunk texts and metadata

### Phase 2: Query Processing

```
User Query
   ↓
Parallel Execution:
   ├─ RAG Retrieval
   │  ├─ Embed query
   │  ├─ Search FAISS index
   │  └─ Get top-k relevant chunks
   │
   └─ CSV Selector
      ├─ Generate pandas code (LLM)
      ├─ Execute code on CSV
      └─ Get matching units
   ↓
Answer Generation
   ├─ Combine: RAG chunks + CSV units
   ├─ Add conversation history
   └─ Generate answer (Gemini)
   ↓
Response to User
```

---

## 🌐 API Endpoints

### 1. Health & Status Endpoints

#### `GET /health`
**Purpose**: Quick health check

**Response:**
```json
{
  "status": "healthy",
  "index_exists": true,
  "chunks_exist": true,
  "gemini_api_key_set": true
}
```

#### `GET /health/detailed`
**Purpose**: Detailed system status

**Response:**
```json
{
  "status": "healthy",
  "api_key": {...},
  "index": {
    "exists": true,
    "num_vectors": 150,
    "embedding_dim": 1024
  },
  "embedder": {...},
  "data": {...}
}
```

---

### 2. Document Management Endpoints

#### `GET /documents`
**Purpose**: List all uploaded documents

**Response:**
```json
{
  "total": 5,
  "documents": [
    {
      "name": "document.pdf",
      "size": 1024000,
      "modified": "2025-11-25T10:00:00"
    }
  ]
}
```

#### `POST /documents/upload`
**Purpose**: Upload a document

**Parameters:**
- `file` (FormData): The file to upload
- `rebuild_index` (Query, default: `true`): Automatically rebuild index after upload

**Supported Formats**: PDF, DOCX, TXT, MD

**Response:**
```json
{
  "status": "success",
  "message": "Document uploaded successfully and index rebuilt",
  "filename": "document.pdf",
  "path": "document.pdf",
  "size": 1024000
}
```

**Note**: If `rebuild_index=true`, the index is automatically rebuilt from all documents in `data/raw/`

#### `DELETE /documents/{filename}`
**Purpose**: Delete a specific document

**Parameters:**
- `filename` (Path): Name of the file to delete
- `remove_from_index` (Query, default: `true`): Remove document chunks from FAISS index

**Response:**
```json
{
  "status": "success",
  "message": "Document 'document.pdf' deleted successfully (removed 15 chunks from index)",
  "chunks_removed": 15
}
```

**Note**: If `remove_from_index=true`, the index is rebuilt with remaining chunks

#### `DELETE /documents`
**Purpose**: Clear all documents

**Parameters:**
- `clear_index` (Query, default: `true`): Also delete FAISS index and chunks

**Response:**
```json
{
  "status": "success",
  "message": "Cleared 5 document(s) and cleared FAISS index",
  "files_deleted": 5,
  "deleted_files": ["doc1.pdf", "doc2.docx", ...],
  "index_cleared": true
}
```

---

### 3. Index Management Endpoints

#### `POST /ingest`
**Purpose**: Build/rebuild the FAISS index from documents

**Request Body:**
```json
{
  "data_path": "data/raw",
  "save_index_path": "data/embeddings/index.faiss",
  "save_chunks_path": "data/embeddings/chunks.pkl",
  "device": "cuda",
  "chunk_min_size": 100,
  "chunk_max_size": 1000,
  "chunk_overlap": 50
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Ingestion completed successfully",
  "num_documents": 5,
  "num_chunks": 150,
  "num_embeddings": 150
}
```

**Process:**
1. Loads all documents from `data_path`
2. Cleans and chunks them
3. Generates embeddings
4. Saves to FAISS index

---

### 4. Query Endpoints

#### `POST /query`
**Purpose**: Query the RAG system (non-streaming)

**Request Body:**
```json
{
  "question": "ما هي أنواع الشقق المتاحة؟",
  "session_id": "session_123",
  "retrieval_k": 5,
  "temperature": 0.7,
  "include_context": false
}
```

**Response:**
```json
{
  "answer": "هناك عدة أنواع من الشقق...",
  "question": "ما هي أنواع الشقق المتاحة؟",
  "num_chunks": 5,
  "top_score": 0.85,
  "num_structured_units": 10,
  "structured_units": [...],
  "unit_selector": {
    "code": "df[df['Type'] == 'Apartment']",
    "error": null
  },
  "context_chunks": [...] // if include_context=true
}
```

**Process:**
1. Embeds the query
2. Runs in parallel:
   - Retrieves relevant chunks from FAISS index
   - Selects units from CSV using LLM-generated pandas code
3. Generates answer using both sources
4. Returns answer with metadata

#### `POST /query/stream`
**Purpose**: Query the RAG system (streaming response)

**Request Body:** Same as `/query`

**Response:** Server-Sent Events (SSE) stream

**Event Types:**
- `chunk`: Partial answer text
- `done`: Complete answer
- `error`: Error message
- `metadata`: Additional metadata

**Example:**
```
data: {"type": "chunk", "text": "هناك"}
data: {"type": "chunk", "text": " عدة"}
data: {"type": "done", "full_text": "هناك عدة أنواع..."}
```

---

### 5. Chat Management Endpoints

#### `POST /chat/clear`
**Purpose**: Clear conversation history for a session

**Request Body:**
```json
{
  "session_id": "session_123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Chat history cleared"
}
```

#### `GET /chat/history`
**Purpose**: Get conversation history for a session

**Parameters:**
- `session_id` (Query): Session ID

**Response:**
```json
{
  "session_id": "session_123",
  "messages": [
    {"role": "user", "content": "مرحبا"},
    {"role": "assistant", "content": "مرحبا بك..."}
  ],
  "total_messages": 2
}
```

---

### 6. Selector Testing Endpoints

#### `POST /selector/test`
**Purpose**: Test the UnitSelector component independently

**Request Body:**
```json
{
  "question": "أعطني الشقق التي تبلغ مساحتها 150 متر",
  "max_rows": 50
}
```

**Response:**
```json
{
  "status": "success",
  "code": "df[df['Area'] == 150]",
  "units": [...],
  "num_units": 5,
  "error": null
}
```

#### `GET /selector/test/ui`
**Purpose**: Serve the selector test HTML page

**Response:** HTML page for testing the selector

---

### 7. UI Endpoints

#### `GET /`
**Purpose**: Serve the main web UI

**Response:** HTML page with chat interface and document management

---

## 📊 Data Flow Diagram

```
┌─────────────┐
│   User      │
│  (Browser)  │
└──────┬──────┘
       │
       │ HTTP Requests
       ▼
┌─────────────────────────────────────┐
│         FastAPI Server              │
│         (api.py)                    │
└──────┬──────────────────┬───────────┘
       │                  │
       │                  │
   ┌───▼───┐         ┌───▼──────┐
   │ Upload│         │  Query   │
   │ Docs  │         │ Endpoint │
   └───┬───┘         └───┬──────┘
       │                 │
       │                 │
       ▼                 │
┌──────────────┐         │
│  data/raw/   │         │
│  (Documents) │         │
└──────┬───────┘         │
       │                 │
       │                 │
       ▼                 │
┌──────────────┐         │
│   /ingest    │         │
│   Endpoint   │         │
└──────┬───────┘         │
       │                 │
       ▼                 │
┌─────────────────────┐  │
│  Ingestion Pipeline │  │
│  - Load Docs        │  │
│  - Clean Text       │  │
│  - Chunk            │  │
│  - Embed            │  │
│  - Save to FAISS    │  │
└──────┬──────────────┘  │
       │                 │
       ▼                 │
┌─────────────────────┐  │
│  FAISS Index        │  │
│  + chunks.pkl       │  │
└──────┬──────────────┘  │
       │                 │
       │                 │
       │                 ▼
       │         ┌──────────────────┐
       │         │  Query Pipeline  │
       │         │  (Parallel)      │
       │         └──────┬───────────┘
       │                │
       │         ┌──────▼──────────┐
       │         │  RAG Retrieval  │
       │         │  + CSV Selector │
       │         └──────┬──────────┘
       │                │
       │         ┌──────▼──────────┐
       │         │  LLM Generator  │
       │         │  (Gemini)       │
       │         └──────┬──────────┘
       │                │
       │                ▼
       │         ┌──────────────┐
       │         │   Answer     │
       │         │   Response   │
       │         └──────────────┘
       │
       └──────────────────────────┘
```

---

## 🔑 Key Features

### 1. **Automatic Index Rebuilding**
- Upload endpoint can automatically rebuild index
- Delete endpoint can update index by removing chunks

### 2. **Parallel Processing**
- RAG retrieval and CSV selection run in parallel
- Faster query response times

### 3. **Conversation Memory**
- Maintains chat history per session
- Context-aware responses

### 4. **Streaming Support**
- Real-time answer generation
- Better user experience

### 5. **Error Handling**
- Graceful degradation if selector fails
- Detailed error messages

---

## 📝 Usage Examples

### Example 1: Complete Workflow

```bash
# 1. Upload a document
curl -X POST "http://localhost:8000/documents/upload?rebuild_index=true" \
  -F "file=@document.pdf"

# 2. Query the system
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ما هي أنواع الوحدات المتاحة؟",
    "session_id": "user123"
  }'

# 3. Check health
curl "http://localhost:8000/health"
```

### Example 2: Manual Index Building

```bash
# Upload without rebuilding
curl -X POST "http://localhost:8000/documents/upload?rebuild_index=false" \
  -F "file=@document.pdf"

# Build index manually
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "data_path": "data/raw"
  }'
```

### Example 3: Delete Document

```bash
# Delete and remove from index
curl -X DELETE "http://localhost:8000/documents/document.pdf?remove_from_index=true"
```

---

## ⚙️ Configuration

Key configuration in `config/settings.yaml`:

- **Embedding Model**: `mohamed2811/Muffakir_Embedding_V2` (Arabic BERT)
- **LLM Generator**: `gemini-2.0-flash`
- **Chunking**: 100-1000 chars with 50 char overlap
- **Retrieval**: Top 5 chunks by default
- **CSV Path**: `data/11-15_sample25.csv` (for unit selector)

---

## 🚀 Getting Started

1. **Set Environment Variables:**
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```

2. **Start the Server:**
   ```bash
   cd ai/rag
   python -m uvicorn app.api:app --reload
   ```

3. **Access the UI:**
   - Main UI: http://localhost:8000/
   - Selector Test: http://localhost:8000/selector/test/ui

4. **Upload Documents:**
   - Use the web UI or API endpoint
   - Index rebuilds automatically

5. **Start Querying:**
   - Use the chat interface or API endpoint
   - System combines RAG + CSV selector results

---

## 📌 Important Notes

- **Index must exist before querying** - Use `/ingest` or upload with `rebuild_index=true`
- **CSV file must exist** for selector to work (default: `data/11-15_sample25.csv`)
- **Gemini API key required** for query and selector functionality
- **Index rebuilds** when documents are added/deleted (if enabled)
- **Conversation history** is maintained per session ID

---

## 🔍 Troubleshooting

### Index not found
- Run `/ingest` endpoint or upload a document with `rebuild_index=true`

### Selector not working
- Check if CSV file exists at configured path
- Verify Gemini API key is set

### No context found
- Ensure index is built and contains documents
- Check if query is relevant to uploaded documents

---

**Last Updated**: 2025-11-25

