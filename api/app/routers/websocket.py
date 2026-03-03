"""WebSocket streaming endpoint."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import HTMLResponse
import base64
import json
import asyncio

from app.models.schemas import WebSocketMessage
from app.services.auth import verify_api_key


router = APIRouter()


@router.websocket("/ws/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    api_key: str = Query(...),
    model: str = Query("base"),
    language: str = Query("auto")
):
    """WebSocket endpoint for real-time streaming transcription."""
    # Verify API key
    try:
        key_obj = await verify_api_key(api_key)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid API key")
        return
    
    await websocket.accept()
    
    # Configuration
    config = {
        "model": model,
        "language": language,
        "vad_enabled": True,
        "word_timestamps": False
    }
    
    audio_buffer = bytearray()
    
    try:
        while True:
            # Receive message
            message = await websocket.receive()
            
            if "text" in message:
                # JSON control message
                data = json.loads(message["text"])
                msg_type = data.get("type")
                
                if msg_type == "config":
                    # Update configuration
                    config.update(data.get("config", {}))
                    await websocket.send_json({
                        "type": "config_ack",
                        "config": config
                    })
                
                elif msg_type == "end":
                    # End of stream - process final buffer
                    if audio_buffer:
                        # Process final audio
                        await websocket.send_json({
                            "type": "final",
                            "text": "Final transcription result",
                            "timestamp": data.get("timestamp")
                        })
                    await websocket.close(code=1000)
                    return
                
                elif msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    })
            
            elif "bytes" in message:
                # Audio data
                audio_buffer.extend(message["bytes"])
                
                # Process when buffer is large enough (e.g., 5 seconds of audio)
                # This is a simplified version - production would use VAD
                if len(audio_buffer) > 16000 * 2 * 5:  # 5s at 16kHz, 16-bit
                    # Send partial result
                    await websocket.send_json({
                        "type": "partial",
                        "text": "Partial transcription...",
                        "is_final": False
                    })
                    
                    # Keep last second for overlap
                    keep_bytes = 16000 * 2 * 1  # 1 second
                    audio_buffer = audio_buffer[-keep_bytes:]
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "code": "INTERNAL_ERROR",
            "message": str(e)
        })
        await websocket.close(code=1011)


@router.get("/ws-test")
async def websocket_test_page():
    """Simple WebSocket test page."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
    </head>
    <body>
        <h1>ASR WebSocket Test</h1>
        <div>
            <input type="text" id="apiKey" placeholder="API Key" />
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
        </div>
        <div>
            <button onclick="startRecording()">Start Recording</button>
            <button onclick="stopRecording()">Stop Recording</button>
        </div>
        <div id="status">Disconnected</div>
        <div id="transcript"></div>
        
        <script>
            let ws = null;
            let mediaRecorder = null;
            
            function connect() {
                const apiKey = document.getElementById('apiKey').value;
                ws = new WebSocket(`wss://${window.location.host}/ws/transcribe?api_key=${apiKey}&model=base`);
                
                ws.onopen = () => {
                    document.getElementById('status').textContent = 'Connected';
                };
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);
                    if (data.type === 'partial' || data.type === 'final') {
                        document.getElementById('transcript').textContent += data.text + ' ';
                    }
                };
                
                ws.onclose = () => {
                    document.getElementById('status').textContent = 'Disconnected';
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                }
            }
            
            async function startRecording() {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                        event.data.arrayBuffer().then(buffer => {
                            ws.send(buffer);
                        });
                    }
                };
                
                mediaRecorder.start(500); // Send chunks every 500ms
            }
            
            function stopRecording() {
                if (mediaRecorder) {
                    mediaRecorder.stop();
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
