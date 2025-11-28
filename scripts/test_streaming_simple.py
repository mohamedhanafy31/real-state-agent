#!/usr/bin/env python3
"""
Simple visual test to see streaming in real-time.
Shows chunks as they arrive with timestamps.
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"
QUESTION = "أخبرني عن أرخص 3 شقق"

print("🚀 Testing Real-Time Streaming")
print("=" * 70)
print(f"Question: {QUESTION}\n")

url = f"{API_BASE}/query/stream"
payload = {
    "question": QUESTION,
    "session_id": "test",
    "retrieval_k": 5,
    "temperature": 0.7
}

start = time.time()
chunk_num = 0

try:
    response = requests.post(url, json=payload, stream=True, timeout=60)
    
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        exit(1)
    
    print("📡 Connected. Streaming response:\n")
    print("-" * 70)
    
    buffer = ""
    for line in response.iter_lines():
        if not line:
            continue
        
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            try:
                data = json.loads(line_str[6:])
                elapsed = time.time() - start
                
                if data.get('type') == 'chunk':
                    chunk_num += 1
                    text = data.get('text', '')
                    # Print chunk with timestamp
                    print(f"[{elapsed:6.3f}s] Chunk #{chunk_num:2d}: {text!r}", flush=True)
                    
                elif data.get('type') == 'done':
                    total = time.time() - start
                    print("-" * 70)
                    print(f"\n✅ Complete in {total:.3f}s | {chunk_num} chunks received")
                    print(f"\nFull response ({len(data.get('full_text', ''))} chars):")
                    print(data.get('full_text', ''))
                    break
                    
                elif data.get('type') == 'error':
                    print(f"\n❌ Error: {data.get('message')}")
                    break
                    
            except json.JSONDecodeError:
                continue
                
except requests.exceptions.ConnectionError:
    print(f"❌ Cannot connect to {API_BASE}")
    print("   Start the server first: cd ai/rag && python -m uvicorn app.api:app --reload")
except Exception as e:
    print(f"❌ Error: {e}")

