"""MinIO storage operations for worker."""
from minio import Minio
from minio.error import S3Error
import io
import os


# MinIO client
_minio_client = None


def get_minio_client():
    """Get or create MinIO client."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
        )
    return _minio_client


def download_file(storage_key: str) -> bytes:
    """Download file from MinIO."""
    client = get_minio_client()
    bucket = os.getenv("MINIO_BUCKET", "asr-storage")
    
    response = client.get_object(bucket, storage_key)
    return response.read()


def upload_artifact(
    data: bytes,
    job_id: str,
    artifact_type: str,
    format: str
) -> str:
    """Upload transcript artifact."""
    client = get_minio_client()
    bucket = os.getenv("MINIO_BUCKET", "asr-storage")
    
    storage_key = f"transcripts/{job_id}/{artifact_type}.{format}"
    
    content_type_map = {
        "json": "application/json",
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain"
    }
    
    client.put_object(
        bucket_name=bucket,
        object_name=storage_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type_map.get(format, "application/octet-stream")
    )
    
    return storage_key
