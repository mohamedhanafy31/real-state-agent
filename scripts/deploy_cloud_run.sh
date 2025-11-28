#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=${PROJECT_ID:-meta-478212}
REGION=${REGION:-us-central1}
REPO=${REPO:-"us-central1-docker.pkg.dev/${PROJECT_ID}/metavr-services"}
FRONTEND_IMAGE="${REPO}/ai-p:latest"
RAG_IMAGE="${REPO}/rag-api:latest"
ORCH_IMAGE="${REPO}/orchestrator:latest"

# Allow the caller (e.g. CI) to control which services are built/deployed.
# By default, if no flags are provided, we build/deploy everything.
DEPLOY_FRONTEND=${DEPLOY_FRONTEND:-1}
DEPLOY_RAG=${DEPLOY_RAG:-1}
DEPLOY_ORCH=${DEPLOY_ORCH:-1}

start_build() {
  local dir="$1"
  local image="$2"

  echo "==> Building & pushing image ${image} from ${dir}" >&2
  local build_id
  build_id="$(
    cd "${dir}" && \
    gcloud builds submit --tag "${image}" . --async --format='value(name)'
  )"
  echo "    Build started with ID: ${build_id}" >&2
  printf '%s\n' "${build_id}"
}

wait_for_build() {
  local build_id="$1"

  echo "    Waiting for build ${build_id} to complete..." >&2
  # Poll build status without streaming logs (avoids logs bucket perms)
  while true; do
    status="$(gcloud builds describe "${build_id}" --format='value(status)')"
    case "${status}" in
      SUCCESS)
        echo "    Build ${build_id} succeeded." >&2
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

echo "==> Starting Cloud Build jobs in parallel"
FRONTEND_BUILD_ID=""
RAG_BUILD_ID=""
ORCH_BUILD_ID=""

if [[ "${DEPLOY_FRONTEND}" == "1" || "${DEPLOY_FRONTEND}" == "true" ]]; then
  FRONTEND_BUILD_ID="$(start_build "Ai-P" "${FRONTEND_IMAGE}")"
fi
if [[ "${DEPLOY_RAG}" == "1" || "${DEPLOY_RAG}" == "true" ]]; then
  RAG_BUILD_ID="$(start_build "ai/rag" "${RAG_IMAGE}")"
fi
if [[ "${DEPLOY_ORCH}" == "1" || "${DEPLOY_ORCH}" == "true" ]]; then
  ORCH_BUILD_ID="$(start_build "ai/orchestrator" "${ORCH_IMAGE}")"
fi

if [[ -n "${FRONTEND_BUILD_ID}" ]]; then
  wait_for_build "${FRONTEND_BUILD_ID}"
fi
if [[ -n "${RAG_BUILD_ID}" ]]; then
  wait_for_build "${RAG_BUILD_ID}"
fi
if [[ -n "${ORCH_BUILD_ID}" ]]; then
  wait_for_build "${ORCH_BUILD_ID}"
fi

require_env GEMINI_API_KEY
require_env JWT_SECRET

ASR_API_URL=${ASR_API_URL:-https://arabic-asr-api-22251281831.us-central1.run.app}
TTS_API_URL=${TTS_API_URL:-https://arabic-tts-api-22251281831.us-central1.run.app}

RAG_URL="${RAG_API_URL:-}"
ORCH_URL="${ORCH_API_URL:-}"

if [[ "${DEPLOY_RAG}" == "1" || "${DEPLOY_RAG}" == "true" ]]; then
  echo "==> Deploying RAG Cloud Run service"
  RAG_URL=$(gcloud run deploy rag-api \
    --image "${RAG_IMAGE}" \
    --region "${REGION}" \
    --memory=4Gi \
    --allow-unauthenticated \
    --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
    --set-env-vars "LOG_LEVEL=INFO" \
    --format='value(status.url)')
  echo "✓ RAG deployed at ${RAG_URL}"
fi

if [[ "${DEPLOY_ORCH}" == "1" || "${DEPLOY_ORCH}" == "true" ]]; then
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
fi

ORCH_WS_URL=""
if [[ -n "${ORCH_URL}" ]]; then
  ORCH_WS_URL="${ORCH_URL/https:/wss:}"
  ORCH_WS_URL="${ORCH_WS_URL/http:/ws:}"
  ORCH_WS_URL="${ORCH_WS_URL%/}/ws/voice"
fi

FRONTEND_URL="${FRONTEND_URL:-}"
if [[ "${DEPLOY_FRONTEND}" == "1" || "${DEPLOY_FRONTEND}" == "true" ]]; then
  echo "==> Deploying frontend Cloud Run service"
  FRONTEND_URL=$(gcloud run deploy ai-frontend \
    --image "${FRONTEND_IMAGE}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    --set-env-vars "NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}" \
    --set-env-vars "NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}" \
    --format='value(status.url)')
  echo "✓ Frontend deployed at ${FRONTEND_URL}"
fi

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

