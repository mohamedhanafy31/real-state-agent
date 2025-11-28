#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=${PROJECT_ID:-meta-478212}
REGION=${REGION:-us-central1}
REPO=${REPO:-"us-central1-docker.pkg.dev/${PROJECT_ID}/metavr-services"}
FRONTEND_IMAGE="${REPO}/ai-p:latest"
RAG_IMAGE="${REPO}/rag-api:latest"
ORCH_IMAGE="${REPO}/orchestrator:latest"

build_and_wait() {
  local dir="$1"
  local image="$2"

  echo "==> Building & pushing image ${image} from ${dir}"
  # Submit build asynchronously so gcloud doesn't try to stream logs from
  # the Cloud Build logs bucket (which often fails under restricted perms).
  local build_id
  build_id="$(
    cd "${dir}" && \
    gcloud builds submit --tag "${image}" . --async --format='value(name)'
  )"

  echo "    Build ID: ${build_id}"
  echo "    Waiting for build to complete..."

  # Poll build status without streaming logs (avoids logs bucket perms)
  while true; do
    status="$(gcloud builds describe "${build_id}" --format='value(status)')"
    case "${status}" in
      SUCCESS)
        echo "    Build ${build_id} succeeded."
        break
        ;;
      FAILURE|CANCELLED)
        echo "✗ Build ${build_id} failed with status: ${status}" >&2
        exit 1
        ;;
      *)
        sleep 5
        ;;
    esac
  done
}

require_env() {
  local name=$1
  if [[ -z "${!name:-}" ]]; then
    echo "✗ Environment variable ${name} is required but not set." >&2
    exit 1
  fi
}

echo "==> Using project ${PROJECT_ID} in ${REGION}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "==> Ensuring Artifact Registry repo exists"
if ! gcloud artifacts repositories describe metavr-services --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create metavr-services \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Containers for frontend, RAG, orchestrator"
fi

build_and_wait "Ai-P" "${FRONTEND_IMAGE}"
build_and_wait "ai/rag" "${RAG_IMAGE}"
build_and_wait "ai/orchestrator" "${ORCH_IMAGE}"

require_env GEMINI_API_KEY
require_env JWT_SECRET

ASR_API_URL=${ASR_API_URL:-https://arabic-asr-api-22251281831.us-central1.run.app}
TTS_API_URL=${TTS_API_URL:-https://arabic-tts-api-22251281831.us-central1.run.app}

echo "==> Deploying RAG Cloud Run service"
RAG_URL=$(gcloud run deploy rag-api \
  --image "${RAG_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --set-env-vars "LOG_LEVEL=INFO" \
  --format='value(status.url)')
echo "✓ RAG deployed at ${RAG_URL}"

echo "==> Deploying orchestrator Cloud Run service"
ORCH_URL=$(gcloud run deploy orchestrator \
  --image "${ORCH_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "RAG_API_URL=${RAG_URL}" \
  --set-env-vars "ASR_API_URL=${ASR_API_URL}" \
  --set-env-vars "TTS_API_URL=${TTS_API_URL}" \
  --set-env-vars "JWT_SECRET=${JWT_SECRET}" \
  --format='value(status.url)')
echo "✓ Orchestrator deployed at ${ORCH_URL}"

ORCH_WS_URL="${ORCH_URL/https:/wss:}"
ORCH_WS_URL="${ORCH_WS_URL/http:/ws:}"
ORCH_WS_URL="${ORCH_WS_URL%/}/ws/voice"

echo "==> Deploying frontend Cloud Run service"
FRONTEND_URL=$(gcloud run deploy ai-frontend \
  --image "${FRONTEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}" \
  --set-env-vars "NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}" \
  --format='value(status.url)')
echo "✓ Frontend deployed at ${FRONTEND_URL}"

cat > .env.cloudrun <<EOF
RAG_API_URL=${RAG_URL}
NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}
NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}
FRONTEND_URL=${FRONTEND_URL}
EOF
echo "==> Wrote resolved URLs to .env.cloudrun"

if [[ "${UPDATE_GITHUB_SECRETS:-0}" == "1" ]]; then
  if command -v gh >/dev/null 2>&1; then
    echo "==> Updating GitHub secrets via gh CLI"
    echo -n "${RAG_URL}" | gh secret set RAG_API_URL
    echo -n "${ORCH_URL}" | gh secret set NEXT_PUBLIC_ORCHESTRATOR_URL
    echo -n "${ORCH_WS_URL}" | gh secret set NEXT_PUBLIC_WS_URL
  else
    echo "⚠ gh CLI not found; skipping GitHub secret update" >&2
  fi
fi

echo "All services deployed successfully:"
echo "  Frontend: ${FRONTEND_URL}"
echo "  Orchestrator: ${ORCH_URL}"
echo "  RAG API: ${RAG_URL}"

