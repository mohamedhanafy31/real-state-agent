# Orchestrator Authentication Setup

## Issue

The frontend is getting a 500 error: `"ORCHESTRATOR_SERVICE_KEY is not configured"` when trying to fetch authentication tokens.

## Solution

The frontend needs `ORCHESTRATOR_SERVICE_KEY` to authenticate with the orchestrator. This must match the orchestrator's `SERVICE_API_KEY`.

## Setup Steps

### 1. Set GitHub Actions Secret

Add `ORCHESTRATOR_SERVICE_KEY` to your GitHub repository secrets:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ORCHESTRATOR_SERVICE_KEY`
5. Value: Your service key (e.g., `super-long-shared-key-82ef7df6b4c64e329c8c1b5b1a0b21f5`)
6. Click **Add secret**

### 2. For Local Deployment

When running the deployment script locally, set the environment variable:

```bash
export ORCHESTRATOR_SERVICE_KEY="super-long-shared-key-82ef7df6b4c64e329c8c1b5b1a0b21f5"
./scripts/deploy_cloud_run.sh
```

### 3. Verify Deployment

After deployment, the following environment variables should be set:

**Frontend (ai-p) service:**
- `ORCHESTRATOR_BASE_URL` - Orchestrator HTTP URL
- `ORCHESTRATOR_SERVICE_KEY` - Service key for authentication

**Orchestrator service:**
- `SERVICE_API_KEY` - Must match `ORCHESTRATOR_SERVICE_KEY` from frontend

### 4. Check Current Deployment

To verify the environment variables are set correctly:

```bash
# Check frontend
gcloud run services describe ai-p \
  --project=meta-478212 \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"

# Check orchestrator
gcloud run services describe orchestrator \
  --project=meta-478212 \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"
```

### 5. Manual Update (if needed)

If you need to update the service key manually:

```bash
# Update frontend
gcloud run services update ai-p \
  --project=meta-478212 \
  --region=us-central1 \
  --set-env-vars "ORCHESTRATOR_SERVICE_KEY=your-service-key-here" \
  --set-env-vars "ORCHESTRATOR_BASE_URL=https://orchestrator-xxx.run.app"

# Update orchestrator
gcloud run services update orchestrator \
  --project=meta-478212 \
  --region=us-central1 \
  --set-env-vars "SERVICE_API_KEY=your-service-key-here"
```

## How It Works

1. Frontend calls `/api/orchestrator/token` (Next.js API route)
2. The API route uses `ORCHESTRATOR_SERVICE_KEY` to authenticate with orchestrator
3. Orchestrator's `/auth/token` endpoint validates the `X-Service-Key` header
4. If valid, orchestrator returns a JWT token
5. Frontend uses this JWT token to authenticate WebSocket connections

## Security Notes

- The service key should be a long, random string
- Keep it secret - never commit it to the repository
- Use GitHub Secrets for CI/CD deployments
- Rotate the key periodically for better security

