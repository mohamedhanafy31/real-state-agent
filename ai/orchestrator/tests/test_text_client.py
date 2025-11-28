"""
Simple test client for text mode.
"""
import asyncio
import json
import websockets
import base64


async def test_text_session():
    """Test text mode session."""
    uri = "ws://localhost:8040/ws/text"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to orchestrator")
            
            # Start session
            start_msg = {
                "type": "start_session",
                "session_id": "test-session-123",
                "auth": "Bearer test-token",
                "metadata": {"lang": "ar"}
            }
            await websocket.send(json.dumps(start_msg))
            print(f"Sent: {start_msg['type']}")
            
            # Send text message
            text_msg = {
                "type": "text_message",
                "text": "ما هي أنواع الشقق المتاحة؟"
            }
            await websocket.send(json.dumps(text_msg))
            print(f"Sent: {text_msg['type']} - {text_msg['text']}")
            
            # Receive responses
            print("\nReceiving responses...")
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "rag_chunk":
                    chunk = data.get("chunk", "")
                    is_last = data.get("is_last", False)
                    print(f"RAG chunk ({'last' if is_last else 'partial'}): {chunk}")
                
                elif msg_type == "tts_audio":
                    seq = data.get("seq", 0)
                    is_last = data.get("is_last", False)
                    audio_b64 = data.get("audio_base64", "")
                    print(f"TTS audio chunk {seq} ({'last' if is_last else 'partial'}): {len(audio_b64)} bytes")
                    
                    # Save audio to file
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        filename = f"test_audio_{seq}.mp3"
                        with open(filename, "wb") as f:
                            f.write(audio_bytes)
                        print(f"  Saved to {filename}")
                
                elif msg_type == "error":
                    print(f"ERROR: {data.get('message')}")
                    break
                
                elif msg_type == "session_closed":
                    print(f"Session closed: {data.get('reason')}")
                    break
                
                else:
                    print(f"Received: {msg_type}")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_text_session())

