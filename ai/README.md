# AI Services Directory

This directory contains the AI services for the real estate chatbot system.

## Structure

```
ai/
├── orchestrator/          # Voice/Text orchestration layer
│   ├── services/          # Service clients (ASR, TTS, RAG)
│   ├── voice_orchestrator.py
│   └── text_orchestrator.py
│
└── rag/                   # RAG (Retrieval-Augmented Generation) system
    ├── app/               # FastAPI application
    ├── src/               # Core RAG components
    ├── config/            # Configuration files
    └── data/              # Data and embeddings
```

## Components

### Orchestrator (`orchestrator/`)

Voice-enabled orchestration layer that handles:
- **Voice Input** → ASR → RAG → TTS → **Audio Output**
- **Text Input** → RAG → TTS → **Audio Output**

**WebSocket Endpoints:**
- `/orchestrator/voice-stream` - Voice streaming
- `/orchestrator/text-stream` - Text streaming

See [ORCHESTRATOR_REVIEW.md](./ORCHESTRATOR_REVIEW.md) for detailed documentation.

### RAG System (`rag/`)

Retrieval-Augmented Generation system for Arabic real estate chatbot:
- Document ingestion and chunking
- Vector embeddings and FAISS indexing
- Unit selection from CSV data
- LLM-powered query generation

**API Endpoints:**
- `/query` - Query endpoint
- `/query/stream` - Streaming query endpoint
- `/ingest` - Document ingestion
- `/documents` - Document management

See [rag/README.md](./rag/README.md) for detailed documentation.

## Quick Start

### Running the API Server

```bash
cd rag
python run.py api
```

The server will start on `http://localhost:8000`

### Using the Orchestrator

Connect to WebSocket endpoints for voice/text streaming:

```javascript
// Voice stream
const ws = new WebSocket('ws://localhost:8000/orchestrator/voice-stream');

// Text stream
const ws = new WebSocket('ws://localhost:8000/orchestrator/text-stream');
```

See [ORCHESTRATOR_REVIEW.md](./ORCHESTRATOR_REVIEW.md) for protocol details.

## Integration

The orchestrator integrates with:
- **Arabic ASR API**: Speech-to-text transcription
- **Arabic TTS API**: Text-to-speech synthesis
- **RAG Pipeline**: Existing RAG system (non-invasive wrapper)

## Documentation

- [Orchestrator Review](./ORCHESTRATOR_REVIEW.md) - Complete orchestrator documentation
- [RAG README](./rag/README.md) - RAG system documentation
- [API Documentation](./rag/API_DOCUMENTATION.md) - API endpoint documentation

