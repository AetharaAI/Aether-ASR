"""Model information endpoints."""
from fastapi import APIRouter
from typing import List

from app.models.schemas import ModelsResponse, ModelInfo


router = APIRouter()

# Model definitions
AVAILABLE_MODELS = [
    ModelInfo(
        id="tiny",
        name="Whisper Tiny",
        description="Fastest model, suitable for quick transcriptions with acceptable accuracy",
        parameters="39M",
        languages=["en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"],
        capabilities={
            "transcription": True,
            "translation": True,
            "vad": True,
            "diarization": False,
            "word_timestamps": True
        },
        resources={
            "vram_gb": 1,
            "compute_types": ["float16", "int8"],
            "relative_speed": 32
        }
    ),
    ModelInfo(
        id="base",
        name="Whisper Base",
        description="Good balance of speed and accuracy for most use cases",
        parameters="74M",
        languages=["en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"],
        capabilities={
            "transcription": True,
            "translation": True,
            "vad": True,
            "diarization": False,
            "word_timestamps": True
        },
        resources={
            "vram_gb": 1,
            "compute_types": ["float16", "int8"],
            "relative_speed": 16
        }
    ),
    ModelInfo(
        id="small",
        name="Whisper Small",
        description="Better accuracy, suitable for professional use",
        parameters="244M",
        languages=["en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"],
        capabilities={
            "transcription": True,
            "translation": True,
            "vad": True,
            "diarization": True,
            "word_timestamps": True
        },
        resources={
            "vram_gb": 2,
            "compute_types": ["float16", "int8"],
            "relative_speed": 6
        }
    ),
    ModelInfo(
        id="medium",
        name="Whisper Medium",
        description="High accuracy for professional transcription",
        parameters="769M",
        languages=["en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"],
        capabilities={
            "transcription": True,
            "translation": True,
            "vad": True,
            "diarization": True,
            "word_timestamps": True
        },
        resources={
            "vram_gb": 5,
            "compute_types": ["float16", "int8", "float32"],
            "relative_speed": 2
        }
    ),
    ModelInfo(
        id="large-v3",
        name="Whisper Large v3",
        description="Best accuracy, recommended for production use",
        parameters="1550M",
        languages=["en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"],
        capabilities={
            "transcription": True,
            "translation": True,
            "vad": True,
            "diarization": True,
            "word_timestamps": True
        },
        resources={
            "vram_gb": 6,
            "compute_types": ["float16", "int8", "float32"],
            "relative_speed": 1
        }
    )
]


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List available models and their capabilities."""
    return ModelsResponse(models=AVAILABLE_MODELS)
