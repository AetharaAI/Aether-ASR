"""TTS proxy endpoints — proxies to upstream Chatterbox TTS server."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import structlog
from fastapi.responses import StreamingResponse

from app.config import settings

logger = structlog.get_logger()
router = APIRouter()


class TTSSpeechRequest(BaseModel):
    """Request body for TTS speech generation."""
    text: str
    voice_mode: str = "predefined"
    predefined_voice_id: Optional[str] = None
    reference_audio_filename: Optional[str] = None
    output_format: str = "wav"
    temperature: Optional[float] = None
    exaggeration: Optional[float] = None
    speed_factor: Optional[float] = None
    seed: Optional[int] = None


async def _tts_get(path: str) -> dict:
    """Helper: GET from TTS upstream."""
    url = f"{settings.TTS_BASE_URL.rstrip('/')}{path}"
    headers = {}
    if settings.TTS_API_KEY:
        headers["Authorization"] = f"Bearer {settings.TTS_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        logger.error("tts_upstream_unreachable", url=url)
        raise HTTPException(status_code=503, detail="TTS upstream is unreachable.")
    except httpx.HTTPStatusError as e:
        logger.error("tts_upstream_error", status=e.response.status_code, url=url)
        raise HTTPException(status_code=e.response.status_code, detail=f"TTS upstream error: {e.response.text}")
    except Exception as e:
        logger.error("tts_proxy_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"TTS proxy error: {str(e)}")


@router.get("/tts/health")
async def tts_health():
    """Check connectivity to the TTS upstream."""
    try:
        data = await _tts_get("/api/model-info")
        return {"status": "healthy", "upstream": settings.TTS_BASE_URL, "model_info": data}
    except HTTPException as e:
        return {"status": "degraded", "upstream": settings.TTS_BASE_URL, "error": e.detail}


@router.get("/tts/model-info")
async def tts_model_info():
    """Proxy: Get TTS model information."""
    return await _tts_get("/api/model-info")


@router.get("/tts/voices")
async def tts_voices():
    """Proxy: Get available predefined voices from TTS upstream."""
    return await _tts_get("/get_predefined_voices")


@router.post("/tts/speech")
async def tts_speech(req: TTSSpeechRequest):
    """Proxy: Generate speech via TTS upstream. Returns audio stream."""
    url = f"{settings.TTS_BASE_URL.rstrip('/')}/tts"
    headers = {"Content-Type": "application/json"}
    if settings.TTS_API_KEY:
        headers["Authorization"] = f"Bearer {settings.TTS_API_KEY}"

    payload = req.model_dump(exclude_none=True)

    try:
        async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "audio/wav")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="tts_output.{req.output_format}"'
                }
            )
    except httpx.ConnectError:
        logger.error("tts_upstream_unreachable_speech", url=url)
        raise HTTPException(status_code=503, detail="TTS upstream is unreachable.")
    except httpx.HTTPStatusError as e:
        logger.error("tts_speech_error", status=e.response.status_code)
        raise HTTPException(status_code=e.response.status_code, detail=f"TTS generation failed: {e.response.text}")
    except Exception as e:
        logger.error("tts_speech_proxy_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"TTS proxy error: {str(e)}")
