"""ID generation utilities."""
import uuid


def generate_job_id() -> str:
    """Generate a unique job ID using UUID4."""
    return f"job_{uuid.uuid4().hex}"


def generate_ulid() -> str:
    """Generate a unique ID using UUID4."""
    return uuid.uuid4().hex
