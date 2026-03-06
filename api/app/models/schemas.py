"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    parameters: str
    languages: List[str]
    capabilities: Dict[str, bool]
    resources: Dict[str, Any]


class ModelsResponse(BaseModel):
    models: List[ModelInfo]


class TranscriptionConfig(BaseModel):
    model: str = Field(default="base", description="Whisper model to use")
    language: str = Field(default="auto", description="Language code or 'auto' for detection")
    compute_type: Literal["float16", "int8", "float32"] = Field(default="float16")
    vad_enabled: bool = Field(default=True)
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    diarization_enabled: bool = Field(default=False)
    word_timestamps: bool = Field(default=False)
    chunk_length: int = Field(default=30, ge=10, le=60)
    chunk_overlap: int = Field(default=5, ge=0, le=10)
    output_format: Literal["json", "srt", "vtt", "txt"] = Field(default="json")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    beam_size: int = Field(default=5, ge=1, le=10)
    retention_days: int = Field(default=7, ge=0)
    webhook_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class FileInfo(BaseModel):
    original_name: Optional[str] = None
    storage_key: Optional[str] = None
    size_bytes: int = 0
    duration_seconds: Optional[float] = None
    format: Optional[str] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ProgressInfo(BaseModel):
    percent: int = 0
    current_step: str = "queued"
    steps_total: int = 5
    chunks_processed: int = 0
    chunks_total: int = 0
    message: str = "Waiting in queue"

    model_config = ConfigDict(from_attributes=True)


class UsageInfo(BaseModel):
    audio_seconds: float
    audio_bytes: int
    model: str
    compute_type: str

    model_config = ConfigDict(from_attributes=True)


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    confidence: Optional[float] = None


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None
    no_speech_prob: Optional[float] = None
    words: Optional[List[WordTimestamp]] = None


class TranscriptionResult(BaseModel):
    language: str
    language_probability: Optional[float] = None
    duration: float
    text: str
    segments: List[TranscriptSegment]
    speakers: Optional[List[str]] = None


class ErrorInfo(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class JobResponse(BaseModel):
    """
    ORM-backed response for a transcription job.

    Field names match the SQLAlchemy Job column names exactly so that
    Pydantic can read them directly via from_attributes=True:
      - file_info  (was: file)  matches  Job.file_info
      - config                  matches  Job.config
      - progress               matches  Job.progress
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    # Renamed from `file` → `file_info` to match the ORM column
    file_info: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None
    artifacts: Optional[Dict[str, str]] = None


class JobListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[JobResponse]
    pagination: Dict[str, Any]


class OpenAITranscriptionRequest(BaseModel):
    model: str = Field(default="whisper-1")
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Field(default="json")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp_granularities: Optional[List[Literal["word", "segment"]]] = None


class OpenAITranscriptionResponse(BaseModel):
    text: str


class OpenAIVerboseTranscriptionResponse(BaseModel):
    task: str
    language: str
    duration: float
    text: str
    words: Optional[List[Dict[str, Any]]] = None
    segments: List[Dict[str, Any]]


class HealthStatus(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, Any]
    models: Optional[Dict[str, Any]] = None


class VersionInfo(BaseModel):
    version: str
    api_version: str
    whisper_version: str
    build: Dict[str, str]


class WebSocketMessage(BaseModel):
    type: Literal["audio", "config", "end", "partial", "final", "error", "ping"]
    data: Optional[Any] = None
    timestamp: Optional[float] = None
    is_final: Optional[bool] = None
    text: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None
    code: Optional[str] = None
    message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class SubscriptionStatusResponse(BaseModel):
    passport_user_id: str
    stripe_subscription_id: Optional[str] = None
    status: str
    current_period_end: Optional[datetime] = None
    tier: str = "Aether Audio Pro"
