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
  local build_args="${3:-}"

  echo "==> Building & pushing image ${image} from ${dir}" >&2
  local build_id
  if [[ -n "${build_args}" ]]; then
    echo "    With build args: ${build_args}" >&2
    build_id="$(
      cd "${dir}" && \
      gcloud builds submit --tag "${image}" --substitutions="${build_args}" . --async --format='value(name)'
    )"
  else
    build_id="$(
      cd "${dir}" && \
      gcloud builds submit --tag "${image}" . --async --format='value(name)'
    )"
  fi
  echo "    Build started with ID: ${build_id}" >&2
  printf '%s\n' "${build_id}"
}

wait_for_build() {
  local build_id="$1"
  local service_name="${2:-build}"

  echo "    [${service_name}] Waiting for build ${build_id} to complete..." >&2
  # Poll build status without streaming logs (avoids logs bucket perms)
  while true; do
    status="$(gcloud builds describe "${build_id}" --format='value(status)')"
    case "${status}" in
      SUCCESS)
        echo "    [${service_name}] ✓ Build ${build_id} succeeded." >&2
        break
        ;;
      FAILURE|CANCELLED)
        echo "✗ [${service_name}] Build ${build_id} failed with status: ${status}" >&2
        return 1
        ;;
      *)
        sleep 5
        ;;
    esac
  done
}

deploy_service() {
  local service_name="$1"
  local image="$2"
  shift 2
  
  echo "==> [${service_name}] Deploying to Cloud Run..." >&2
  local url
  url=$(gcloud run deploy "${service_name}" \
    --image "${image}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    "$@" \
    --format='value(status.url)')
  echo "✓ [${service_name}] Deployed at ${url}" >&2
  printf '%s\n' "${url}"
}

# Function to build and deploy a service
build_and_deploy() {
  local service_name="$1"
  local dir="$2"
  local image="$3"
  shift 3
  local deploy_args=("$@")
  
  local build_id
  build_id="$(start_build "${dir}" "${image}")"
  
  if ! wait_for_build "${build_id}" "${service_name}"; then
    echo "✗ [${service_name}] Build failed, aborting deployment" >&2
    return 1
  fi
  
  deploy_service "${service_name}" "${image}" "${deploy_args[@]}"
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

require_env GEMINI_API_KEY
require_env JWT_SECRET

# Orchestrator service key (for frontend to authenticate)
# If not set, generate a warning but continue (will use static token if available)
ORCHESTRATOR_SERVICE_KEY=${ORCHESTRATOR_SERVICE_KEY:-}
if [[ -z "${ORCHESTRATOR_SERVICE_KEY}" ]]; then
  echo "⚠️  Warning: ORCHESTRATOR_SERVICE_KEY not set. Frontend token endpoint will fail."
  echo "    Set ORCHESTRATOR_SERVICE_KEY to match orchestrator's SERVICE_API_KEY"
fi

ASR_API_URL=${ASR_API_URL:-https://arabic-asr-api-22251281831.us-central1.run.app}
TTS_API_URL=${TTS_API_URL:-https://arabic-tts-api-22251281831.us-central1.run.app}

# Start all builds in parallel, but deploy in dependency order
echo "==> Starting all builds in parallel"
RAG_URL="${RAG_API_URL:-}"
ORCH_URL="${ORCH_API_URL:-}"
RAG_BUILD_ID=""
ORCH_BUILD_ID=""
RAG_PID=""
ORCH_BUILD_PID=""

# Start RAG build in background
if [[ "${DEPLOY_RAG}" == "1" || "${DEPLOY_RAG}" == "true" ]]; then
  RAG_BUILD_ID="$(start_build "ai/rag" "${RAG_IMAGE}")"
  # Start waiting for RAG build in background
  (wait_for_build "${RAG_BUILD_ID}" "RAG") &
  RAG_PID=$!
  echo "  Started RAG build (PID: ${RAG_PID})"
fi

# Start Orchestrator build in background (can build in parallel)
if [[ "${DEPLOY_ORCH}" == "1" || "${DEPLOY_ORCH}" == "true" ]]; then
  ORCH_BUILD_ID="$(start_build "ai/orchestrator" "${ORCH_IMAGE}")"
  # Start waiting for Orchestrator build in background
  (wait_for_build "${ORCH_BUILD_ID}" "Orchestrator") &
  ORCH_BUILD_PID=$!
  echo "  Started Orchestrator build (PID: ${ORCH_BUILD_PID})"
fi

# Deploy RAG first (orchestrator depends on it)
if [[ -n "${RAG_PID}" ]]; then
  echo "==> Waiting for RAG build to complete, then deploying..."
  wait "${RAG_PID}"
  RAG_URL=$(deploy_service "rag-api" "${RAG_IMAGE}" \
    --memory=4Gi \
    --cpu=2 \
    --min-instances=1 \
    --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
    --set-env-vars "HF_TOKEN=${HF_TOKEN:-}" \
    --set-env-vars "LOG_LEVEL=INFO" \
    --set-env-vars "CORS_ORIGINS=*")
  echo "✓ RAG deployed at ${RAG_URL}"
fi

# Deploy Orchestrator (needs RAG_URL)
if [[ -n "${ORCH_BUILD_PID}" ]]; then
  echo "==> Waiting for Orchestrator build to complete, then deploying..."
  wait "${ORCH_BUILD_PID}"
  
  # Ensure we have RAG_URL
  if [[ -z "${RAG_URL}" ]]; then
    RAG_URL="${RAG_API_URL:-}"
    if [[ -z "${RAG_URL}" ]]; then
      echo "✗ Error: RAG_URL is required for orchestrator deployment but not available" >&2
      exit 1
    fi
    echo "  Using RAG_URL from environment: ${RAG_URL}"
  fi
  
  orch_deploy_args=(
    --memory=2Gi
    --cpu=2
    --set-env-vars "RAG_API_URL=${RAG_URL}"
    --set-env-vars "ASR_API_URL=${ASR_API_URL}"
    --set-env-vars "TTS_API_URL=${TTS_API_URL}"
    --set-env-vars "JWT_SECRET=${JWT_SECRET}"
    --set-env-vars "CORS_ORIGINS=*"
  )
  if [[ -n "${ORCHESTRATOR_SERVICE_KEY}" ]]; then
    orch_deploy_args+=(--set-env-vars "SERVICE_API_KEY=${ORCHESTRATOR_SERVICE_KEY}")
  fi
  
  ORCH_URL=$(deploy_service "orchestrator" "${ORCH_IMAGE}" "${orch_deploy_args[@]}")
  echo "✓ Orchestrator deployed at ${ORCH_URL}"
fi

# Build and deploy frontend (needs orchestrator URL)
ORCH_WS_URL=""
if [[ -n "${ORCH_URL}" ]]; then
  ORCH_WS_URL="${ORCH_URL/https:/wss:}"
  ORCH_WS_URL="${ORCH_WS_URL/http:/ws:}"
  ORCH_WS_URL="${ORCH_WS_URL%/}/ws/voice"
fi

FRONTEND_URL="${FRONTEND_URL:-}"
if [[ "${DEPLOY_FRONTEND}" == "1" || "${DEPLOY_FRONTEND}" == "true" ]]; then
  if [[ -z "${ORCH_URL}" || -z "${ORCH_WS_URL}" ]]; then
    echo "⚠️  Warning: Orchestrator URL not available, building frontend without build args"
    FRONTEND_BUILD_ID="$(start_build "Ai-P" "${FRONTEND_IMAGE}")"
    wait_for_build "${FRONTEND_BUILD_ID}" "Frontend"
    frontend_deploy_args_fallback=(
      --memory=4Gi
      --cpu=2
      --set-env-vars "NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}"
      --set-env-vars "NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}"
    )
    if [[ -n "${ORCH_URL}" ]]; then
      frontend_deploy_args_fallback+=(--set-env-vars "ORCHESTRATOR_BASE_URL=${ORCH_URL}")
    fi
    if [[ -n "${ORCHESTRATOR_SERVICE_KEY}" ]]; then
      frontend_deploy_args_fallback+=(--set-env-vars "ORCHESTRATOR_SERVICE_KEY=${ORCHESTRATOR_SERVICE_KEY}")
    fi
    
    FRONTEND_URL=$(deploy_service "ai-p" "${FRONTEND_IMAGE}" "${frontend_deploy_args_fallback[@]}")
  else
    # Build frontend with orchestrator URLs as build args
    echo "==> Building frontend with orchestrator URLs"
    FRONTEND_BUILD_ID="$(
      cd "Ai-P" && \
      gcloud builds submit \
        --config=cloudbuild.yaml \
        --substitutions=_NEXT_PUBLIC_ORCHESTRATOR_URL="${ORCH_URL}",_NEXT_PUBLIC_WS_URL="${ORCH_WS_URL}",_IMAGE_NAME="${FRONTEND_IMAGE}" \
        --async \
        --format='value(name)'
    )"
    echo "    Frontend build started with ID: ${FRONTEND_BUILD_ID}"
    wait_for_build "${FRONTEND_BUILD_ID}" "Frontend"
    
    echo "==> Deploying frontend Cloud Run service"
    frontend_deploy_args=(
      --memory=4Gi
      --cpu=2
      --set-env-vars "NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}"
      --set-env-vars "NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}"
    )
    if [[ -n "${ORCH_URL}" ]]; then
      frontend_deploy_args+=(--set-env-vars "ORCHESTRATOR_BASE_URL=${ORCH_URL}")
    fi
    if [[ -n "${ORCHESTRATOR_SERVICE_KEY}" ]]; then
      frontend_deploy_args+=(--set-env-vars "ORCHESTRATOR_SERVICE_KEY=${ORCHESTRATOR_SERVICE_KEY}")
    fi
    
    FRONTEND_URL=$(deploy_service "ai-p" "${FRONTEND_IMAGE}" "${frontend_deploy_args[@]}")
  fi
  
  if [[ -n "${FRONTEND_URL}" ]]; then
    echo "==> CORS is configured to allow all origins (*) for Cloud Run compatibility"
    echo "    To restrict CORS, set CORS_ORIGINS env var with comma-separated specific URLs"
  fi
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

echo ""
echo "=========================================="
echo "All services deployed successfully:"
echo "  Frontend: ${FRONTEND_URL}"
echo "  Orchestrator: ${ORCH_URL}"
echo "  RAG API: ${RAG_URL}"
echo "=========================================="
