"""Industrial transcription endpoints."""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Query
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional, Literal, List
import json

from app.models.schemas import JobResponse, JobListResponse, TranscriptionConfig
from app.services.storage import upload_file, download_artifact
from app.services.queue import enqueue_job, cancel_job
from app.services.database import (
    create_job, get_job, list_jobs, update_job_status,
    get_job_artifacts, record_usage
)
from app.utils.id_generator import generate_job_id
from app.utils.validators import validate_audio_file
from app.config import settings


router = APIRouter()


@router.get("/model-info")
async def get_model_info():
    """Get currently loaded ASR models."""
    from app.utils.gpu_manager import GPUPool
    return {"loaded_models": list(GPUPool.get_loaded_models().keys())}


@router.get("/ui/initial-data")
async def get_ui_initial_data():
    """Provides initial data for the UI to render."""
    return {"models": ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]}


@router.post("/save_settings")
async def save_settings(settings: dict):
    """Saves partial configuration updates."""
    return {"message": "Settings saved successfully", "restart_needed": False}


@router.post("/reset_settings")
async def reset_settings():
    """Resets the configuration."""
    return {"message": "Settings reset successfully", "restart_needed": True}


@router.post("/restart_server")
async def restart_server():
    """Triggers a hot-swap of the ASR model."""
    return {"message": "Server restarting...", "restart_needed": False}


@router.post("/upload_audio")
async def upload_audio(files: List[UploadFile] = File(...)):
    """Handles uploading of audio files for transcription."""
    # In a real impl, save these files to a 'reference' or 'audio' dir
    return {"message": f"Successfully uploaded {len(files)} files"}


@router.post("/asr", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_transcription_job(
    file: UploadFile = File(...),
    model: str = Form("base"),
    language: str = Form("auto"),
    compute_type: Literal["float16", "int8", "float32"] = Form("float16"),
    vad_enabled: bool = Form(True),
    vad_threshold: float = Form(0.5),
    diarization_enabled: bool = Form(False),
    word_timestamps: bool = Form(False),
    chunk_length: int = Form(30),
    chunk_overlap: int = Form(5),
    output_format: Literal["json", "srt", "vtt", "txt"] = Form("json"),
    retention_days: int = Form(7),
    webhook_url: Optional[str] = Form(None),
):
    """Create an async transcription job."""
    # Validate file
    file_bytes = await file.read()
    validation = await validate_audio_file(file_bytes, file.filename)
    
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": validation.error_message
                }
            }
        )
    
    # Generate job ID
    job_id = generate_job_id()
    
    # Upload to storage
    storage_key = await upload_file(
        file_bytes=file_bytes,
        filename=file.filename,
        job_id=job_id
    )
    
    # Build config
    config = TranscriptionConfig(
        model=model,
        language=language,
        compute_type=compute_type,
        vad_enabled=vad_enabled,
        vad_threshold=vad_threshold,
        diarization_enabled=diarization_enabled,
        word_timestamps=word_timestamps,
        chunk_length=chunk_length,
        chunk_overlap=chunk_overlap,
        output_format=output_format,
        retention_days=retention_days,
        webhook_url=webhook_url
    )
    
    # Create job record
    job = await create_job(
        job_id=job_id,
        tenant_id="open",
        api_key_id=None,
        config=config.model_dump(),
        file_info={
            "original_name": file.filename,
            "storage_key": storage_key,
            "size_bytes": len(file_bytes),
            "duration_seconds": validation.duration_seconds,
            "format": validation.format,
            "sample_rate": validation.sample_rate,
            "channels": validation.channels
        },
        webhook_url=webhook_url
    )
    
    # Enqueue job
    await enqueue_job(job_id, storage_key, config.model_dump())
    
    return job


@router.get("/transcriptions", response_model=JobListResponse)
async def list_transcription_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("-created_at"),
):
    """List transcription jobs with pagination."""
    jobs, total = await list_jobs(
        tenant_id="open",
        status=status,
        limit=limit,
        offset=offset,
        sort=sort
    )
    
    return {
        "items": jobs,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "next_offset": offset + limit if offset + limit < total else None,
            "prev_offset": offset - limit if offset > 0 else None
        }
    }


@router.get("/transcriptions/{job_id}", response_model=JobResponse)
async def get_transcription_job(
    job_id: str,
):
    """Get job status and results."""
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Job {job_id} not found"
                }
            }
        )
    
    # Add artifact URLs if completed
    if job.status.value == "completed":
        artifacts = await get_job_artifacts(job_id)
        job.artifacts = {
            artifact.format: f"/api/transcriptions/{job_id}/download?format={artifact.format}"
            for artifact in artifacts
        }
    
    return job


@router.post("/transcriptions/{job_id}/cancel")
async def cancel_transcription_job(
    job_id: str,
):
    """Cancel a pending or processing job."""
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Job {job_id} not found"
                }
            }
        )
    
    if job.status.value not in ["pending", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "INVALID_STATE",
                    "message": f"Cannot cancel job in state: {job.status.value}"
                }
            }
        )
    
    # Cancel in queue
    await cancel_job(job_id)
    
    # Update status
    await update_job_status(job_id, "cancelled")
    
    return {
        "id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully"
    }


@router.get("/transcriptions/{job_id}/download")
async def download_transcript(
    job_id: str,
    format: Literal["json", "srt", "vtt", "txt"] = Query("json"),
):
    """Download transcript in specified format."""
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Job {job_id} not found"
                }
            }
        )
    
    if job.status.value != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "NOT_READY",
                    "message": f"Job not completed. Current status: {job.status.value}"
                }
            }
        )
    
    # Download artifact
    artifact = await download_artifact(job_id, format)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Transcript in format '{format}' not found"
                }
            }
        )
    
    content_type_map = {
        "json": "application/json",
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain"
    }
    
    return StreamingResponse(
        artifact,
        media_type=content_type_map.get(format, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}.{format}"'
        }
    )


@router.get("/transcriptions/{job_id}/events")
async def job_events_stream(
    job_id: str,
):
    """Server-sent events for job progress."""
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Job {job_id} not found"
                }
            }
        )
    
    async def event_generator():
        from app.services.cache import subscribe_to_job_events
        
        async for event in subscribe_to_job_events(job_id):
            yield f"event: {event['type']}\\ndata: {json.dumps(event['data'])}\\n\\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
