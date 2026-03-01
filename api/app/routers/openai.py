"""OpenAI-compatible endpoints."""
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from typing import Optional, Literal
import tempfile
import os

from app.models.schemas import (
    OpenAITranscriptionResponse, 
    OpenAIVerboseTranscriptionResponse
)
from app.services.auth import verify_api_key
from app.services.storage import upload_file
from app.services.queue import enqueue_job
from app.services.database import create_job, get_job
from app.utils.id_generator import generate_job_id
from app.utils.validators import validate_audio_file
from app.config import settings


router = APIRouter()

# Model mapping from OpenAI to faster-whisper
MODEL_MAPPING = {
    "whisper-1": "base",
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v3": "large-v3",
    "large": "large-v3"
}


@router.post("/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Form("json"),
    temperature: float = Form(0.0),
    timestamp_granularities: Optional[str] = Form(None),
    api_key: str = Depends(verify_api_key)
):
    """
    OpenAI-compatible transcription endpoint.
    
    For small files (< 30s), processes synchronously.
    For larger files, creates an async job and returns immediately.
    """
    # Map model name
    whisper_model = MODEL_MAPPING.get(model, "base")
    
    # Validate file
    file_bytes = await file.read()
    validation = await validate_audio_file(file_bytes, file.filename)
    
    # Check if we should process sync or async
    if validation.duration_seconds and validation.duration_seconds <= settings.SYNC_MAX_DURATION_SECONDS:
        # Synchronous processing
        return await _process_sync(
            file_bytes=file_bytes,
            filename=file.filename,
            model=whisper_model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            timestamp_granularities=timestamp_granularities
        )
    else:
        # Async processing - create job
        job_id = generate_job_id()
        
        # Upload to storage
        storage_key = await upload_file(
            file_bytes=file_bytes,
            filename=file.filename,
            job_id=job_id
        )
        
        # Create job record
        config = {
            "model": whisper_model,
            "language": language or "auto",
            "temperature": temperature,
            "vad_enabled": True,
            "word_timestamps": timestamp_granularities and "word" in timestamp_granularities,
            "output_format": "json" if response_format == "verbose_json" else response_format
        }
        
        await create_job(
            job_id=job_id,
            tenant_id=api_key.tenant_id,
            api_key_id=api_key.id,
            config=config,
            file_info={
                "original_name": file.filename,
                "storage_key": storage_key,
                "size_bytes": len(file_bytes),
                "duration_seconds": validation.duration_seconds,
                "format": validation.format
            }
        )
        
        # Enqueue job
        await enqueue_job(job_id, storage_key, config)
        
        # Return job info (OpenAI doesn't have async, so we return a message)
        return {
            "text": f"Job created: {job_id}. Check status at /api/transcriptions/{job_id}",
            "job_id": job_id,
            "status": "pending"
        }


@router.post("/audio/translations")
async def create_translation(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    prompt: Optional[str] = Form(None),
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Form("json"),
    temperature: float = Form(0.0),
    api_key: str = Depends(verify_api_key)
):
    """OpenAI-compatible translation endpoint (translates to English)."""
    # Similar to transcription but forces language to English
    file_bytes = await file.read()
    
    whisper_model = MODEL_MAPPING.get(model, "large-v3")
    
    return await _process_sync(
        file_bytes=file_bytes,
        filename=file.filename,
        model=whisper_model,
        language="en",  # Force English
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
        timestamp_granularities=None
    )


async def _process_sync(
    file_bytes: bytes,
    filename: str,
    model: str,
    language: Optional[str],
    prompt: Optional[str],
    response_format: str,
    temperature: float,
    timestamp_granularities: Optional[str]
):
    """Process transcription synchronously."""
    import asyncio
    
    # For sync processing, we'd ideally have a local whisper instance
    # For this skeleton, we'll return a placeholder
    # In production, this would call the worker pipeline directly
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        # This would be replaced with actual transcription
        # For now, return a mock response
        result = {
            "text": "This is a placeholder transcription result.",
            "language": language or "en",
            "duration": 10.0
        }
        
        if response_format == "text":
            return PlainTextResponse(content=result["text"])
        
        elif response_format == "json":
            return {"text": result["text"]}
        
        elif response_format == "verbose_json":
            return {
                "task": "transcribe",
                "language": result["language"],
                "duration": result["duration"],
                "text": result["text"],
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": result["duration"],
                        "text": result["text"]
                    }
                ]
            }
        
        elif response_format == "srt":
            srt_content = f"1\\n00:00:00,000 --> 00:00:{int(result['duration']):02d},000\\n{result['text']}\\n"
            return PlainTextResponse(content=srt_content, media_type="application/x-subrip")
        
        elif response_format == "vtt":
            vtt_content = f"WEBVTT\\n\\n00:00:00.000 --> 00:00:{int(result['duration']):02d}.000\\n{result['text']}\\n"
            return PlainTextResponse(content=vtt_content, media_type="text/vtt")
        
        else:
            return {"text": result["text"]}
    
    finally:
        os.unlink(tmp_path)
