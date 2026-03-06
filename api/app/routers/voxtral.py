"""Voxtral Realtime ASR proxy — routes requests to the vLLM sidecar."""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, WebSocket
from typing import Optional
import httpx
import base64
import asyncio
import json

from app.config import settings


router = APIRouter()


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


@router.post("/voxtral/transcribe")
async def voxtral_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    temperature: float = Form(0.0),
):
    """
    Transcribe audio via Voxtral Realtime (vLLM).
    
    Reads the uploaded audio file and sends it to the vLLM OpenAI-compatible
    transcription endpoint.
    """
    if not settings.VOXTRAL_ENABLED:
        raise HTTPException(status_code=503, detail="Voxtral engine is disabled")
    
    file_bytes = await file.read()
    
    try:
        # vLLM's OpenAI-compatible audio transcription endpoint
        async with httpx.AsyncClient(timeout=settings.VOXTRAL_TIMEOUT_SECONDS) as client:
            files_payload = {
                "file": (file.filename or "audio.wav", file_bytes, file.content_type or "audio/wav"),
            }
            data_payload = {
                "model": "mistralai/Voxtral-Mini-4B-Realtime-2602",
                "temperature": str(temperature),
            }
            if language:
                data_payload["language"] = language
            
            resp = await client.post(
                f"{settings.VOXTRAL_BASE_URL}/v1/audio/transcriptions",
                files=files_payload,
                data=data_payload,
            )
            
            if resp.status_code != 200:
                error_detail = resp.text
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Voxtral transcription failed: {error_detail}"
                )
            
            return resp.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Voxtral transcription timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot connect to Voxtral vLLM service")


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
    
    import websockets
    
    vllm_ws_url = settings.VOXTRAL_BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    vllm_ws_url = f"{vllm_ws_url}/v1/realtime"
    
    try:
        async with websockets.connect(vllm_ws_url) as vllm_ws:
            async def forward_to_vllm():
                """Forward client messages to vLLM."""
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await vllm_ws.send(data)
                except Exception:
                    pass
            
            async def forward_to_client():
                """Forward vLLM responses to client."""
                try:
                    async for message in vllm_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception:
                    pass
            
            # Run both directions concurrently
            await asyncio.gather(forward_to_vllm(), forward_to_client())
    
    except Exception as e:
        await websocket.close(code=1011, reason=f"vLLM connection failed: {str(e)[:100]}")
