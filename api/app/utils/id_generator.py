"""ID generation utilities."""
import ulid


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{ulid.new().str.lower()}"


def generate_ulid() -> str:
    """Generate a ULID."""
    return ulid.new().str.lower()
