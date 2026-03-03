"""GPU model pool management."""
import os
from typing import Dict, Optional
from collections import OrderedDict
import structlog
import torch


logger = structlog.get_logger()


class GPUPool:
    """Manages GPU model loading with LRU eviction."""
    
    _models: Dict[str, any] = OrderedDict()
    _max_models: int = 4  # Maximum concurrent models
    _compute_type: str = "float16"
    _device: str = "cuda" if torch.cuda.is_available() else "cpu"
    
    @classmethod
    def warmup(cls):
        """Preload default models on startup."""
        preload_raw = os.getenv("WHISPER_PRELOAD_MODELS", "large-v3")
        preload_models = [m.strip() for m in preload_raw.split(",") if m.strip()]
        
        logger.info("warming_up_models", models=preload_models)
        
        for model_name in preload_models:
            try:
                cls.load_model(model_name)
                logger.info("model_loaded", model=model_name)
            except Exception as e:
                logger.error("model_load_failed", model=model_name, error=str(e))
    
    @classmethod
    def cleanup(cls):
        """Unload all models on shutdown."""
        logger.info("cleaning_up_models", count=len(cls._models))
        
        for model_name in list(cls._models.keys()):
            cls.unload_model(model_name)
        
        # Clear CUDA cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    @classmethod
    def load_model(cls, model_name: str, compute_type: Optional[str] = None) -> any:
        """Load a model into GPU memory."""
        from faster_whisper import WhisperModel
        
        compute_type = compute_type or cls._compute_type
        cache_key = f"{model_name}:{compute_type}"
        
        # Check if already loaded
        if cache_key in cls._models:
            # Move to end (most recently used)
            cls._models.move_to_end(cache_key)
            return cls._models[cache_key]
        
        # Check if we need to evict
        if len(cls._models) >= cls._max_models:
            cls._evict_lru()
        
        # Load model
        logger.info("loading_model", model=model_name, compute_type=compute_type)
        
        models_dir = os.getenv("WHISPER_MODELS_DIR", "/models")
        
        model = WhisperModel(
            model_name,
            device=cls._device,
            compute_type=compute_type,
            cpu_threads=4 if cls._device == "cpu" else 0,
            num_workers=1,
            download_root=models_dir
        )
        
        cls._models[cache_key] = model
        
        # Log GPU memory
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(
                "gpu_memory",
                allocated_gb=round(allocated, 2),
                reserved_gb=round(reserved, 2)
            )
        
        return model
    
    @classmethod
    def unload_model(cls, model_name: str, compute_type: Optional[str] = None):
        """Unload a model from GPU memory."""
        cache_key = f"{model_name}:{compute_type or cls._compute_type}"
        
        if cache_key in cls._models:
            logger.info("unloading_model", model=model_name)
            del cls._models[cache_key]
            
            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    @classmethod
    def get_model(cls, model_name: str, compute_type: Optional[str] = None) -> any:
        """Get a model, loading if necessary."""
        return cls.load_model(model_name, compute_type)
    
    @classmethod
    def _evict_lru(cls):
        """Evict least recently used model."""
        if cls._models:
            # Get first item (least recently used)
            lru_key = next(iter(cls._models))
            lru_model = lru_key.split(":")[0]
            
            logger.info("evicting_model", model=lru_model)
            cls.unload_model(lru_model)
    
    @classmethod
    def get_loaded_models(cls) -> Dict[str, bool]:
        """Get list of loaded models."""
        return {
            key.split(":")[0]: True 
            for key in cls._models.keys()
        }
    
    @classmethod
    def get_gpu_info(cls) -> Dict:
        """Get GPU information."""
        if not torch.cuda.is_available():
            return {"available": False}
        
        return {
            "available": True,
            "count": torch.cuda.device_count(),
            "name": torch.cuda.get_device_name(0),
            "memory": {
                "total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                "allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 2),
                "reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 2)
            }
        }
