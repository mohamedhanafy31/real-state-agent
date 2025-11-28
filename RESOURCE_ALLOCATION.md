# Cloud Run Resource Allocation

This document summarizes the resource allocations for each service deployed on Google Cloud Run.

## Service Resources Summary

### 1. RAG API (`rag-api`)
- **Memory**: 4 GiB
- **CPU**: 2000m (2 vCPU)
- **Timeout**: 300 seconds (5 minutes)
- **Concurrency**: 80 requests per instance
- **Service Account**: Default compute service account
- **Region**: us-central1
- **Project**: meta-478212

**Notes**: 
- Highest memory allocation due to RAG processing (vector embeddings, FAISS index, Gemini API calls)
- Memory-intensive operations include document indexing and similarity search
- 2 vCPU for better parallel processing of vector operations

---

### 2. Orchestrator (`orchestrator`)
- **Memory**: 2 GiB
- **CPU**: 2000m (2 vCPU)
- **Timeout**: 300 seconds (5 minutes)
- **Concurrency**: 80 requests per instance
- **Service Account**: Default compute service account
- **Region**: us-central1
- **Project**: meta-478212

**Notes**:
- Increased memory for handling multiple concurrent WebSocket connections
- 2 vCPU for better parallel processing of multiple sessions
- Handles WebSocket connections for voice mode
- Manages session state and coordinates ASR → RAG → TTS flow

---

### 3. Frontend (`ai-p`)
- **Memory**: 4 GiB
- **CPU**: 2000m (2 vCPU)
- **Timeout**: 300 seconds (5 minutes)
- **Concurrency**: 80 requests per instance
- **Service Account**: Default compute service account
- **Region**: us-central1
- **Project**: meta-478212

**Notes**:
- Next.js application serving static assets and API routes
- Increased memory for better performance with large client-side bundles
- 2 vCPU for faster server-side rendering and API route processing
- Handles client-side rendering and API proxy requests

---

## Resource Configuration in Deployment Script

All services now have explicit resource configuration in the deployment script:

```bash
# RAG API deployment (scripts/deploy_cloud_run.sh:164-169)
deploy_service "rag-api" "${RAG_IMAGE}" \
  --memory=4Gi \
  --cpu=2 \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --set-env-vars "LOG_LEVEL=INFO" \
  --set-env-vars "CORS_ORIGINS=*"

# Orchestrator deployment (scripts/deploy_cloud_run.sh:188-201)
deploy_service "orchestrator" "${ORCH_IMAGE}" \
  --memory=2Gi \
  --cpu=2 \
  "${orch_deploy_args[@]}"

# Frontend deployment (scripts/deploy_cloud_run.sh:248-260)
deploy_service "ai-p" "${FRONTEND_IMAGE}" \
  --memory=4Gi \
  --cpu=2 \
  "${frontend_deploy_args[@]}"
```

---

## Cost Implications

### Memory Pricing (us-central1)
- **2 GiB**: ~$0.00001 per request-second
- **4 GiB**: ~$0.00002 per request-second (2x more expensive than 2 GiB)

### CPU Pricing
- All services use 2 vCPU: ~$0.000005 per request-second (2x more expensive than 1 vCPU)

### Estimated Monthly Costs (assuming 24/7 operation)
- **RAG API**: Higher cost due to 4 GiB memory
- **Orchestrator**: Standard cost
- **Frontend**: Standard cost

---

## Recommendations

### Current Configuration
✅ **RAG API**: 4 GiB + 2 vCPU is appropriate for vector search and LLM operations
✅ **Orchestrator**: 2 GiB + 2 vCPU provides good performance for concurrent WebSocket connections
✅ **Frontend**: 4 GiB + 2 vCPU ensures fast server-side rendering and API processing

### Potential Optimizations

1. **Monitor Resource Usage**: 
   - Use Cloud Run metrics to track actual CPU and memory utilization
   - Adjust if services are consistently underutilized or hitting limits

2. **Cost Optimization**:
   - Current configuration prioritizes performance over cost
   - Consider reducing resources if usage patterns show lower requirements

3. **Timeout Settings**:
   - 300 seconds (5 minutes) is appropriate for long-running RAG queries
   - Consider reducing for frontend if API routes complete faster

4. **Concurrency**:
   - 80 concurrent requests per instance is a good default
   - Monitor instance utilization and adjust if needed

---

## Monitoring

To monitor resource usage:

```bash
# Check service metrics
gcloud run services describe <service-name> \
  --project=meta-478212 \
  --region=us-central1 \
  --format="yaml(spec.template.spec.containers[0].resources)"

# View Cloud Run metrics in Console
# https://console.cloud.google.com/run/detail/us-central1/<service-name>/metrics
```

---

## Updating Resources

To update resource allocations, modify the deployment script:

```bash
# Example: Increase orchestrator memory
deploy_service "orchestrator" "${ORCH_IMAGE}" \
  --memory=1Gi \
  --cpu=2 \
  --timeout=600 \
  --concurrency=100 \
  "${orch_deploy_args[@]}"
```

Then redeploy the service using the deployment script.

