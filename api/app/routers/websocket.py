"""WebSocket streaming endpoint.

The /ws/transcribe endpoint now properly handles audio streaming:
- While recording: buffer audio chunks
- On 'end' message: write buffer to a temp file, submit a real Celery
  transcription job, and return the job_id so the client can poll via SSE.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
import base64
import json
import asyncio
import tempfile
import os

from app.models.schemas import WebSocketMessage


router = APIRouter()


@router.websocket("/ws/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    model: str = Query("base"),
    language: str = Query("auto")
):
    """WebSocket endpoint for real-time streaming transcription.

    Protocol:
    - Client sends binary frames: raw audio bytes (PCM or webm chunks).
    - Client sends JSON { "type": "config", "config": {...} } to update config.
    - Client sends JSON { "type": "end" } when done recording.
    - Server responds with { "type": "job_submitted", "job_id": "..." } so
      the client can open SSE /api/transcriptions/{job_id}/events to poll.
    - Client sends JSON { "type": "ping" } → server replies { "type": "pong" }.
    """
    await websocket.accept()

    config = {
        "model": model,
        "language": language,
        "vad_enabled": True,
        "word_timestamps": False,
        "output_format": "json",
        "retention_days": 7,
    }

    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "config":
                    config.update(data.get("config", {}))
                    await websocket.send_json({
                        "type": "config_ack",
                        "config": config
                    })

                elif msg_type == "end":
                    if not audio_buffer:
                        await websocket.send_json({
                            "type": "error",
                            "code": "NO_AUDIO",
                            "message": "No audio data received"
                        })
                        await websocket.close(code=1000)
                        return

                    # Submit a real transcription job
                    try:
                        from app.utils.id_generator import generate_job_id
                        from app.services.storage import upload_file
                        from app.services.queue import enqueue_job
                        from app.services.database import create_job

                        job_id = generate_job_id()

                        # Upload the buffered audio
                        audio_bytes = bytes(audio_buffer)
                        storage_key = await upload_file(
                            file_bytes=audio_bytes,
                            filename=f"recording-{job_id}.webm",
                            job_id=job_id
                        )

                        # Create the DB record
                        await create_job(
                            job_id=job_id,
                            tenant_id="open",
                            api_key_id=None,
                            config=config,
                            file_info={
                                "original_name": f"recording-{job_id}.webm",
                                "storage_key": storage_key,
                                "size_bytes": len(audio_bytes),
                                "duration_seconds": None,
                                "format": "webm",
                            }
                        )

                        # Enqueue Celery task
                        await enqueue_job(job_id, storage_key, config)

                        await websocket.send_json({
                            "type": "job_submitted",
                            "job_id": job_id,
                            "message": "Recording submitted for transcription"
                        })

                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "SUBMISSION_FAILED",
                            "message": str(e)
                        })

                    await websocket.close(code=1000)
                    return

                elif msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    })

            elif "bytes" in message:
                # Accumulate audio data
                audio_buffer.extend(message["bytes"])

                # Acknowledge receipt with buffer size (helps UI show progress)
                # Only send every ~50KB to avoid flooding
                if len(audio_buffer) % (50 * 1024) < 4096:
                    await websocket.send_json({
                        "type": "buffering",
                        "bytes_received": len(audio_buffer)
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e)
            })
            await websocket.close(code=1011)
        except Exception:
            pass


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
                ws = new WebSocket(`wss://${window.location.host}/ws/transcribe?model=base`);

                ws.onopen = () => {
                    document.getElementById('status').textContent = 'Connected';
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);
                    if (data.type === 'partial' || data.type === 'final') {
                        document.getElementById('transcript').textContent += data.text + ' ';
                    } else if (data.type === 'job_submitted') {
                        document.getElementById('status').textContent = `Job submitted: ${data.job_id}`;
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
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ type: 'end' }));
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
