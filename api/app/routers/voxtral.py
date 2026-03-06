"""Voxtral Realtime ASR proxy — routes requests to the vLLM sidecar.

Voxtral uses vLLM's /v1/realtime WebSocket API, not the HTTP transcription API.
This router handles:
  - File upload transcription (converts to PCM16, streams via WebSocket)
  - Health check
  - Model listing
  - WebSocket proxy for client-side streaming
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, WebSocket
from typing import Optional
import httpx
import asyncio
import json
import base64
import io
import struct
import numpy as np

from app.config import settings


router = APIRouter()

VLLM_MODEL = "mistralai/Voxtral-Mini-4B-Realtime-2602"
TARGET_SR = 16000
CHUNK_DURATION_MS = 480


@router.get("/voxtral/health")
async def voxtral_health():
    """Check Voxtral vLLM service health."""
    if not settings.VOXTRAL_ENABLED:
        return {"status": "disabled"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.VOXTRAL_BASE_URL}/health")
            if resp.status_code == 200:
                return {"status": "healthy", "engine": "voxtral-realtime-4b", "backend": "vllm"}
            return {"status": "degraded", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}


@router.get("/voxtral/models")
async def voxtral_models():
    """List models available on the Voxtral vLLM instance."""
    if not settings.VOXTRAL_ENABLED:
        raise HTTPException(status_code=503, detail="Voxtral engine is disabled")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.VOXTRAL_BASE_URL}/v1/models")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Voxtral vLLM unreachable: {e}")


def _audio_bytes_to_pcm16(file_bytes: bytes, filename: str) -> bytes:
    """Convert uploaded audio file to 16kHz PCM16 bytes using pydub."""
    from pydub import AudioSegment
    
    # Detect format from extension
    ext = (filename or "audio.wav").rsplit(".", 1)[-1].lower()
    format_map = {"wav": "wav", "mp3": "mp3", "m4a": "m4a", "webm": "webm", 
                  "ogg": "ogg", "flac": "flac", "opus": "ogg"}
    fmt = format_map.get(ext, "wav")
    
    audio = AudioSegment.from_file(io.BytesIO(file_bytes), format=fmt)
    
    # Convert to mono, 16kHz, 16-bit PCM
    audio = audio.set_channels(1).set_frame_rate(TARGET_SR).set_sample_width(2)
    
    return audio.raw_data


@router.post("/voxtral/transcribe")
async def voxtral_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    temperature: float = Form(0.0),
):
    """
    Transcribe audio via Voxtral Realtime (vLLM WebSocket).
    
    Accepts an uploaded audio file, converts it to PCM16 16kHz, 
    then streams it through vLLM's /v1/realtime WebSocket to get
    the transcript back.
    """
    if not settings.VOXTRAL_ENABLED:
        raise HTTPException(status_code=503, detail="Voxtral engine is disabled")
    
    file_bytes = await file.read()
    
    # Convert to PCM16 16kHz
    try:
        pcm_bytes = _audio_bytes_to_pcm16(file_bytes, file.filename or "audio.wav")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {e}")
    
    # Stream via WebSocket to vLLM
    import aiohttp
    
    vllm_ws_url = settings.VOXTRAL_BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{vllm_ws_url}/v1/realtime"
    
    chunk_samples = int(TARGET_SR * CHUNK_DURATION_MS / 1000)
    chunk_bytes_size = chunk_samples * 2  # 16-bit = 2 bytes per sample
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url, timeout=aiohttp.ClientTimeout(total=60)) as ws:
                # Wait for session.created from server
                init_msg = await ws.receive_json()
                if init_msg.get("type") != "session.created":
                    raise HTTPException(status_code=502, detail=f"Expected session.created, got: {init_msg.get('type')}")
                
                # Send session config (flat format per current vLLM docs)
                await ws.send_json({
                    "type": "session.update",
                    "model": VLLM_MODEL,
                })
                
                # Stream audio in chunks
                offset = 0
                while offset < len(pcm_bytes):
                    chunk = pcm_bytes[offset:offset + chunk_bytes_size]
                    await ws.send_json({
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(chunk).decode("ascii"),
                    })
                    offset += chunk_bytes_size
                    await asyncio.sleep(0.01)
                
                # Signal end of input (final=True for file uploads)
                await ws.send_json({
                    "type": "input_audio_buffer.commit",
                    "final": True,
                })
                
                # Collect response
                full_text = ""
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        event = json.loads(msg.data)
                        event_type = event.get("type", "")
                        
                        if event_type == "transcription.delta":
                            delta = event.get("delta", "")
                            full_text += delta
                        
                        elif event_type == "transcription.done":
                            transcript = event.get("text", full_text)
                            return {"text": transcript.strip()}
                        
                        elif event_type == "error":
                            error_msg = event.get("error", {}).get("message", str(event))
                            raise HTTPException(status_code=500, detail=f"Voxtral error: {error_msg}")
                    
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break
                
                # If we exited loop without transcription.done
                if full_text.strip():
                    return {"text": full_text.strip()}
                
                return {"text": ""}
    
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=502, detail=f"Cannot connect to Voxtral vLLM: {e}")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Voxtral transcription timed out")


@router.websocket("/voxtral/realtime")
async def voxtral_realtime(websocket: WebSocket):
    """
    WebSocket proxy to vLLM's /v1/realtime endpoint for streaming ASR.
    
    Clients connect here and stream audio frames; transcription results
    are streamed back in real time.
    """
    await websocket.accept()
    
    if not settings.VOXTRAL_ENABLED:
        await websocket.close(code=1013, reason="Voxtral engine is disabled")
        return
    
    import aiohttp
    
    vllm_ws_url = settings.VOXTRAL_BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{vllm_ws_url}/v1/realtime"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as vllm_ws:
                async def forward_to_vllm():
                    """Forward client messages to vLLM."""
                    try:
                        while True:
                            data = await websocket.receive_text()
                            await vllm_ws.send_str(data)
                    except Exception:
                        pass
                
                async def forward_to_client():
                    """Forward vLLM responses to client."""
                    try:
                        async for msg in vllm_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await websocket.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await websocket.send_bytes(msg.data)
                    except Exception:
                        pass
                
                await asyncio.gather(forward_to_vllm(), forward_to_client())
    
    except Exception as e:
        await websocket.close(code=1011, reason=f"vLLM connection failed: {str(e)[:100]}")
