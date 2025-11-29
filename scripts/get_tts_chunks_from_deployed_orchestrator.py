#!/usr/bin/env python3
"""
Extract TTS input chunks from the last 3 cases in the deployed orchestrator.
Uses Google Cloud Logging to query logs from Cloud Run.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from collections import defaultdict

PROJECT_ID = "meta-478212"
SERVICE_NAME = "orchestrator"

def fetch_logs():
    """Fetch logs from Cloud Logging."""
    print("Querying Cloud Logging for orchestrator TTS chunks...")
    print(f"Project: {PROJECT_ID}")
    print(f"Service: {SERVICE_NAME}\n")
    
    # Fetch session logs
    print("Fetching session logs...")
    cmd = [
        "gcloud", "logging", "read",
        f"resource.type=cloud_run_revision AND resource.labels.service_name={SERVICE_NAME} AND jsonPayload.message=~\"Session.*TTS sentences\"",
        f"--project={PROJECT_ID}",
        "--limit=100",
        "--format=json",
        "--freshness=1d"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error fetching session logs: {result.stderr}")
        return None, None
    
    session_logs = json.loads(result.stdout) if result.stdout.strip() else []
    
    # Fetch TTS request logs
    print("Fetching TTS request logs...")
    cmd = [
        "gcloud", "logging", "read",
        f"resource.type=cloud_run_revision AND resource.labels.service_name={SERVICE_NAME} AND jsonPayload.message=~\"Sending TTS request\"",
        f"--project={PROJECT_ID}",
        "--limit=500",
        "--format=json",
        "--freshness=1d"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error fetching TTS logs: {result.stderr}")
        return session_logs, None
    
    tts_logs = json.loads(result.stdout) if result.stdout.strip() else []
    
    return session_logs, tts_logs

def parse_timestamp(ts_str):
    """Parse timestamp string to datetime."""
    try:
        # Handle RFC3339 format with microseconds
        if 'Z' in ts_str:
            ts_str = ts_str.replace('Z', '+00:00')
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        try:
            return datetime.fromisoformat(ts_str)
        except:
            return None

def extract_sessions(session_logs):
    """Extract session information from logs."""
    sessions = {}
    
    for log_entry in session_logs:
        try:
            payload = log_entry.get('jsonPayload', {})
            message = payload.get('message', '')
            timestamp = log_entry.get('timestamp', '')
            
            match = re.search(r'Session ([a-f0-9-]+) TTS sentences=(\d+)', message)
            if match:
                session_id = match.group(1)
                sentences_count = int(match.group(2))
                sessions[session_id] = {
                    'count': sentences_count,
                    'timestamp': timestamp,
                    'datetime': parse_timestamp(timestamp)
                }
        except Exception as e:
            continue
    
    return sessions

def extract_tts_requests(tts_logs):
    """Extract TTS request text from logs."""
    tts_requests = []
    
    for log_entry in tts_logs:
        try:
            payload = log_entry.get('jsonPayload', {})
            message = payload.get('message', '')
            timestamp = log_entry.get('timestamp', '')
            
            if 'Sending TTS request' not in message:
                continue
            
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
                'datetime': parse_timestamp(timestamp),
                'text': text
            })
        except Exception as e:
            continue
    
    return tts_requests

def match_tts_to_sessions(sessions, tts_requests):
    """Match TTS requests to sessions based on timestamps."""
    # Sort sessions by timestamp (most recent first)
    sorted_sessions = sorted(
        sessions.items(),
        key=lambda x: x[1]['datetime'] if x[1]['datetime'] else datetime.min,
        reverse=True
    )[:3]
    
    # Sort TTS requests by timestamp
    sorted_tts = sorted(
        tts_requests,
        key=lambda x: x['datetime'] if x['datetime'] else datetime.min
    )
    
    results = []
    
    for i, (session_id, session_info) in enumerate(sorted_sessions):
        session_dt = session_info['datetime']
        if not session_dt:
            continue
        
        # Find TTS requests for this session
        session_tts = []
        
        # Determine time window
        if i < len(sorted_sessions) - 1:
            # Not the last session - use next session as upper bound, but allow some overlap
            next_session_dt = sorted_sessions[i + 1][1]['datetime']
            if next_session_dt:
                # Use next session time, but if sessions are very close, extend window
                time_diff = (next_session_dt - session_dt).total_seconds()
                if time_diff < 60:  # Less than 1 minute between sessions
                    upper_bound = session_dt + timedelta(minutes=5)
                else:
                    upper_bound = next_session_dt
            else:
                upper_bound = session_dt + timedelta(minutes=10)
        else:
            # Last session - use 10 minute window
            upper_bound = session_dt + timedelta(minutes=10)
        
        # Find matching TTS requests
        for req in sorted_tts:
            req_dt = req['datetime']
            if not req_dt:
                continue
            
            if session_dt <= req_dt < upper_bound:
                session_tts.append(req)
        
        # Limit to expected count if we have more
        if len(session_tts) > session_info['count']:
            session_tts = session_tts[:session_info['count']]
        
        results.append({
            'session_id': session_id,
            'session_info': session_info,
            'tts_chunks': session_tts
        })
    
    return results

def main():
    """Main function."""
    session_logs, tts_logs = fetch_logs()
    
    if not session_logs:
        print("No session logs found.")
        return 1
    
    if not tts_logs:
        print("No TTS logs found.")
        return 1
    
    print(f"Found {len(session_logs)} session logs and {len(tts_logs)} TTS logs\n")
    
    # Extract data
    sessions = extract_sessions(session_logs)
    tts_requests = extract_tts_requests(tts_logs)
    
    if not sessions:
        print("No sessions with TTS found.")
        return 1
    
    # Match TTS to sessions
    results = match_tts_to_sessions(sessions, tts_requests)
    
    # Print results
    print("\n" + "="*80)
    print("TTS INPUT CHUNKS FOR LAST 3 CASES FROM DEPLOYED ORCHESTRATOR")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        session_id = result['session_id']
        session_info = result['session_info']
        tts_chunks = result['tts_chunks']
        
        print(f"\n{'='*80}")
        print(f"Case {i}: Session {session_id}")
        print(f"Session Start: {session_info['timestamp']}")
        print(f"Expected TTS Chunks: {session_info['count']}")
        print(f"{'='*80}")
        
        print(f"\nTTS Input Chunks ({len(tts_chunks)} chunks):")
        print("-" * 80)
        
        if not tts_chunks:
            print("  (No TTS chunks found for this session)")
        else:
            for j, chunk in enumerate(tts_chunks, 1):
                print(f"\nChunk {j}:")
                print(f"  Timestamp: {chunk['timestamp']}")
                print(f"  Text: {chunk['text']}")
    
    print("\n" + "="*80)
    print("Done!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

