# URL Configuration Changes for Cloud Run Deployment

## Summary

Updated RAG and Orchestrator services to properly handle CORS origins and URL configuration for Cloud Run deployments.

## Changes Made

### 1. Orchestrator Service (`ai/orchestrator/`)

#### Configuration (`app/core/config.py`)
- Added `cors_origins` setting to support configurable CORS origins via `CORS_ORIGINS` environment variable
- Defaults to `"*"` (allow all origins) for flexibility

#### Main Application (`app/main.py`)
- Updated CORS middleware to read from `settings.cors_origins`
- Handles comma-separated list of origins
- Automatically falls back to `["*"]` if wildcard patterns are detected (FastAPI doesn't support wildcard patterns like `https://*.run.app`)

### 2. RAG Service (`ai/rag/`)

#### API (`app/api.py`)
- Updated CORS middleware to read from `CORS_ORIGINS` environment variable
- Same behavior as orchestrator: supports comma-separated origins, defaults to `["*"]`
- Handles wildcard patterns gracefully by falling back to allow all

### 3. Frontend (`Ai-P/`)

#### WebSocket Hook (`app/hooks/useWebSocket.ts`)
- Added automatic Cloud Run domain detection
- Constructs orchestrator WebSocket URL from frontend URL pattern:
  - Frontend: `ai-p-xxxxx-uc.a.run.app`
  - Orchestrator: `orchestrator-xxxxx-uc.a.run.app`
- Falls back to `NEXT_PUBLIC_WS_URL` if set, then to localhost for local development

#### Dockerfile
- Added build args for `NEXT_PUBLIC_ORCHESTRATOR_URL` and `NEXT_PUBLIC_WS_URL`
- These are set during build time so Next.js can bake them into the bundle

#### Cloud Build Config (`cloudbuild.yaml`)
- New file to handle build args during Cloud Build
- Passes orchestrator URLs as build arguments

### 4. Deployment Script (`scripts/deploy_cloud_run.sh`)

#### Changes
- Frontend is now built **after** orchestrator is deployed (so we have the orchestrator URL)
- Uses `cloudbuild.yaml` to pass build args to frontend build
- Sets `CORS_ORIGINS=*` for both RAG and Orchestrator services
- Documents that CORS allows all origins for Cloud Run compatibility

## Environment Variables

### Orchestrator
- `CORS_ORIGINS`: Comma-separated list of allowed origins, or `*` for all (default: `*`)

### RAG
- `CORS_ORIGINS`: Comma-separated list of allowed origins, or `*` for all (default: `*`)

### Frontend (Build Time)
- `NEXT_PUBLIC_ORCHESTRATOR_URL`: Orchestrator HTTP URL
- `NEXT_PUBLIC_WS_URL`: Orchestrator WebSocket URL

### Frontend (Runtime)
- `NEXT_PUBLIC_ORCHESTRATOR_URL`: Orchestrator HTTP URL (if not set at build time)
- `NEXT_PUBLIC_WS_URL`: Orchestrator WebSocket URL (if not set at build time)

## How It Works

1. **Deployment Flow**:
   - RAG and Orchestrator are built and deployed first
   - Orchestrator URL is captured
   - Frontend is built with orchestrator URLs as build args
   - Frontend is deployed with runtime environment variables

2. **WebSocket Connection**:
   - Frontend checks `NEXT_PUBLIC_WS_URL` first (build-time or runtime)
   - If not set, detects Cloud Run domain and constructs orchestrator URL
   - Falls back to localhost for local development

3. **CORS Handling**:
   - Both services allow all origins (`*`) by default for Cloud Run compatibility
   - Can be restricted by setting `CORS_ORIGINS` with specific URLs
   - FastAPI doesn't support wildcard patterns, so `https://*.run.app` would fall back to `*`

## Security Considerations

- **Current**: CORS allows all origins (`*`) for simplicity and Cloud Run compatibility
- **Production**: Consider setting specific origins in `CORS_ORIGINS` environment variable:
  ```bash
  CORS_ORIGINS=https://ai-p-xxxxx-uc.a.run.app,https://your-custom-domain.com
  ```

## Testing

After deployment, verify:
1. Frontend can connect to orchestrator WebSocket
2. Frontend can make HTTP requests to orchestrator
3. Orchestrator can make requests to RAG API
4. CORS headers are present in responses

## Notes

- WebSocket connections from Cloud Run frontend to Cloud Run orchestrator work automatically
- CORS is primarily for HTTP requests (WebSocket connections don't use CORS)
- The runtime URL detection in the frontend provides a fallback if build-time variables aren't set

