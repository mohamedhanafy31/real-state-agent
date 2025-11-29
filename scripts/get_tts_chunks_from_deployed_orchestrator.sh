#!/bin/bash
# Script to extract TTS input chunks from the last 3 cases in the deployed orchestrator
# Uses Google Cloud Logging to query logs from Cloud Run

PROJECT_ID="meta-478212"
SERVICE_NAME="orchestrator"
REGION="us-central1"

echo "Querying Cloud Logging for orchestrator TTS chunks..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo ""

# Query for TTS-related logs
echo "Fetching TTS logs from Cloud Run..."
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND (jsonPayload.message=~\"Sending TTS request\" OR jsonPayload.message=~\"Session.*TTS sentences\")" \
  --project=$PROJECT_ID \
  --limit=1000 \
  --format=json \
  --freshness=7d \
  > /tmp/orchestrator_tts_logs.json

# Process logs with Python
python3 << 'PYTHON_SCRIPT'
import json
import re
from datetime import datetime
from collections import defaultdict

# Read logs
try:
    with open('/tmp/orchestrator_tts_logs.json', 'r') as f:
        logs = json.load(f)
except Exception as e:
    print(f"Error reading logs: {e}")
    exit(1)

if not logs:
    print("No logs found in the file.")
    exit(1)

# Parse logs
sessions = {}
tts_requests = []

for log_entry in logs:
    try:
        # Extract timestamp
        timestamp = log_entry.get('timestamp', '')
        if not timestamp:
            timestamp = log_entry.get('receiveTimestamp', '')
        
        # Extract message
        payload = log_entry.get('jsonPayload', {})
        message = payload.get('message', '')
        
        if not message:
            continue
        
        # Find session TTS sentences
        match = re.search(r'Session ([a-f0-9-]+) TTS sentences=(\d+)', message)
        if match:
            session_id = match.group(1)
            sentences_count = int(match.group(2))
            sessions[session_id] = {
                'count': sentences_count,
                'timestamp': timestamp
            }
        
        # Find TTS requests
        if 'Sending TTS request' in message:
            # Extract text - handle both formats
            match1 = re.search(r'Sending TTS request \(voice=[^,]+,\s*chars=\d+\):\s*(.+?)(?:\s*\(lang:|$)', message)
            match2 = re.search(r'Sending TTS request:\s*(.+?)(?:\s*\(lang:|$)', message)
            if match1:
                text = match1.group(1).strip()
            elif match2:
                text = match2.group(1).strip()
            else:
                continue
            
            tts_requests.append({
                'timestamp': timestamp,
                'text': text
            })
    except Exception as e:
        continue

# Sort sessions by timestamp (most recent first)
sorted_sessions = sorted(sessions.items(), key=lambda x: x[1]['timestamp'], reverse=True)[:3]

if not sorted_sessions:
    print("No sessions with TTS found in the logs.")
    exit(0)

print("\n" + "="*80)
print("TTS INPUT CHUNKS FOR LAST 3 CASES FROM DEPLOYED ORCHESTRATOR")
print("="*80)

# For each session, find TTS requests
for i, (session_id, session_info) in enumerate(sorted_sessions, 1):
    print(f"\n{'='*80}")
    print(f"Case {i}: Session {session_id}")
    print(f"Session Start: {session_info['timestamp']}")
    print(f"Expected TTS Chunks: {session_info['count']}")
    print(f"{'='*80}")
    
    # Find TTS requests for this session
    # We'll match by timestamp proximity
    session_time = session_info['timestamp']
    session_tts = []
    
    # Find requests that occur after this session start
    for req in sorted(tts_requests, key=lambda x: x['timestamp']):
        req_time = req['timestamp']
        if req_time >= session_time:
            # Check if it's before the next session or within reasonable time (10 minutes)
            if i < len(sorted_sessions):
                next_session_time = sorted_sessions[i][1]['timestamp']
                if req_time < next_session_time:
                    session_tts.append(req)
            else:
                # Last session - take all remaining within 10 minutes of session start
                # Parse timestamps for comparison
                try:
                    from dateutil import parser
                    session_dt = parser.parse(session_time)
                    req_dt = parser.parse(req_time)
                    if (req_dt - session_dt).total_seconds() < 600:  # 10 minutes
                        session_tts.append(req)
                except:
                    # Fallback: take first N chunks
                    if len(session_tts) < session_info['count']:
                        session_tts.append(req)
    
    # For better matching, limit to first N chunks where N = expected count
    if len(session_tts) > session_info['count']:
        session_tts = session_tts[:session_info['count']]
    
    print(f"\nTTS Input Chunks ({len(session_tts)} chunks):")
    print("-" * 80)
    
    if not session_tts:
        print("  (No TTS chunks found for this session)")
    else:
        for j, req in enumerate(session_tts, 1):
            print(f"\nChunk {j}:")
            print(f"  Timestamp: {req['timestamp']}")
            print(f"  Text: {req['text']}")

print("\n" + "="*80)
print("Done!")
PYTHON_SCRIPT

# Cleanup
rm -f /tmp/orchestrator_tts_logs.json

