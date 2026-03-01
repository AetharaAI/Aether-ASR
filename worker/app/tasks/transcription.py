"""Transcription Celery tasks."""
import os
import tempfile
import json
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
import structlog

from app.celery_app import app
from app.pipeline.asr import ASRPipeline
from app.services.database import update_job_status, record_usage, get_job
from app.services.storage import download_file, upload_artifact
from app.services.cache import publish_job_event
from app.utils.gpu_manager import GPUPool


logger = structlog.get_logger()


# Error codes that are retryable
RETRYABLE_ERRORS = [
    "GPU_OOM_ERROR",
    "TRANSCRIPTION_ERROR",
    "STORAGE_ERROR",
    "TIMEOUT_ERROR"
]


def is_retryable_error(error_code: str) -> bool:
    """Check if error is retryable."""
    return error_code in RETRYABLE_ERRORS


@app.task(
    bind=True,
    queue="transcription",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=3600,  # 1 hour
    time_limit=7200,  # 2 hours
)
def transcribe_audio(self, job_id: str, storage_key: str, config: dict):
    """
    Main transcription task.
    
    This task downloads the audio file, runs the full transcription pipeline,
    and uploads the results.
    """
    logger.info("starting_transcription", job_id=job_id, model=config.get("model"))
    
    # Check if job already completed (idempotency)
    job = get_job(job_id)
    if job and job.status.value == "completed":
        logger.info("job_already_completed", job_id=job_id)
        return job.result
    
    if job and job.status.value == "cancelled":
        logger.info("job_cancelled", job_id=job_id)
        return None
    
    temp_dir = None
    
    try:
        # Update status to processing
        update_job_status(
            job_id=job_id,
            status="processing",
            progress={"step": "downloading", "percent": 5}
        )
        publish_job_event(job_id, "started", {"step": "downloading"})
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix=f"asr_{job_id}_")
        audio_path = os.path.join(temp_dir, "audio.wav")
        
        # Download audio file
        logger.info("downloading_audio", job_id=job_id, storage_key=storage_key)
        audio_bytes = download_file(storage_key)
        
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        
        # Get audio info
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        duration_seconds = len(audio) / 1000.0
        
        # Update progress
        update_job_status(
            job_id=job_id,
            status="processing",
            progress={"step": "processing", "percent": 10}
        )
        
        # Run transcription pipeline
        logger.info("running_pipeline", job_id=job_id, model=config.get("model"))
        
        pipeline = ASRPipeline(config)
        
        def progress_callback(step: str, percent: int, **kwargs):
            """Report progress."""
            progress = {
                "step": step,
                "percent": percent,
                **kwargs
            }
            update_job_status(job_id, "processing", progress=progress)
            publish_job_event(job_id, "progress", progress)
        
        result = pipeline.process(
            audio_path=audio_path,
            progress_callback=progress_callback
        )
        
        # Upload artifacts
        logger.info("uploading_artifacts", job_id=job_id)
        progress_callback("uploading", 95)
        
        # Upload JSON
        json_data = json.dumps(result, indent=2).encode("utf-8")
        json_key = upload_artifact(json_data, job_id, "transcript", "json")
        
        # Upload SRT
        srt_data = _to_srt(result).encode("utf-8")
        srt_key = upload_artifact(srt_data, job_id, "transcript", "srt")
        
        # Upload VTT
        vtt_data = _to_vtt(result).encode("utf-8")
        vtt_key = upload_artifact(vtt_data, job_id, "transcript", "vtt")
        
        # Upload TXT
        txt_data = result.get("text", "").encode("utf-8")
        txt_key = upload_artifact(txt_data, job_id, "transcript", "txt")
        
        # Update job status
        logger.info("transcription_complete", job_id=job_id)
        
        update_job_status(
            job_id=job_id,
            status="completed",
            progress={"step": "completed", "percent": 100},
            result=result
        )
        
        publish_job_event(job_id, "completed", {"result": result})
        
        # Record usage
        record_usage(
            tenant_id=job.tenant_id,
            api_key_id=job.api_key_id,
            job_id=job_id,
            audio_seconds=duration_seconds,
            audio_bytes=len(audio_bytes),
            model=config.get("model", "base"),
            features={
                "vad": config.get("vad_enabled", True),
                "diarization": config.get("diarization_enabled", False),
                "word_timestamps": config.get("word_timestamps", False)
            }
        )
        
        return result
        
    except SoftTimeLimitExceeded:
        logger.error("transcription_timeout", job_id=job_id)
        update_job_status(
            job_id=job_id,
            status="failed",
            error={
                "code": "TIMEOUT_ERROR",
                "message": "Transcription timed out",
                "retryable": True
            }
        )
        raise
        
    except Exception as e:
        logger.error("transcription_failed", job_id=job_id, error=str(e))
        
        error_code = _classify_error(e)
        retryable = is_retryable_error(error_code)
        
        # Check if we should retry
        if retryable and self.request.retries < self.max_retries:
            logger.info("retrying_transcription", job_id=job_id, attempt=self.request.retries + 1)
            update_job_status(
                job_id=job_id,
                status="processing",
                progress={
                    "step": "retrying",
                    "attempt": self.request.retries + 1,
                    "error": str(e)
                }
            )
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        # Final failure
        update_job_status(
            job_id=job_id,
            status="failed",
            error={
                "code": error_code,
                "message": str(e),
                "retryable": False
            }
        )
        
        publish_job_event(job_id, "failed", {"error": str(e), "code": error_code})
        
        raise
        
    finally:
        # Cleanup temp directory
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def _classify_error(error: Exception) -> str:
    """Classify error type."""
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    if "cuda" in error_str or "out of memory" in error_str:
        return "GPU_OOM_ERROR"
    elif "decode" in error_str or "format" in error_str:
        return "AUDIO_DECODE_ERROR"
    elif "storage" in error_str or "s3" in error_str or "minio" in error_str:
        return "STORAGE_ERROR"
    elif "timeout" in error_str:
        return "TIMEOUT_ERROR"
    elif "transcrib" in error_str:
        return "TRANSCRIPTION_ERROR"
    else:
        return "UNKNOWN_ERROR"


def _to_srt(result: dict) -> str:
    """Convert result to SRT format."""
    lines = []
    segments = result.get("segments", [])
    
    for i, segment in enumerate(segments):
        start = _format_timestamp_srt(segment.get("start", 0))
        end = _format_timestamp_srt(segment.get("end", 0))
        text = segment.get("text", "").strip()
        speaker = segment.get("speaker")
        
        if speaker:
            text = f"[{speaker}] {text}"
        
        lines.append(f"{i + 1}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    
    return "\n".join(lines)


def _to_vtt(result: dict) -> str:
    """Convert result to VTT format."""
    lines = ["WEBVTT", ""]
    segments = result.get("segments", [])
    
    for segment in segments:
        start = _format_timestamp_vtt(segment.get("start", 0))
        end = _format_timestamp_vtt(segment.get("end", 0))
        text = segment.get("text", "").strip()
        speaker = segment.get("speaker")
        
        if speaker:
            lines.append(f'{start} --> {end}')
            lines.append(f"<v {speaker}>{text}</v>")
        else:
            lines.append(f'{start} --> {end}')
            lines.append(text)
        
        lines.append("")
    
    return "\n".join(lines)


def _format_timestamp_srt(seconds: float) -> str:
    """Format seconds to SRT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    """Format seconds to VTT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
