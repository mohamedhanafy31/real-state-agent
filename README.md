# real-state-agent

Infrastructure for the MetaVR real estate AI stack, including:

- `Ai-P/`: Next.js 16 frontend experience
- `ai/rag/`: Retrieval-Augmented Generation FastAPI backend
- `ai/orchestrator/`: Real-time orchestrator coordinating ASR ↔ RAG ↔ TTS

Useful docs:

- `DOCKER_COMPOSE.md` – local multi-service setup
- `ai/rag/RAG_SYSTEM_OVERVIEW.md` – RAG architecture
- `ai/orchestrator/README.md` – orchestrator API details

## Environment Bootstrap

`scripts/sync-env.sh` keeps env files in sync across services. Run it after
cloning the repo or whenever you edit `.env`:

```
./scripts/sync-env.sh
```

The script copies `config/env.template` → `.env` (if missing) and fans the values
out to `Ai-P/.env.local`, `ai/orchestrator/.env`, and `ai/rag/.env`, which are
consumed by Docker Compose, local dev servers, and CI/CD jobs.

## Deployment Workflow

`./scripts/deploy_cloud_run.sh` builds the three containers, deploys them to
Cloud Run (`meta-478212` by default), captures the emitted URLs, and writes them
to `.env.cloudrun`. Optional flags allow propagating those URLs into GitHub
Secrets (requires `gh` and a repo token).

GitHub Actions automation (`.github/workflows/deploy.yml`) runs this script on
every push to `main` (and via manual dispatch). Provide these secrets in the
repository before enabling the workflow:

- `GCP_SERVICE_ACCOUNT_KEY` – JSON for a service account with Cloud Run,
  Cloud Build, Artifact Registry, and Secret Manager permissions.
- `GEMINI_API_KEY`
- `JWT_SECRET`
- `ASR_API_URL`, `TTS_API_URL` (optional overrides)
- `ASR_STREAMING_WS_URL` (optional, enables realtime STT)
- `RAG_API_URL`
- `NEXT_PUBLIC_ORCHESTRATOR_URL`
- `NEXT_PUBLIC_WS_URL`

Environment variables required before running:

```
export GEMINI_API_KEY=...
export JWT_SECRET=...
export ASR_API_URL=...   # optional (defaults to hosted endpoint)
export ASR_STREAMING_WS_URL=... # optional (enables streaming transcripts)
export TTS_API_URL=...   # optional
export PROJECT_ID=meta-478212
export REGION=us-central1
```

Run the script:

```
./scripts/deploy_cloud_run.sh
```

To auto-update GitHub secrets after deploy:

```
UPDATE_GITHUB_SECRETS=1 ./scripts/deploy_cloud_run.sh
```

## GitHub Actions

CI/CD workflows live under `.github/workflows/`. See `ci.yml` for build/test/publish jobs.

# real-state-agent
