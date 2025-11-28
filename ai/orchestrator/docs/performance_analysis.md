# Orchestrator Performance Analysis

## Executive Summary

After deep analysis of orchestrator and RAG service logs, the root cause of timeouts and slow operations has been identified. The issue is a **timeout mismatch** between the orchestrator and the Gemini API client, combined with **Gemini API connectivity issues**.

---

## Issue #1: Timeout Mismatch (Primary Issue)

### Problem
- **Orchestrator timeout**: 60 seconds (`RAG_TIMEOUT=60`)
- **Gemini API client timeout**: 600 seconds (10 minutes - default from Google's API client)
- **Result**: When Gemini API has connectivity issues, the RAG service waits up to 600s, but the orchestrator times out after 60s and closes the connection.

### Evidence from Logs

**Orchestrator Log (14:21:35 - 14:22:52):**
```
14:21:35.685  Streaming RAG response for session ...
14:21:35.698  Starting RAG stream query: كنت عايز اعرف تفاصيل عن الشقه دي؟...
14:21:52.093  HTTP Request: POST http://localhost:8000/query/stream "200 OK"
14:22:52.097  RAG API timeout after 60s
14:22:52.100  Error streaming RAG response: RAG service timeout after 60 seconds
14:22:52.102  Session ... closed: rag_error
```

**RAG Service Log (16:21:35 - 16:21:52):**
```
16:21:35  Processing streaming query: كنت عايز اعرف تفاصيل عن الشقه دي؟
16:21:52  Response: 200 - Process time: 16.393s
```

**Note**: The RAG service actually completed in 16.4 seconds, but the orchestrator timed out at 60s. This suggests the timeout happened on a different request, or there was a delay in the HTTP response.

---

## Issue #2: Gemini API Connectivity Problems

### Problem
The Gemini API client is experiencing connection failures and retrying for up to 600 seconds:

```
ERROR | src.generator.llm_generator | generate_stream | 282
Error in streaming generation: Timeout of 600.0s exceeded, 
last exception: 503 failed to connect to all addresses; 
last error: UNAVAILABLE: ipv4:142.250.200.234:443: Socket closed
```

### Root Cause
- **IP Address**: `142.250.200.234` is a Google IP (Gemini API endpoint)
- **Error**: `503 ServiceUnavailable` with `UNAVAILABLE: Socket closed`
- **Behavior**: Google's API client retries with exponential backoff for up to 600 seconds
- **Impact**: The RAG service hangs waiting for Gemini, causing orchestrator timeouts

---

## Issue #3: Selector Performance

### Observations
- **Fast queries**: 2-3 seconds (e.g., "اي ارخص ثلاث شقق موجودين" - 3.137s)
- **Slow queries**: 14-16 seconds (e.g., "كنت عايز اعرف تفاصيل عن الشقه دي؟" - 16.393s)
- **Selector time**: Most of the delay is in the selector (unit selection), not the generator

### Analysis
The selector takes longer when:
1. It needs to filter within `last_units` (conversational references)
2. It needs to generate pandas code via LLM
3. It needs to execute complex queries on the CSV

---

## Performance Breakdown

### Typical Request Flow (Successful)
1. **ASR**: 2-4 seconds (cloud service)
2. **RAG Service**:
   - Selector: 2-16 seconds (varies by query complexity)
   - Generator: 1-3 seconds (Gemini API)
   - **Total**: 3-19 seconds
3. **TTS**: 1-5 seconds per sentence (5 sentences ≈ 15s total)
4. **Total End-to-End**: ~20-40 seconds

### Failed Request Flow (Timeout)
1. **ASR**: 2-4 seconds ✅
2. **RAG Service**:
   - Selector: 2-16 seconds ✅
   - Generator: **Hangs waiting for Gemini API** ❌
   - Gemini retries for up to 600s
   - Orchestrator times out at 60s
3. **Result**: Session closed with `rag_error`

---

## Recommendations

### 1. Configure Gemini API Timeout (High Priority)
**Action**: Add explicit timeout configuration to the Gemini client in `ai/rag/src/generator/llm_generator.py`

**Implementation**:
- Set a timeout of 30-45 seconds for Gemini API calls
- This should be less than the orchestrator's 60s timeout
- Use `google.api_core.timeout` to configure request timeouts

**Benefits**:
- Prevents RAG service from hanging for 600 seconds
- Faster failure detection and error reporting
- Better user experience with quicker error feedback

### 2. Add Retry Logic with Circuit Breaker (Medium Priority)
**Action**: Implement a circuit breaker pattern for Gemini API calls

**Implementation**:
- Track consecutive failures
- After N failures, temporarily stop calling Gemini API
- Return a graceful error message to the user
- Automatically retry after a cooldown period

**Benefits**:
- Prevents cascading failures
- Reduces load on Gemini API during outages
- Faster error recovery

### 3. Increase Orchestrator Timeout (Low Priority - Not Recommended)
**Action**: Increase `RAG_TIMEOUT` from 60s to 90-120s

**Why Not Recommended**:
- Doesn't solve the root cause (Gemini connectivity)
- Makes the system slower to fail
- Users will wait longer for errors

### 4. Optimize Selector Performance (Medium Priority)
**Action**: Profile and optimize the unit selector

**Potential Optimizations**:
- Cache frequently used queries
- Pre-compile common pandas filters
- Use more efficient data structures for unit lookup
- Parallelize selector and retriever when possible

**Benefits**:
- Faster response times for complex queries
- Better user experience

### 5. Add Better Error Handling and Logging (Low Priority)
**Action**: Improve error messages and logging

**Implementation**:
- Log Gemini API connection errors with more context
- Add metrics for timeout rates
- Alert on high timeout rates
- Provide user-friendly error messages

---

## Immediate Action Items

1. **Configure Gemini timeout** to 30-45 seconds
2. **Test** with the problematic query: "كنت عايز اعرف تفاصيل عن الشقه دي؟"
3. **Monitor** logs for timeout improvements
4. **Consider** implementing circuit breaker if timeouts persist

---

## Configuration Changes Needed

### File: `ai/rag/src/generator/llm_generator.py`
- Add timeout configuration to `generate_content()` calls
- Use `google.api_core.timeout` with a 30-45 second limit

### File: `ai/orchestrator/app/core/config.py`
- Current `rag_timeout: 60` is appropriate
- No changes needed here

---

## Monitoring Recommendations

1. **Track timeout rates**: Log when timeouts occur and their frequency
2. **Track Gemini API errors**: Monitor 503/500 errors from Gemini
3. **Track selector performance**: Log selector execution time separately
4. **Track end-to-end latency**: Measure total request time from ASR to TTS

---

## Conclusion

The primary issue is **Gemini API connectivity problems** combined with a **600-second default timeout** that exceeds the orchestrator's 60-second timeout. The solution is to configure the Gemini client with a shorter timeout (30-45 seconds) to fail fast and provide better error handling.

The orchestrator itself is performing well - the bottleneck is in the RAG service's interaction with the Gemini API.

