#!/usr/bin/env python3
"""
Verbose streaming test to see exactly what Gemini sends.
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"
QUESTION = "أخبرني عن أرخص 3 شقق"

print("🔍 VERBOSE STREAMING TEST")
print("=" * 70)
print(f"Question: {QUESTION}\n")

url = f"{API_BASE}/query/stream"
payload = {
    "question": QUESTION,
    "session_id": "test_verbose",
    "retrieval_k": 5,
    "temperature": 0.7
}

start = time.time()
chunk_num = 0
chunk_sizes = []

try:
    response = requests.post(url, json=payload, stream=True, timeout=60)
    
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        exit(1)
    
    print("📡 Connected. Analyzing stream...\n")
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
                
                if data.get('type') == 'metadata':
                    print(f"[{elapsed:.3f}s] 📊 METADATA")
                    print(f"   Retrieval + Unit Selection completed")
                    print()
                    
                elif data.get('type') == 'chunk':
                    chunk_num += 1
                    text = data.get('text', '')
                    chunk_size = len(text)
                    chunk_sizes.append(chunk_size)
                    
                    # Show chunk details
                    time_since_last = elapsed - (chunk_sizes[-2] if len(chunk_sizes) > 1 else 0)
                    print(f"[{elapsed:6.3f}s] Chunk #{chunk_num:2d} | Size: {chunk_size:3d} chars | Text: {text[:50]!r}...")
                    
                elif data.get('type') == 'done':
                    total = time.time() - start
                    print("-" * 70)
                    print(f"\n✅ STREAM COMPLETE")
                    print(f"   Total time: {total:.3f}s")
                    print(f"   Total chunks: {chunk_num}")
                    print(f"   Total chars: {sum(chunk_sizes)}")
                    print(f"   Avg chunk size: {sum(chunk_sizes)/len(chunk_sizes):.1f} chars")
                    print(f"   Min chunk size: {min(chunk_sizes)} chars")
                    print(f"   Max chunk size: {max(chunk_sizes)} chars")
                    
                    # Analysis
                    print(f"\n🔍 ANALYSIS:")
                    if chunk_num > 5:
                        print("   ✅ Multiple chunks received - Real streaming confirmed!")
                    if min(chunk_sizes) < 10:
                        print("   ✅ Small chunks detected - Granular streaming!")
                    if total < 10:
                        print("   ✅ Fast response - Efficient streaming!")
                    
                    break
                    
                elif data.get('type') == 'error':
                    print(f"\n❌ Error: {data.get('message')}")
                    break
                    
            except json.JSONDecodeError:
                continue
                
except requests.exceptions.ConnectionError:
    print(f"❌ Cannot connect to {API_BASE}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

