#!/usr/bin/env python3
"""
Test script to verify real-time streaming from the API.
This will show if chunks arrive incrementally (real streaming) 
or all at once at the end (buffered).
"""

import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"  # Adjust if your server runs on different port
TEST_QUESTION = "أخبرني عن أرخص 3 شقق"

def test_streaming():
    """Test if streaming is real-time or buffered."""
    print("=" * 60)
    print("STREAMING TEST - Real-time vs Buffered")
    print("=" * 60)
    print(f"\nQuestion: {TEST_QUESTION}")
    print(f"Endpoint: {API_BASE}/query/stream")
    print("\n" + "-" * 60)
    print("Starting stream...\n")
    
    url = f"{API_BASE}/query/stream"
    payload = {
        "question": TEST_QUESTION,
        "session_id": "test_stream",
        "retrieval_k": 5,
        "temperature": 0.7
    }
    
    start_time = time.time()
    first_chunk_time = None
    chunk_count = 0
    total_text_length = 0
    chunk_times = []
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,  # Important: enable streaming
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return
        
        print("✅ Connection established. Waiting for chunks...\n")
        print("Chunk Timeline:")
        print("-" * 60)
        
        buffer = ""
        for line in response.iter_lines():
            if not line:
                continue
            
            line_str = line.decode('utf-8')
            buffer += line_str + "\n"
            
            # Process complete SSE messages
            if line_str.startswith('data: '):
                try:
                    data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                    event_type = data.get('type')
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    if event_type == 'metadata':
                        print(f"\n[{elapsed:.3f}s] 📊 METADATA received:")
                        print(f"   - Chunks: {data.get('num_chunks', 0)}")
                        print(f"   - Units: {data.get('num_structured_units', 0)}")
                        print(f"   - Top score: {data.get('top_score')}")
                        print()
                        
                    elif event_type == 'chunk':
                        chunk_count += 1
                        chunk_text = data.get('text', '')
                        total_text_length += len(chunk_text)
                        
                        if first_chunk_time is None:
                            first_chunk_time = elapsed
                            time_to_first_chunk = first_chunk_time
                            print(f"⚡ FIRST CHUNK arrived at {time_to_first_chunk:.3f}s")
                            print(f"   Text: '{chunk_text[:50]}...'")
                        else:
                            time_since_last = elapsed - chunk_times[-1] if chunk_times else 0
                            print(f"[{elapsed:.3f}s] Chunk #{chunk_count} (+{time_since_last:.3f}s): '{chunk_text[:30]}...'")
                        
                        chunk_times.append(elapsed)
                        
                    elif event_type == 'done':
                        total_time = elapsed
                        print(f"\n[{elapsed:.3f}s] ✅ STREAM COMPLETE")
                        print(f"   Full text length: {len(data.get('full_text', ''))} chars")
                        print()
                        
                    elif event_type == 'error':
                        print(f"\n❌ ERROR: {data.get('message')}")
                        return
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    continue
        
        # Analysis
        print("=" * 60)
        print("STREAMING ANALYSIS")
        print("=" * 60)
        
        if chunk_count == 0:
            print("❌ No chunks received - streaming may not be working")
            return
        
        if first_chunk_time is None:
            print("❌ No chunks received")
            return
        
        time_to_first_chunk = first_chunk_time
        total_time = time.time() - start_time
        avg_time_between_chunks = sum(
            chunk_times[i] - chunk_times[i-1] 
            for i in range(1, len(chunk_times))
        ) / (len(chunk_times) - 1) if len(chunk_times) > 1 else 0
        
        print(f"\n📊 Statistics:")
        print(f"   Total chunks received: {chunk_count}")
        print(f"   Total text length: {total_text_length} characters")
        print(f"   Time to first chunk: {time_to_first_chunk:.3f}s")
        print(f"   Total stream duration: {total_time:.3f}s")
        print(f"   Average time between chunks: {avg_time_between_chunks:.3f}s")
        
        # Determine if it's real streaming
        print(f"\n🔍 Analysis:")
        if time_to_first_chunk < 2.0 and chunk_count > 1:
            print("   ✅ REAL STREAMING DETECTED")
            print("   - First chunk arrived quickly (< 2s)")
            print("   - Multiple chunks received incrementally")
            print("   - Chunks arrived at different times")
        elif time_to_first_chunk > 5.0 and chunk_count == 1:
            print("   ⚠️  POSSIBLY BUFFERED")
            print("   - Long delay before first chunk (> 5s)")
            print("   - Only one chunk received (entire response)")
        else:
            print("   ⚠️  UNCLEAR - Check chunk timing above")
        
        # Show chunk distribution
        if len(chunk_times) > 1:
            print(f"\n📈 Chunk arrival timeline:")
            for i, chunk_time in enumerate(chunk_times[:10], 1):  # Show first 10
                delay = chunk_time - chunk_times[0] if i > 1 else 0
                print(f"   Chunk {i}: +{delay:.3f}s from start")
            if len(chunk_times) > 10:
                print(f"   ... and {len(chunk_times) - 10} more chunks")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {API_BASE}")
        print("   Make sure the server is running!")
    except requests.exceptions.Timeout:
        print("❌ Timeout: Request took too long")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_streaming()

