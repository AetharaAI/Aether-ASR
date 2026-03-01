"""Input validation utilities."""
from pydantic import BaseModel
from typing import Optional
import io

from app.config import settings


class ValidationResult(BaseModel):
    valid: bool
    format: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    error_message: Optional[str] = None


# Magic numbers for audio formats
AUDIO_MAGIC = {
    b"\xff\xfb": "mp3",
    b"\xff\xf3": "mp3",
    b"\xff\xf2": "mp3",
    b"ID3": "mp3",
    b"RIFF": "wav",
    b"fLaC": "flac",
    b"OggS": "ogg",
    b"\x00\x00\x00\x1cftypM4A": "m4a",
}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".opus"}
ALLOWED_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/ogg", "audio/vorbis", "audio/opus",
    "audio/flac", "audio/x-flac",
    "audio/webm"
}


async def validate_audio_file(file_bytes: bytes, filename: str) -> ValidationResult:
    """Validate audio file format and size."""
    
    # Check file size
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_size:
        return ValidationResult(
            valid=False,
            error_message=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
        )
    
    # Check extension
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if f".{ext}" not in ALLOWED_EXTENSIONS:
        return ValidationResult(
            valid=False,
            error_message=f"Unsupported file extension: .{ext}"
        )
    
    # Check magic numbers
    detected_format = None
    for magic, fmt in AUDIO_MAGIC.items():
        if file_bytes.startswith(magic):
            detected_format = fmt
            break
    
    if not detected_format:
        # Try to detect by content analysis
        detected_format = _detect_format_by_content(file_bytes)
    
    if not detected_format:
        return ValidationResult(
            valid=False,
            error_message="Could not detect audio format from file content"
        )
    
    # Try to decode to get duration
    try:
        duration, sample_rate, channels = _get_audio_info(file_bytes)
        
        if duration and duration > settings.MAX_DURATION_SECONDS:
            return ValidationResult(
                valid=False,
                error_message=f"Audio duration exceeds {settings.MAX_DURATION_SECONDS} seconds"
            )
        
        return ValidationResult(
            valid=True,
            format=detected_format,
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels
        )
    
    except Exception as e:
        return ValidationResult(
            valid=False,
            error_message=f"Failed to decode audio: {str(e)}"
        )


def _detect_format_by_content(file_bytes: bytes) -> Optional[str]:
    """Try to detect format by analyzing content."""
    # Check for MP3 without ID3
    if file_bytes[0:2] in [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"]:
        return "mp3"
    
    # Check for WAV
    if file_bytes[0:4] == b"RIFF" and file_bytes[8:12] == b"WAVE":
        return "wav"
    
    # Check for OGG
    if file_bytes[0:4] == b"OggS":
        return "ogg"
    
    # Check for FLAC
    if file_bytes[0:4] == b"fLaC":
        return "flac"
    
    # Check for MP4/M4A
    if file_bytes[4:8] == b"ftyp":
        return "m4a"
    
    return None


def _get_audio_info(file_bytes: bytes) -> tuple[Optional[float], Optional[int], Optional[int]]:
    """Get audio duration, sample rate, and channels."""
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(io.BytesIO(file_bytes))
        
        duration = len(audio) / 1000.0  # Convert ms to seconds
        sample_rate = audio.frame_rate
        channels = audio.channels
        
        return duration, sample_rate, channels
    
    except ImportError:
        # pydub not available, return None
        return None, None, None
    
    except Exception:
        return None, None, None
