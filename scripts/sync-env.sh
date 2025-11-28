#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT_DIR}/config/env.template"
ROOT_ENV="${ROOT_DIR}/.env"
AI_ENV="${ROOT_DIR}/Ai-P/.env.local"
ORCH_ENV="${ROOT_DIR}/ai/orchestrator/.env"
RAG_ENV="${ROOT_DIR}/ai/rag/.env"

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "✗ Missing env template at ${TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${ROOT_ENV}" ]]; then
  echo "→ Creating ${ROOT_ENV} from template"
  cp "${TEMPLATE}" "${ROOT_ENV}"
fi

# shellcheck disable=SC1090
source "${TEMPLATE}"
# shellcheck disable=SC1090
source "${ROOT_ENV}"

mkdir -p "${ROOT_DIR}/Ai-P" "${ROOT_DIR}/ai/orchestrator" "${ROOT_DIR}/ai/rag"

cat > "${AI_ENV}" <<EOF
NEXT_PUBLIC_ORCHESTRATOR_URL="${NEXT_PUBLIC_ORCHESTRATOR_URL:-http://localhost:8040}"
NEXT_PUBLIC_WS_URL="${NEXT_PUBLIC_WS_URL:-ws://localhost:8040/ws/voice}"
EOF
echo "✓ Synced ${AI_ENV}"

cat > "${ORCH_ENV}" <<EOF
ASR_API_URL="${ASR_API_URL}"
ASR_STREAMING_WS_URL="${ASR_STREAMING_WS_URL:-}"
ASR_STREAMING_CONNECT_TIMEOUT=${ASR_STREAMING_CONNECT_TIMEOUT:-10}
ASR_STREAMING_RESULT_TIMEOUT=${ASR_STREAMING_RESULT_TIMEOUT:-15}
RAG_API_URL="${RAG_API_URL}"
TTS_API_URL="${TTS_API_URL}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
JWT_SECRET="${JWT_SECRET}"
HOST=0.0.0.0
PORT=${ORCHESTRATOR_PORT:-8040}
LOG_LEVEL=${ORCHESTRATOR_LOG_LEVEL:-INFO}
LOG_FORMAT=${LOG_FORMAT:-json}
EOF
echo "✓ Synced ${ORCH_ENV}"

cat > "${RAG_ENV}" <<EOF
GEMINI_API_KEY="${GEMINI_API_KEY}"
HOST=0.0.0.0
PORT=${RAG_PORT:-8000}
LOG_LEVEL=${RAG_LOG_LEVEL:-INFO}
LOG_DIR=logs
EOF
echo "✓ Synced ${RAG_ENV}"

echo "Done. Update ${ROOT_ENV} (based on ${TEMPLATE}) to change defaults."

