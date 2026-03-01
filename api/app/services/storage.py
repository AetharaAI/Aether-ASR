"""MinIO storage operations."""
from minio import Minio
from minio.error import S3Error
import io
from typing import Optional

from app.config import settings


# MinIO client
_minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Get or create MinIO client."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
    return _minio_client


async def init_storage():
    """Initialize storage bucket."""
    client = get_minio_client()
    
    # Create bucket if it doesn't exist
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)
        
        # Set lifecycle policy for temp files
        lifecycle_config = {
            "Rules": [
                {
                    "ID": "DeleteTempFiles",
                    "Status": "Enabled",
                    "Filter": {
                        "Prefix": "temp/"
                    },
                    "Expiration": {
                        "Days": 1
                    }
                }
            ]
        }
        # Note: MinIO Python client doesn't support lifecycle directly
        # This would need to be done via AWS CLI or MinIO Console


async def check_storage() -> bool:
    """Check storage connectivity."""
    try:
        client = get_minio_client()
        return client.bucket_exists(settings.MINIO_BUCKET)
    except Exception:
        return False


async def upload_file(
    file_bytes: bytes,
    filename: str,
    job_id: str,
    folder: str = "audio"
) -> str:
    """Upload file to MinIO."""
    client = get_minio_client()
    
    # Generate storage key
    ext = filename.split(".")[-1] if "." in filename else "bin"
    storage_key = f"{folder}/{job_id}/original.{ext}"
    
    # Upload
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
        data=io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=f"audio/{ext}"
    )
    
    return storage_key


async def download_file(storage_key: str) -> bytes:
    """Download file from MinIO."""
    client = get_minio_client()
    
    response = client.get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key
    )
    
    return response.read()


async def upload_artifact(
    data: bytes,
    job_id: str,
    artifact_type: str,
    format: str
) -> str:
    """Upload transcript artifact."""
    client = get_minio_client()
    
    storage_key = f"transcripts/{job_id}/{artifact_type}.{format}"
    
    content_type_map = {
        "json": "application/json",
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain"
    }
    
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type_map.get(format, "application/octet-stream")
    )
    
    return storage_key


async def download_artifact(job_id: str, format: str):
    """Download transcript artifact."""
    client = get_minio_client()
    
    storage_key = f"transcripts/{job_id}/transcript.{format}"
    
    try:
        response = client.get_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=storage_key
        )
        return response
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise


async def delete_job_files(job_id: str):
    """Delete all files for a job."""
    client = get_minio_client()
    
    # List and delete objects with job_id prefix
    objects = client.list_objects(
        settings.MINIO_BUCKET,
        prefix=f"audio/{job_id}/",
        recursive=True
    )
    for obj in objects:
        client.remove_object(settings.MINIO_BUCKET, obj.object_name)
    
    objects = client.list_objects(
        settings.MINIO_BUCKET,
        prefix=f"transcripts/{job_id}/",
        recursive=True
    )
    for obj in objects:
        client.remove_object(settings.MINIO_BUCKET, obj.object_name)
    
    objects = client.list_objects(
        settings.MINIO_BUCKET,
        prefix=f"temp/{job_id}/",
        recursive=True
    )
    for obj in objects:
        client.remove_object(settings.MINIO_BUCKET, obj.object_name)
