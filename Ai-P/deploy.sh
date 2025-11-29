#!/usr/bin/env bash
set -euo pipefail

# Configuration (matches GitHub Actions workflow)
PROJECT_ID=${PROJECT_ID:-meta-478212}
REGION=${REGION:-us-central1}
SERVICE_NAME="ai-p"
REPO="us-central1-docker.pkg.dev/${PROJECT_ID}/metavr-services"
IMAGE="${REPO}/${SERVICE_NAME}:latest"

# Get orchestrator URLs (can be overridden via env vars)
ORCH_URL=${NEXT_PUBLIC_ORCHESTRATOR_URL:-${ORCHESTRATOR_URL:-"https://orchestrator-dbgj63mjca-uc.a.run.app"}}
ORCH_WS_URL=${NEXT_PUBLIC_WS_URL:-${WS_URL:-""}}

# If WS URL not provided, derive it from orchestrator URL
if [[ -z "${ORCH_WS_URL}" ]]; then
  ORCH_WS_URL="${ORCH_URL/https:/wss:}"
  ORCH_WS_URL="${ORCH_WS_URL/http:/ws:}"
  ORCH_WS_URL="${ORCH_WS_URL%/}/ws/voice"
fi

echo "==> Deploying ${SERVICE_NAME} to Cloud Run"
echo "    Project: ${PROJECT_ID}"
echo "    Region: ${REGION}"
echo "    Image: ${IMAGE}"
echo "    Orchestrator URL: ${ORCH_URL}"
echo "    WebSocket URL: ${ORCH_WS_URL}"
echo ""

# Ensure we're in the script directory
cd "$(dirname "$0")"

# Ensure gcloud is configured
gcloud config set project "${PROJECT_ID}" >/dev/null

# Build frontend with orchestrator URLs as build args (matches CI/CD)
echo "==> Building frontend with orchestrator URLs"
BUILD_ID=$(
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_NEXT_PUBLIC_ORCHESTRATOR_URL="${ORCH_URL}",_NEXT_PUBLIC_WS_URL="${ORCH_WS_URL}",_IMAGE_NAME="${IMAGE}" \
    --async \
    --format='value(name)' \
    .
)

if [[ -z "${BUILD_ID}" ]]; then
  echo "✗ Failed to start build"
  exit 1
fi

echo "    Build started with ID: ${BUILD_ID}"

# Wait for build to complete (matches CI/CD pattern)
echo "    Waiting for build to complete..."
while true; do
  STATUS=$(gcloud builds describe "${BUILD_ID}" --format='value(status)' 2>/dev/null || echo "UNKNOWN")
  case "${STATUS}" in
    SUCCESS)
      echo "    ✓ Build ${BUILD_ID} succeeded."
      break
      ;;
    FAILURE|CANCELLED)
      echo "✗ Build ${BUILD_ID} failed with status: ${STATUS}"
      exit 1
      ;;
    *)
      sleep 5
      ;;
  esac
done

echo ""

# Prepare deployment arguments (matches CI/CD configuration)
echo "==> Deploying to Cloud Run"
frontend_deploy_args=(
  --memory=4Gi
  --cpu=2
  --set-env-vars "NEXT_PUBLIC_ORCHESTRATOR_URL=${ORCH_URL}"
  --set-env-vars "NEXT_PUBLIC_WS_URL=${ORCH_WS_URL}"
)

# Add ORCHESTRATOR_BASE_URL
if [[ -n "${ORCH_URL}" ]]; then
  frontend_deploy_args+=(--set-env-vars "ORCHESTRATOR_BASE_URL=${ORCH_URL}")
fi

# Add ORCHESTRATOR_SERVICE_KEY if provided
if [[ -n "${ORCHESTRATOR_SERVICE_KEY:-}" ]]; then
  frontend_deploy_args+=(--set-env-vars "ORCHESTRATOR_SERVICE_KEY=${ORCHESTRATOR_SERVICE_KEY}")
fi

# Deploy to Cloud Run
SERVICE_URL=$(
  gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated \
    --platform managed \
    "${frontend_deploy_args[@]}" \
    --format='value(status.url)'
)

if [[ -z "${SERVICE_URL}" ]]; then
  echo "✗ Deployment failed"
  exit 1
fi

echo ""
echo "=========================================="
echo "✓ Deployment completed successfully!"
echo "  Service: ${SERVICE_NAME}"
echo "  URL: ${SERVICE_URL}"
echo "=========================================="

