"""OpenAI-compatible endpoints."""
from fastapi import APIRouter, File, UploadFile, Form
from typing import Optional, Literal

from app.services.storage import upload_file
from app.services.queue import enqueue_job
from app.services.database import create_job
from app.utils.id_generator import generate_job_id
from app.utils.validators import validate_audio_file



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
):
    """
    OpenAI-compatible transcription endpoint.
    
    Always creates an async job processed by the Celery worker.
    """
    # Map model name
    whisper_model = MODEL_MAPPING.get(model, "base")
    
    # Validate file
    file_bytes = await file.read()
    validation = await validate_audio_file(file_bytes, file.filename)
    
    # Always use async processing via Celery worker
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
        tenant_id="open",
        api_key_id=None,
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
    
    # Return job info for polling
    return {
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
):
    """OpenAI-compatible translation endpoint (translates to English)."""
    file_bytes = await file.read()
    validation = await validate_audio_file(file_bytes, file.filename)
    
    whisper_model = MODEL_MAPPING.get(model, "large-v3")
    
    job_id = generate_job_id()
    
    storage_key = await upload_file(
        file_bytes=file_bytes,
        filename=file.filename,
        job_id=job_id
    )
    
    config = {
        "model": whisper_model,
        "language": "en",  # Force English for translation
        "task": "translate",
        "temperature": temperature,
        "vad_enabled": True,
        "word_timestamps": False,
        "output_format": "json" if response_format == "verbose_json" else response_format
    }
    
    await create_job(
        job_id=job_id,
        tenant_id="open",
        api_key_id=None,
        config=config,
        file_info={
            "original_name": file.filename,
            "storage_key": storage_key,
            "size_bytes": len(file_bytes),
            "duration_seconds": validation.duration_seconds,
            "format": validation.format
        }
    )
    
    await enqueue_job(job_id, storage_key, config)
    
    return {
        "job_id": job_id,
        "status": "pending"
    }

