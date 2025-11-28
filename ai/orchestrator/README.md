# Real-Time Orchestrator

High-performance Real-Time Orchestrator in Python using FastAPI that manages the complete voice/text pipeline for an Arabic RAG chatbot. This orchestrator coordinates between ASR, RAG, and TTS services with bidirectional streaming support.

## Features

- **WebSocket-based bidirectional communication** for real-time interaction
- **Voice mode**: Audio input → ASR → RAG → TTS → Audio output
- **Text mode**: Text input → RAG → TTS → Audio output
- **Redis-based state management** for scalability
- **Structured JSON logging** for observability
- **Prometheus metrics** endpoint
- **Docker Compose** deployment ready

## Architecture

```
Client (WebSocket)
    ↓
Orchestrator
    ├─→ ASR Service (HTTP POST)
    ├─→ RAG Service (SSE Streaming)
    └─→ TTS Service (HTTP POST)
    ↓
Redis (State Management)
```

## Project Structure

```
orchestrator/
├── app/
│   ├── main.py                    # FastAPI app, startup/shutdown, routes
│   ├── api/
│   │   ├── websocket.py          # WebSocket connection handler
│   │   ├── health.py             # Health check endpoints
│   │   └── metrics.py            # Prometheus metrics
│   ├── services/
│   │   ├── asr_client.py         # ASR API client (HTTP POST)
│   │   ├── rag_client.py         # RAG API client (SSE streaming)
│   │   ├── tts_client.py         # TTS API client (HTTP POST)
│   │   └── redis_client.py       # Redis Streams helper
│   ├── orchestrators/
│   │   ├── base.py               # Base orchestrator class
│   │   ├── voice_orchestrator.py # Voice flow state machine
│   │   └── text_orchestrator.py  # Text flow state machine
│   ├── models/
│   │   └── schemas.py            # Pydantic models for messages
│   ├── core/
│   │   ├── config.py             # Environment-based config
│   │   ├── auth.py               # Token authentication
│   │   └── utils.py              # Helper functions
│   └── logging_config.py         # Structured JSON logging
├── tests/
├── docker-compose.yml            # Redis + Orchestrator
├── Dockerfile
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites

- Python 3.11+
- Redis 7+
- Docker and Docker Compose (optional)

### Local Development

1. **Clone and navigate to the orchestrator directory:**
   ```bash
   cd orchestrator
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables:**
   ```bash
   export ASR_API_URL=https://arabic-asr-api-22251281831.us-central1.run.app
   export RAG_API_URL=http://localhost:8000
   export TTS_API_URL=https://arabic-tts-api-22251281831.us-central1.run.app
   export REDIS_HOST=localhost
   export REDIS_PORT=6379
   export JWT_SECRET=your-secret-key
   ```

5. **Start Redis:**
   ```bash
   redis-server
   ```

6. **Run the orchestrator:**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8040
   ```

### Docker Compose

1. **Create a `.env` file (optional):**
   ```bash
   ASR_API_URL=https://arabic-asr-api-22251281831.us-central1.run.app
   RAG_API_URL=http://host.docker.internal:8000
   TTS_API_URL=https://arabic-tts-api-22251281831.us-central1.run.app
   JWT_SECRET=your-secret-key-change-in-production
   ```

2. **Start services:**
   ```bash
   docker-compose up -d
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f orchestrator
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ASR_API_URL` | Batch ASR service URL (HTTP) | `https://arabic-asr-api-22251281831.us-central1.run.app` |
| `ASR_STREAMING_WS_URL` | Streaming ASR WebSocket endpoint | `wss://arabic-asr-api-22251281831.us-central1.run.app/ws/asr-stream` |
| `ASR_STREAMING_CONNECT_TIMEOUT` | Seconds to wait when establishing the streaming socket | `10` |
| `ASR_STREAMING_RESULT_TIMEOUT` | Seconds to wait for the final streaming transcript before falling back to batch ASR | `15` |
| `RAG_API_URL` | RAG service URL | `http://localhost:8000` |
| `TTS_API_URL` | TTS service URL | `https://arabic-tts-api-22251281831.us-central1.run.app` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password | `None` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8040` |
| `JWT_SECRET` | JWT secret for authentication | `your-secret-key-change-in-production` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format (json/text) | `json` |
| `MAX_AUDIO_BUFFER_SIZE` | Max audio buffer size (bytes) | `10485760` (10MB) |
| `MAX_SESSION_DURATION` | Max session duration (seconds) | `3600` (1 hour) |

## API Endpoints

### WebSocket Endpoints

#### `/ws/voice` - Voice Mode
Handles voice input flow: Audio → ASR → RAG → TTS → Audio

##### Streaming STT (realtime transcripts)

- When `ASR_STREAMING_WS_URL` is configured the orchestrator opens a dedicated WebSocket
  to the Google Cloud backed ASR proxy as soon as the client sends `start_session`.
- Incoming `audio_chunk` frames are forwarded to the streaming socket after being
  transcoded to 16‑bit PCM. Interim and final transcripts are pushed back to the
  frontend immediately through the existing orchestrator WebSocket (`type: "transcript"`).
- If streaming is unavailable (env unset, connection failure, or timeout) the
  orchestrator automatically falls back to the previous batch flow:
  combine all chunks → send a single `/asr` request → emit one final transcript.
- Regardless of the source, the transcript is subsequently sent through the RAG+TTS
  stages without further changes.

#### `/ws/text` - Text Mode
Handles text input flow: Text → RAG → TTS → Audio

### HTTP Endpoints

- `GET /` - Root endpoint with service information
- `GET /test` - Test client HTML page (interactive WebSocket testing interface)
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health check with service status
- `GET /metrics` - Prometheus metrics endpoint
- `GET /documents` - Proxy to RAG document listing
- `POST /documents` - Upload a document to RAG (optionally rebuilds the index)
- `PUT /documents/{filename}` - Overwrite an existing RAG document
- `DELETE /documents/{filename}` - Remove a specific document (and optionally its index chunks)
- `DELETE /documents` - Clear all documents (and optionally the FAISS index)

## WebSocket Protocol

### Client → Orchestrator Messages

#### Start Session
```json
{
  "type": "start_session",
  "session_id": "<uuid>",
  "auth": "Bearer <token>",
  "metadata": {
    "lang": "ar",
    "sample_rate": 16000
  }
}
```

#### Audio Chunk (Voice Mode)
```json
{
  "type": "audio_chunk",
  "seq": 1,
  "audio_base64": "<base64 encoded audio>",
  "timestamp": 1670000000
}
```

#### Text Message (Text Mode)
```json
{
  "type": "text_message",
  "text": "ما هي أنواع الشقق المتاحة؟"
}
```

#### End Stream
```json
{
  "type": "end_stream"
}
```

### Orchestrator → Client Messages

#### Transcript
```json
{
  "type": "transcript",
  "session_id": "<uuid>",
  "text": "...",
  "is_final": true
}
```

#### RAG Chunk
```json
{
  "type": "rag_chunk",
  "session_id": "<uuid>",
  "chunk": "...",
  "is_last": false
}
```

#### TTS Audio
```json
{
  "type": "tts_audio",
  "seq": 1,
  "audio_base64": "<base64 MP3>",
  "format": "mp3",
  "is_last": false
}
```

#### Error
```json
{
  "type": "error",
  "code": 500,
  "message": "..."
}
```

#### Session Closed
```json
{
  "type": "session_closed",
  "session_id": "<uuid>",
  "reason": "completed"
}
```

## Usage Examples

### Voice Mode Example (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8040/ws/voice');

ws.onopen = () => {
  // Start session
  ws.send(JSON.stringify({
    type: 'start_session',
    session_id: 'session-123',
    auth: 'Bearer your-token',
    metadata: { lang: 'ar', sample_rate: 16000 }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
  
  if (message.type === 'transcript') {
    console.log('Transcript:', message.text);
  } else if (message.type === 'rag_chunk') {
    console.log('RAG chunk:', message.chunk);
  } else if (message.type === 'tts_audio') {
    // Play audio
    const audio = new Audio('data:audio/mp3;base64,' + message.audio_base64);
    audio.play();
  }
};

// Send audio chunks
function sendAudioChunk(audioBlob, seq) {
  const reader = new FileReader();
  reader.onload = () => {
    const base64 = reader.result.split(',')[1];
    ws.send(JSON.stringify({
      type: 'audio_chunk',
      seq: seq,
      audio_base64: base64
    }));
  };
  reader.readAsDataURL(audioBlob);
}

// When done sending audio
ws.send(JSON.stringify({ type: 'end_stream' }));
```

### Text Mode Example (Python)

```python
import asyncio
import websockets
import json

async def text_session():
    uri = "ws://localhost:8040/ws/text"
    async with websockets.connect(uri) as websocket:
        # Start session
        await websocket.send(json.dumps({
            "type": "start_session",
            "session_id": "session-123",
            "auth": "Bearer your-token",
            "metadata": {"lang": "ar"}
        }))
        
        # Send text message
        await websocket.send(json.dumps({
            "type": "text_message",
            "text": "ما هي أنواع الشقق المتاحة؟"
        }))
        
        # Receive responses
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data['type']}")
            
            if data['type'] == 'rag_chunk':
                print(f"RAG: {data['chunk']}")
            elif data['type'] == 'tts_audio':
                # Save or play audio
                audio_bytes = base64.b64decode(data['audio_base64'])
                with open(f"audio_{data['seq']}.mp3", "wb") as f:
                    f.write(audio_bytes)

asyncio.run(text_session())
```

## Testing

### Web Test Client

A simple HTML test client is included and served directly by the orchestrator API:

1. **Access the test client:**
   ```bash
   # Start the orchestrator
   python -m uvicorn app.main:app --reload --port 8040
   
   # Then navigate to:
   http://localhost:8040/test
   ```

2. **Features:**
   - Test both Text and Voice modes
   - Real-time WebSocket connection status
   - Display transcripts, RAG chunks, and TTS audio
   - Record audio directly from browser microphone
   - Visual feedback for all message types
   - No additional setup required - just start the orchestrator and visit `/test`

### Health Check
```bash
curl http://localhost:8040/health
```

### Detailed Health Check
```bash
curl http://localhost:8040/health/detailed
```

### Metrics
```bash
curl http://localhost:8040/metrics
```

## Monitoring

The orchestrator exposes Prometheus metrics at `/metrics`:

- `orchestrator_websocket_connections_total` - Total WebSocket connections
- `orchestrator_websocket_messages_total` - Total WebSocket messages
- `orchestrator_session_duration_seconds` - Session duration
- `orchestrator_api_requests_total` - API requests by service
- `orchestrator_api_latency_seconds` - API latency
- `orchestrator_active_sessions` - Active sessions

## Logging

Logs are written in JSON format to `logs/orchestrator_YYYYMMDD.log` and also output to stdout.

Example log entry:
```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "app.orchestrators.voice_orchestrator",
  "message": "Voice session abc123 started",
  "module": "voice_orchestrator",
  "function": "handle_session",
  "line": 45
}
```

## Troubleshooting

### Redis Connection Failed
- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_HOST` and `REDIS_PORT` environment variables

### RAG Service Not Responding
- Verify RAG service is running: `curl http://localhost:8000/health`
- Check `RAG_API_URL` environment variable
- For Docker, use `host.docker.internal:8000` instead of `localhost:8000`

### ASR/TTS Service Errors
- Check service URLs are correct
- Verify network connectivity
- Check service logs for errors

## License

MIT

